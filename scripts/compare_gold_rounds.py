"""Compare map-ui-newset500 result JSON against Round3 baseline."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _case_map(doc: dict) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for c in doc.get("rows") or doc.get("cases") or doc.get("results") or []:
        cid = str(c.get("id") or c.get("qid") or c.get("case_id") or "")
        if not cid:
            continue
        ok = bool(c.get("ok") or c.get("passed") or c.get("pass"))
        out[cid] = ok
    return out


def compare(before_path: Path, after_path: Path) -> dict:
    before = json.loads(before_path.read_text(encoding="utf-8"))
    after = json.loads(after_path.read_text(encoding="utf-8"))
    bm = _case_map(before)
    am = _case_map(after)
    fixed = sorted(cid for cid, ok in am.items() if ok and bm.get(cid) is False)
    regressed = sorted(cid for cid, ok in am.items() if (not ok) and bm.get(cid) is True)
    still_fail = sorted(cid for cid, ok in am.items() if (not ok) and bm.get(cid) is False)
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
        "migration": {
            "fixed_n": len(fixed),
            "regressed_n": len(regressed),
            "still_fail_n": len(still_fail),
            "fixed_sample": fixed[:30],
            "regressed_sample": regressed[:30],
        },
    }
    return report


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: compare_gold_rounds.py BEFORE.json AFTER.json [OUT.json]")
        return 2
    before = Path(sys.argv[1])
    after = Path(sys.argv[2])
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("artifacts/semantic_architecture_v2/final_vs_round3.json")
    report = compare(before, after)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = out.with_suffix(".md")
    lines = [
        "# Final vs Round3",
        "",
        f"- Round3: {report['before']['passed']}/{report['before']['total']} ({report['before']['accuracy_pct']}%)",
        f"- v2: {report['after']['passed']}/{report['after']['total']} ({report['after']['accuracy_pct']}%)",
        f"- delta: {report['delta_passed']:+d} ({report['delta_accuracy_pct']:+.1f}%p)",
        f"- fixed: {report['migration']['fixed_n']}, regressed: {report['migration']['regressed_n']}, still_fail: {report['migration']['still_fail_n']}",
        "",
    ]
    md.write_text("\n".join(lines), encoding="utf-8")
    print(md.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
