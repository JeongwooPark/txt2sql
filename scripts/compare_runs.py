"""두 평가 런을 비교한다. SQL 토큰 일치는 지표로 쓰지 않는다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from llm2sql.evaluation.compare import compare, to_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--a", required=True, type=Path)
    parser.add_argument("--b", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    a = json.loads(args.a.read_text(encoding="utf-8"))
    b = json.loads(args.b.read_text(encoding="utf-8"))
    cmp = compare(a, b)
    md = to_markdown(cmp)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        if args.out.suffix == ".json":
            args.out.write_text(
                json.dumps(cmp, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        else:
            args.out.write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
