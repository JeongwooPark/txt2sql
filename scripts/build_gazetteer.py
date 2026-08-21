"""DB에서 부산 지명 사전(gazetteer_data.json)을 만든다."""

from __future__ import annotations

import json
from pathlib import Path

from llm2sql.config import load_settings
from llm2sql.db import connect

OUT = Path(__file__).resolve().parents[1] / "llm2sql" / "gazetteer_data.json"

SIDO_ALIASES = ["부산시"]
# 부산은 별칭으로만 두고 스캔에서는 제외(gazetteer.load)


def _names(rows: list[dict], key: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for row in rows:
        name = str(row[key] or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def main() -> int:
    settings = load_settings()
    with connect(settings.database_url) as conn:
        legal = conn.execute(
            """
            SELECT DISTINCT regexp_replace(trim("A4"), '.* ', '') AS dong
            FROM "AL_D010_26_20250704"
            WHERE "A4" LIKE '부산광역시%'
              AND trim("A4") <> ''
            ORDER BY 1
            """
        ).fetchall()
        admin = conn.execute(
            """
            SELECT DISTINCT trim("ADM_NM") AS name
            FROM "BND_ADM_DONG_PG"
            WHERE "ADM_CD" LIKE '21%'
              AND "ADM_NM" IS NOT NULL
            ORDER BY 1
            """
        ).fetchall()
        sido = conn.execute(
            """
            SELECT DISTINCT "CTP_KOR_NM" AS name
            FROM "TL_KODIS_BAS_26_202507"
            WHERE "CTP_KOR_NM" IS NOT NULL
            ORDER BY 1
            """
        ).fetchall()
        gu = conn.execute(
            """
            SELECT DISTINCT "SIG_KOR_NM" AS name
            FROM "TL_KODIS_BAS_26_202507"
            WHERE "SIG_KOR_NM" IS NOT NULL
            ORDER BY 1
            """
        ).fetchall()

    payload = {
        "sido": _names(sido, "name"),
        "sido_aliases": SIDO_ALIASES,
        "sigungu": _names(gu, "name"),
        "legal_dong": _names(legal, "dong"),
        "admin_dong": _names(admin, "name"),
    }
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {OUT.name}: "
        f"sido={len(payload['sido'])} gu={len(payload['sigungu'])} "
        f"legal={len(payload['legal_dong'])} admin={len(payload['admin_dong'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
