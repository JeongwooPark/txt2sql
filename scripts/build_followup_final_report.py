"""Build follow-up final report vs Round3."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from txt2sql.evaluation.case_map import case_pass_map, case_rows
from txt2sql.evaluation.count_mismatch import decompose_count_mismatches
from txt2sql.evaluation.execution_sources import share_execution_sources
from txt2sql.evaluation.stage_eval import migrate_failures

ROOT = Path(__file__).resolve().parents[1]
AFTER = ROOT / "tests/map_ui_gold500/results/mapui_newset500_followup_20260826_152056.json"
BEFORE = ROOT / "tests/map_ui_gold500/results/mapui_newset500_round3_20260826_120607.json"
OUT_DIR = ROOT / "artifacts/semantic_architecture_v2_followup"


def pct(a: int, b: int) -> float:
    return round(100.0 * a / b, 1) if b else 0.0


def main() -> None:
    after = json.loads(AFTER.read_text(encoding="utf-8"))
    before = json.loads(BEFORE.read_text(encoding="utf-8"))
    mig = migrate_failures(case_pass_map(before), case_pass_map(after))
    share = share_execution_sources(after)
    cm = decompose_count_mismatches(after)

    by_kind: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    by_cat: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in case_rows(after):
        kind = str(row.get("kind") or "unknown")
        cat = str(row.get("cat") or "na")
        by_kind[kind][1] += 1
        by_cat[cat][1] += 1
        if row.get("pass"):
            by_kind[kind][0] += 1
            by_cat[cat][0] += 1

    kind_acc = {
        k: {"passed": v[0], "total": v[1], "pct": pct(v[0], v[1])}
        for k, v in sorted(by_kind.items())
    }
    cat_acc = {
        k: {"passed": v[0], "total": v[1], "pct": pct(v[0], v[1])}
        for k, v in sorted(by_cat.items())
    }

    cat5_key = next((k for k in cat_acc if str(k).startswith("5")), None)
    report = {
        "followup": {
            "passed": after.get("passed"),
            "total": after.get("total"),
            "accuracy_pct": after.get("accuracy_pct"),
            "path": str(AFTER),
        },
        "round3": {
            "passed": before.get("passed"),
            "total": before.get("total"),
            "accuracy_pct": before.get("accuracy_pct"),
        },
        "delta_passed": (after.get("passed") or 0) - (before.get("passed") or 0),
        "delta_accuracy_pct": (after.get("accuracy_pct") or 0)
        - (before.get("accuracy_pct") or 0),
        "migration": {k: len(mig[k]) for k in ("fixed", "regressed", "still_pass", "still_fail")},
        "fixed_ids": mig["fixed"],
        "regressed_ids": mig["regressed"],
        "execution_sources": share,
        "by_kind": kind_acc,
        "by_cat": cat_acc,
        "count_mismatch": {
            "total": cm["total_count_mismatch"],
            "concrete_pct": cm["concrete_pct"],
            "counts": cm["counts"],
        },
        "gates": {
            "overall_gt_48_8": (after.get("accuracy_pct") or 0) > 48.8,
            "scalar_pct": kind_acc.get("scalar", {}).get("pct"),
            "group_pct": kind_acc.get("group", {}).get("pct"),
            "cat5_pct": (cat_acc.get(cat5_key) or {}).get("pct") if cat5_key else None,
            "regressed_le_fixed": len(mig["regressed"]) <= len(mig["fixed"]),
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "final_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Semantic Architecture v2 Follow-up — Final Gold",
        "",
        f"- Round3: {report['round3']['passed']}/{report['round3']['total']} ({report['round3']['accuracy_pct']}%)",
        f"- Follow-up: {report['followup']['passed']}/{report['followup']['total']} ({report['followup']['accuracy_pct']}%)",
        f"- Delta: {report['delta_passed']:+d} ({report['delta_accuracy_pct']:+.1f}%p)",
        (
            f"- Migration: fixed={report['migration']['fixed']} "
            f"regressed={report['migration']['regressed']} "
            f"still_pass={report['migration']['still_pass']} "
            f"still_fail={report['migration']['still_fail']}"
        ),
        f"- Execution sources: {share['counts']}",
        f"- Share %: {share['share_pct']}",
        "",
        "## by_kind",
    ]
    for key, val in kind_acc.items():
        lines.append(f"- {key}: {val['passed']}/{val['total']} ({val['pct']}%)")
    lines.extend(
        [
            "",
            "## Gates",
            f"- overall>48.8: {report['gates']['overall_gt_48_8']}",
            f"- scalar: {report['gates']['scalar_pct']}%",
            f"- group: {report['gates']['group_pct']}%",
            f"- cat5: {report['gates']['cat5_pct']}%",
            f"- regressed<=fixed: {report['gates']['regressed_le_fixed']}",
            f"- count-mismatch concrete: {cm['concrete_pct']}%",
            "",
            f"- gold: `{AFTER.name}`",
        ]
    )
    (OUT_DIR / "final_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", OUT_DIR / "final_report.md")


if __name__ == "__main__":
    main()
