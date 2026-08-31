"""pnu_def·행정동 경계에서 gazetteer_data.json을 만든다."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from txt2sql.config import Settings
from txt2sql.db import connect

DATA_PATH = Path(__file__).resolve().parent / "gazetteer_data.json"

# 공식 시도명과 별칭. 짧은 별칭(서울·부산)은 스캔에서 빼 고유명사 오탐을 막는다.
SIDO_ALIASES = [
    "서울시",
    "부산시",
    "대구시",
    "인천시",
    "광주시",
    "대전시",
    "울산시",
    "세종시",
]
_FALSE_TAIL = {
    "공동",
    "이동",
    "수동",
    "자동",
    "유동",
    "부동",
    "주동",
    "전동",
    "구동",
    "운동",
    "행동",
    "활동",
    "진동",
    "변동",
    "연동",
    "가동",
    "충동",
    "행정동",
    "법정동",
}


def gazetteer_data_path() -> Path:
    return DATA_PATH


def names_from_rows(rows: list[dict[str, Any]], key: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for row in rows:
        name = str(row[key] or "").strip()
        if not name or name in seen or name in _FALSE_TAIL or len(name) < 2:
            continue
        if "직할시" in name:
            continue
        seen.add(name)
        out.append(name)
    return out


def collect_gazetteer_payload(
    conn: Any,
    *,
    default_sido: str | None = None,
) -> dict[str, Any]:
    sido = conn.execute(
        """
        SELECT DISTINCT trim("PNU_NM") AS name
        FROM pnu_def
        WHERE "PNU" LIKE '__00000000'
          AND trim("PNU_NM") <> ''
          AND trim("PNU_NM") <> '전국'
          AND trim("PNU_NM") NOT LIKE '%직할시'
        ORDER BY 1
        """
    ).fetchall()
    gu = conn.execute(
        """
        SELECT DISTINCT regexp_replace(trim("PNU_NM"), '.* ', '') AS name
        FROM pnu_def
        WHERE "PNU" LIKE '%00000'
          AND "PNU" NOT LIKE '%00000000'
          AND trim("PNU_NM") <> ''
        ORDER BY 1
        """
    ).fetchall()
    gu_sido_rows = conn.execute(
        """
        SELECT
          regexp_replace(trim("PNU_NM"), '.* ', '') AS gu,
          split_part(trim("PNU_NM"), ' ', 1) AS sido
        FROM pnu_def
        WHERE "PNU" LIKE '%00000'
          AND "PNU" NOT LIKE '%00000000'
          AND trim("PNU_NM") LIKE '% %'
        """
    ).fetchall()
    gu_pnu_rows = conn.execute(
        """
        SELECT
          regexp_replace(trim("PNU_NM"), '.* ', '') AS gu,
          left("PNU", 5) AS pnu_prefix
        FROM pnu_def
        WHERE "PNU" LIKE '%00000'
          AND "PNU" NOT LIKE '%00000000'
          AND trim("PNU_NM") <> ''
        """
    ).fetchall()
    legal = conn.execute(
        """
        SELECT DISTINCT regexp_replace(trim("PNU_NM"), '.* ', '') AS name
        FROM pnu_def
        WHERE "PNU" NOT LIKE '%00000'
          AND trim("PNU_NM") <> ''
          AND (
                regexp_replace(trim("PNU_NM"), '.* ', '') ~ '[동가면읍리]$'
             OR regexp_replace(trim("PNU_NM"), '.* ', '') ~ '동[0-9]+가$'
          )
          AND regexp_replace(trim("PNU_NM"), '.* ', '') !~ '[0-9]+동$'
        ORDER BY 1
        """
    ).fetchall()
    legal_dong_sigungu_rows = conn.execute(
        """
        SELECT DISTINCT
          regexp_replace(trim("PNU_NM"), '.* ', '') AS dong,
          split_part(trim("PNU_NM"), ' ', 2) AS gu
        FROM pnu_def
        WHERE "PNU" NOT LIKE '%00000'
          AND trim("PNU_NM") LIKE '% %'
          AND split_part(trim("PNU_NM"), ' ', 2) ~ '[구군]$'
          AND (
                regexp_replace(trim("PNU_NM"), '.* ', '') ~ '[동가면읍리]$'
             OR regexp_replace(trim("PNU_NM"), '.* ', '') ~ '동[0-9]+가$'
          )
        ORDER BY 1, 2
        """
    ).fetchall()
    admin = conn.execute(
        """
        SELECT DISTINCT trim("ADM_NM") AS name
        FROM "BND_ADM_DONG_PG"
        WHERE "ADM_NM" IS NOT NULL
        ORDER BY 1
        """
    ).fetchall()
    admin_pref_rows = conn.execute(
        """
        SELECT trim("ADM_NM") AS name,
               array_agg(DISTINCT left("ADM_CD", 2) ORDER BY left("ADM_CD", 2)) AS prefixes
        FROM "BND_ADM_DONG_PG"
        WHERE "ADM_NM" IS NOT NULL
          AND "ADM_CD" IS NOT NULL
        GROUP BY 1
        """
    ).fetchall()

    sigungu_sido: dict[str, list[str]] = {}
    for row in gu_sido_rows:
        gu_name = str(row["gu"] or "").strip()
        sido_name = str(row["sido"] or "").strip()
        if not gu_name or not sido_name or "직할시" in sido_name:
            continue
        bucket = sigungu_sido.setdefault(gu_name, [])
        if sido_name not in bucket:
            bucket.append(sido_name)

    from txt2sql.gazetteer import choose_sigungu_pnu_code

    # 동명 구(중구 등): 후보를 모두 모은 뒤 정책으로 대표 PNU를 고른다.
    # 정책: default_sido 접두 일치 > 가장 짧은 코드 (부산 26 하드 우선 금지).
    preferred_sido = (default_sido or "부산광역시").strip() or "부산광역시"
    candidates: dict[str, list[str]] = {}
    for row in gu_pnu_rows:
        gu_name = str(row["gu"] or "").strip()
        code = str(row["pnu_prefix"] or "").strip()
        if not gu_name or not code.isdigit() or len(code) != 5:
            continue
        bucket = candidates.setdefault(gu_name, [])
        if code not in bucket:
            bucket.append(code)

    sigungu_pnu_prefix: dict[str, str] = {}
    sigungu_pnu_candidates: dict[str, list[str]] = {}
    for gu_name, codes in candidates.items():
        ordered = sorted(codes)
        sigungu_pnu_candidates[gu_name] = ordered
        chosen = choose_sigungu_pnu_code(
            ordered,
            question_sido=None,
            default_sido=preferred_sido,
        )
        if chosen:
            sigungu_pnu_prefix[gu_name] = chosen

    admin_dong_prefixes: dict[str, list[str]] = {}
    for row in admin_pref_rows:
        name = str(row["name"] or "").strip()
        prefixes = [str(p) for p in (row["prefixes"] or []) if str(p).isdigit()]
        if name and prefixes:
            admin_dong_prefixes[name] = prefixes

    legal_dong_sigungu: dict[str, list[str]] = {}
    for row in legal_dong_sigungu_rows:
        dong = str(row["dong"] or "").strip()
        gu_name = str(row["gu"] or "").strip()
        if not dong or not gu_name:
            continue
        bucket = legal_dong_sigungu.setdefault(dong, [])
        if gu_name not in bucket:
            bucket.append(gu_name)

    return {
        "sido": names_from_rows(sido, "name"),
        "sido_aliases": list(SIDO_ALIASES),
        "sigungu": names_from_rows(gu, "name"),
        "sigungu_sido": sigungu_sido,
        "sigungu_pnu_prefix": sigungu_pnu_prefix,
        "sigungu_pnu_candidates": sigungu_pnu_candidates,
        "legal_dong": names_from_rows(legal, "name"),
        "legal_dong_sigungu": legal_dong_sigungu,
        "admin_dong": names_from_rows(admin, "name"),
        "admin_dong_prefixes": admin_dong_prefixes,
    }


def write_gazetteer_payload(
    payload: dict[str, Any],
    path: Path | None = None,
) -> Path:
    out = path or DATA_PATH
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    from txt2sql.gazetteer import invalidate_gazetteer

    invalidate_gazetteer()
    return out


def gazetteer_counts(payload: dict[str, Any]) -> dict[str, int]:
    return {
        "sido": len(payload.get("sido") or []),
        "sigungu": len(payload.get("sigungu") or []),
        "legal_dong": len(payload.get("legal_dong") or []),
        "admin_dong": len(payload.get("admin_dong") or []),
    }


def rebuild_gazetteer(
    settings: Settings,
    *,
    path: Path | None = None,
) -> dict[str, Any]:
    """pnu_def·BND_ADM_DONG_PG를 읽어 지명 JSON을 다시 쓰고 메모리 캐시를 비운다.

    내용이 같으면 파일을 다시 쓰지 않는다.
    """
    with connect(settings.database_url) as conn:
        payload = collect_gazetteer_payload(
            conn,
            default_sido=settings.default_sido,
        )
    out = path or DATA_PATH
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    counts = gazetteer_counts(payload)
    if out.exists() and out.read_text(encoding="utf-8") == text:
        return {
            "ok": True,
            "path": str(out),
            "counts": counts,
            "unchanged": True,
        }
    out.write_text(text, encoding="utf-8")
    from txt2sql.gazetteer import invalidate_gazetteer

    invalidate_gazetteer()
    return {
        "ok": True,
        "path": str(out),
        "counts": counts,
        "unchanged": False,
    }
