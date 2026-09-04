"""Compare gold test 1 vs gold test 2 evaluation results."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def reason_bucket(reason: str) -> str:
    r = reason or ""
    if "count-mismatch" in r:
        return "count-mismatch"
    if "scalar-mismatch" in r:
        return "scalar-mismatch"
    if "list-top-missing" in r:
        return "list-top-missing"
    if "name-missing" in r:
        return "name-missing"
    if "compare-num-missing" in r:
        return "compare-num-missing"
    if "engine-fail" in r:
        return r.split()[0] if "engine-fail" in r else "engine-fail"
    if "group-mismatch" in r:
        return "group-mismatch"
    return r.split()[0] if r else "unknown"


def analyze(data: dict, label: str) -> dict:
    rows = data.get("rows") or []
    fails = [r for r in rows if not r.get("pass")]
    by_kind = data.get("by_kind") or {}
    by_cat = data.get("by_cat") or {}
    routes = Counter(r.get("route") or "?" for r in fails)
    buckets = Counter(reason_bucket(r.get("reason") or "") for r in fails)
    root = Counter()
    for r in fails:
        for c in r.get("root_causes") or []:
            root[c] += 1
    return {
        "label": label,
        "passed": data.get("passed"),
        "total": data.get("total"),
        "accuracy_pct": data.get("accuracy_pct"),
        "fail_reasons": dict(data.get("fail_reasons") or {}),
        "by_kind": by_kind,
        "by_cat": by_cat,
        "fail_route_top": routes.most_common(12),
        "fail_bucket_top": buckets.most_common(12),
        "root_cause_top": root.most_common(10),
        "count_mismatch_n": buckets.get("count-mismatch", 0),
    }


def main() -> None:
    gt1_path = sys.argv[1] if len(sys.argv) > 1 else "artifacts/evaluation/gold_test1_contract_fix_v2.json"
    gt2_path = sys.argv[2] if len(sys.argv) > 2 else "artifacts/evaluation/gold_test2_contract_fix.json"
    gt1 = analyze(load(gt1_path), "gold_test1")
    gt2 = analyze(load(gt2_path), "gold_test2")

    print("=== SUMMARY ===")
    for g in (gt1, gt2):
        print(f"{g['label']}: {g['passed']}/{g['total']} ({g['accuracy_pct']}%) count-mismatch={g['count_mismatch_n']}")

    print("\n=== FAIL BUCKETS (gt1 vs gt2) ===")
    all_b = sorted(set(gt1["fail_bucket_top"]) | set(gt2["fail_bucket_top"]), key=lambda x: -(gt1["fail_bucket_top"].count(x) + gt2["fail_bucket_top"].count(x)) if isinstance(x, str) else 0)
    b1 = dict(gt1["fail_bucket_top"])
    b2 = dict(gt2["fail_bucket_top"])
    keys = sorted(set(b1) | set(b2), key=lambda k: -(b1.get(k, 0) + b2.get(k, 0)))
    for k in keys[:15]:
        print(f"  {k}: gt1={b1.get(k,0)} gt2={b2.get(k,0)}")

    print("\n=== WEAK KIND (gt2 acc) ===")
    for kind, stats in sorted((gt2.get("by_kind") or {}).items(), key=lambda x: x[1].get("acc_pct", 0)):
        s = stats
        print(f"  {kind}: {s.get('ok')}/{s.get('n')} ({s.get('acc_pct')}%)")

    print("\n=== WEAK CAT (gt2 acc) ===")
    for cat, stats in sorted((gt2.get("by_cat") or {}).items(), key=lambda x: x[1].get("acc_pct", 0))[:12]:
        s = stats
        print(f"  {cat}: {s.get('ok')}/{s.get('n')} ({s.get('acc_pct')}%)")

    print("\n=== ROOT CAUSE gt2 ===")
    for c, n in gt2["root_cause_top"]:
        print(f"  {c}: {n}")

    out = {"gold_test1": gt1, "gold_test2": gt2}
    out_path = Path("artifacts/evaluation/gt1_gt2_compare.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
