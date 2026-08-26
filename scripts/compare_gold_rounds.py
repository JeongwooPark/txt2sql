"""Compare map-ui-newset500 result JSON against a baseline round."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from txt2sql.evaluation.stage_eval import migrate_failures, taxonomy_from_reason
from txt2sql.evaluation.case_map import case_rows, case_pass_map


def compare(before_path: Path, after_path: Path) -> dict[str, Any]:
    before = json.loads(before_path.read_text(encoding="utf-8"))
    after = json.loads(after_path.read_text(encoding="utf-8"))
    bm = case_pass_map(before)
    am = case_pass_map(after)
    mig = migrate_failures(bm, am)
    matched = len(set(bm) & set(am))
    fixed = mig["fixed"]
    regressed = mig["regressed"]
    still_fail = mig["still_fail"]
    still_pass = mig["still_pass"]
    # Taxonomy from after failures (prefer reason field)
    tax: Counter[str] = Counter()
    for row in case_rows(after):
        if case_pass_map({"rows": [row]}).get(str(row.get("id")), True):
            continue
        reason = str(row.get("reason") or row.get("fail_reason") or row.get("error") or "")
        tax[taxonomy_from_reason(reason)] += 1
    report = {
        "before": {
            "path": str(before_path),
            "passed": before.get("passed"),
            "total": before.get("total"),
            "accuracy_pct": before.get("accuracy_pct"),
            "latency": before.get("latency"),
            "by_kind": before.get("by_kind"),
        },
        "after": {
            "path": str(after_path),
            "passed": after.get("passed"),
            "total": after.get("total"),
            "accuracy_pct": after.get("accuracy_pct"),
            "latency": after.get("latency"),
            "by_kind": after.get("by_kind"),
        },
        "delta_accuracy_pct": (after.get("accuracy_pct") or 0) - (before.get("accuracy_pct") or 0),
        "delta_passed": (after.get("passed") or 0) - (before.get("passed") or 0),
        "matched_cases": matched,
        "migration": {
            "fixed_n": len(fixed),
            "regressed_n": len(regressed),
            "still_fail_n": len(still_fail),
            "still_pass_n": len(still_pass),
            "sum_n": len(fixed) + len(regressed) + len(still_fail) + len(still_pass),
            "fixed_sample": fixed[:30],
            "regressed_sample": regressed[:30],
        },
        "taxonomy_after_top": dict(tax.most_common(20)),
    }
    return report


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: compare_gold_rounds.py BEFORE.json AFTER.json [OUT.json]")
        return 2
    before = Path(sys.argv[1])
    after = Path(sys.argv[2])
    out = (
        Path(sys.argv[3])
        if len(sys.argv) > 3
        else Path("artifacts/semantic_architecture_v2/final_vs_round3.json")
    )
    report = compare(before, after)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = out.with_suffix(".md")
    m = report["migration"]
    lines = [
        "# Gold round compare",
        "",
        f"- Before: {report['before']['passed']}/{report['before']['total']} ({report['before']['accuracy_pct']}%)",
        f"- After: {report['after']['passed']}/{report['after']['total']} ({report['after']['accuracy_pct']}%)",
        f"- delta: {report['delta_passed']:+d} ({report['delta_accuracy_pct']:+.1f}%p)",
        f"- fixed: {m['fixed_n']}, regressed: {m['regressed_n']}, still_pass: {m['still_pass_n']}, still_fail: {m['still_fail_n']}",
        f"- sum check: {m['sum_n']} (matched={report['matched_cases']})",
        "",
    ]
    md.write_text("\n".join(lines), encoding="utf-8")
    print(md.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
