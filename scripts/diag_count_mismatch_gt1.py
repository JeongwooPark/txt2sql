"""Diagnose gold_test1 count-mismatch failures."""
from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

from txt2sql.evaluation.count_mismatch import decompose_count_mismatches  # noqa: E402


def _norm_sql(sql: str | None) -> str:
    return re.sub(r"\s+", " ", (sql or "").upper())


def classify_engine_vs_gold(case: dict, gold_sql: str | None) -> str:
    eng = _norm_sql(case.get("sql_full") or case.get("sql"))
    g = _norm_sql(gold_sql)
    if not g:
        return "no_gold_sql"
    if "ST_INTERSECTS" in g and "ST_INTERSECTS" not in eng:
        return "spatial_join_missing"
    if "BND_ADM_DONG" in g and "BND_ADM_DONG" not in eng:
        return "admin_boundary_not_used"
    if "AL_D198" in g and "AL_D010" in eng and "AL_D198" not in eng:
        return "wrong_dataset_d010_vs_d198"
    if "AL_D010" in g and "AL_D198" in eng and "AL_D010" not in eng:
        return "wrong_dataset_d198_vs_d010"
    if g.count("AND") > eng.count("AND") + 1:
        return "predicate_thinner"
    if eng and g and eng == g:
        return "sql_match_wrong_answer"
    if "COUNT(DISTINCT" in g and "COUNT(DISTINCT" not in eng:
        return "distinct_grain_missing"
    return "other_sql_divergence"


def main() -> int:
    eval_path = ROOT / "artifacts/evaluation/gold_test1_refreshed.json"
    gold_path = ROOT / "docs/평가문항_500.json"
    data = json.loads(eval_path.read_text(encoding="utf-8"))
    gold_doc = json.loads(gold_path.read_text(encoding="utf-8"))
    gold_map = {q["id"]: q for q in gold_doc["questions"]}

    fails = [
        r
        for r in data["rows"]
        if not r["pass"] and str(r.get("reason", "")).startswith("count-mismatch")
    ]
    print(f"count-mismatch: {len(fails)}")

    sql_class = Counter()
    samples: dict[str, list[str]] = defaultdict(list)
    for r in fails:
        cls = classify_engine_vs_gold(r, gold_map.get(r["id"], {}).get("sql"))
        sql_class[cls] += 1
        if len(samples[cls]) < 6:
            samples[cls].append(r["id"])

    print("\n=== engine SQL vs gold SQL ===")
    for k, n in sql_class.most_common():
        print(f"  {k}: {n}  e.g. {samples[k]}")

    sem = decompose_count_mismatches(data)
    print("\n=== semantic cause (count_mismatch.py) ===")
    for k, n in sorted(sem["counts"].items(), key=lambda x: -x[1]):
        print(f"  {k}: {n} ({sem['share_pct'][k]}%)")

    # pred magnitude
    import re as _re

    num_re = _re.compile(r"-?\d+(?:\.\d+)?")
    off_by = Counter()
    for r in fails:
        g = gold_map[r["id"]].get("gold", "")
        gm = num_re.findall(g.replace(",", ""))
        rm = num_re.findall(str(r.get("answer", "")).replace(",", ""))
        if gm and rm:
            try:
                gv, rv = float(gm[0]), float(rm[0])
                if gv == 0:
                    off_by["gold_zero"] += 1
                elif rv == 0:
                    off_by["engine_zero"] += 1
                elif abs(gv - rv) / max(gv, 1) < 0.05:
                    off_by["within_5pct"] += 1
                elif abs(gv - rv) <= 3:
                    off_by["off_by_1_3"] += 1
                else:
                    off_by["large_gap"] += 1
            except ValueError:
                off_by["unparsed"] += 1
        else:
            off_by["no_nums"] += 1
    print("\n=== magnitude ===")
    for k, n in off_by.most_common():
        print(f"  {k}: {n}")

    # DB spot check N050
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(url, row_factory=dict_row) as conn:
            for qid in ("N050", "N051", "N042"):
                gsql = gold_map[qid]["sql"]
                eng = (next(r for r in fails if r["id"] == qid).get("sql_full") or "").strip()
                gr = conn.execute(gsql).fetchone()
                er = conn.execute(eng).fetchone() if eng else None
                print(f"\n=== DB check {qid} ===")
                print(f"  gold SQL -> {dict(gr)}")
                print(f"  engine SQL -> {dict(er) if er else None}")

    out = {
        "total": len(fails),
        "sql_class": dict(sql_class),
        "sql_samples": {k: v for k, v in samples.items()},
        "semantic": sem,
        "magnitude": dict(off_by),
    }
    out_path = ROOT / "artifacts/evaluation/gold_test1_count_mismatch_diag.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
