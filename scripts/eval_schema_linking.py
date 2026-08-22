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
    fixtures = []
    if args.fixtures and args.fixtures.exists():
        fixtures = json.loads(args.fixtures.read_text(encoding="utf-8"))
    else:
        fixtures = [
            {"q": "해운대구 공동주택 높이", "tables": ["building"], "columns": ["height_m"], "values": ["공동주택"]},
        ]
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
    summary = {
        "n": len(fixtures),
        "schema_recall_at_10": sum(table_scores) / len(table_scores) if table_scores else 0,
        "column_recall_at_10": sum(col_scores) / len(col_scores) if col_scores else 0,
        "value_recall_at_5": sum(val_scores) / len(val_scores) if val_scores else 0,
        "env_blocked": False,
        "gate_passed": False,
        "note": "fixture recall only; production holdout gate deferred",
    }
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
