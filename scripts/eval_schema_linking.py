"""Schema linking evaluator. SQL 토큰 존재는 정답으로 쓰지 않는다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from llm2sql.semantic_catalog.linking import retrieve_columns, retrieve_tables, retrieve_values


def recall_at_k(gold: list[str], predicted: list[str], k: int) -> float:
    if not gold:
        return 1.0
    top = set(predicted[:k])
    return len(set(gold) & top) / len(set(gold))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    default_holdout = ROOT / "benchmarks" / "korean_postgis_v1" / "linking_holdout.json"
    path = args.fixtures or default_holdout
    if path.exists():
        fixtures = json.loads(path.read_text(encoding="utf-8"))
    else:
        fixtures = [
            {"q": "해운대구 공동주택 높이", "tables": ["building"], "columns": ["height_m"], "values": ["공동주택"]},
        ]
    fixtures = [item for item in fixtures if item.get("split", "holdout") == "holdout"]
    table_scores = []
    col_scores = []
    val_scores = []
    for item in fixtures:
        tables = [h.key for h in retrieve_tables(item["q"]).hits]
        cols = [h.key for h in retrieve_columns(item["q"]).hits]
        vals = [h.key for h in retrieve_values(item["q"]).hits]
        table_scores.append(recall_at_k(item.get("tables") or [], tables, 10))
        col_scores.append(recall_at_k(item.get("columns") or [], cols, 10))
        val_scores.append(recall_at_k(item.get("values") or [], vals, 5))
    n = len(fixtures)
    schema = sum(table_scores) / n if n else 0.0
    columns = sum(col_scores) / n if n else 0.0
    values = sum(val_scores) / n if n else 0.0
    gate = n >= 10 and schema >= 1.0 and values >= 1.0 and columns >= 1.0
    summary = {
        "n": n,
        "schema_recall_at_10": schema,
        "column_recall_at_10": columns,
        "value_recall_at_5": values,
        "join_path_accuracy": "fixture_only",
        "env_blocked": False,
        "gate_passed": gate,
        "note": "labeled expression+place holdout; Recall goals not relaxed",
        "d010_plus_entities": ["admin_area", "basic_zone", "industrial_complex"],
    }
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
