"""DB에서 전국 지명 사전(gazetteer_data.json)을 만든다."""

from __future__ import annotations

import sys

from txt2sql.config import load_settings
from txt2sql.gazetteer_build import rebuild_gazetteer


def main() -> int:
    result = rebuild_gazetteer(load_settings())
    counts = result.get("counts") or {}
    print(
        f"wrote {result.get('path')}: "
        f"sido={counts.get('sido', 0)} gu={counts.get('sigungu', 0)} "
        f"legal={counts.get('legal_dong', 0)} admin={counts.get('admin_dong', 0)}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
