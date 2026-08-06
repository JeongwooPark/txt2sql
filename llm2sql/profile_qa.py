"""장소·용도 기반 건물 특징 요약(집계) 답변."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row

_PROFILE_HINTS = (
    "특징",
    "특성",
    "요약",
    "어때",
    "어떤가",
    "어떤지",
    "프로필",
    "분포",
    "구성",
    "경향",
    "대략",
    "평균",
)

_USAGE_ALIASES: dict[str, str] = {
    "아파트": "공동주택",
    "공동주택": "공동주택",
    "단독주택": "단독주택",
    "다가구": "단독주택",
    "공장": "공장",
    "창고": "창고시설",
    "창고시설": "창고시설",
    "학교": "교육연구시설",
    "교육연구시설": "교육연구시설",
    "근린생활": "제1종근린생활시설",
    "업무시설": "업무시설",
    "숙박": "숙박시설",
    "종교": "종교시설",
}

_DONG = re.compile(r"([가-힣0-9]{1,12}동)")
_GU = re.compile(
    r"(중구|서구|동구|영도구|부산진구|동래구|남구|북구|해운대구|사하구|"
    r"금정구|강서구|연제구|수영구|사상구|기장군|[가-힣]{1,6}구)"
)


@dataclass(frozen=True)
class ProfileAnswer:
    intent: str
    answer: str
    sql: str
    tables: list[str]
    rows: list[dict[str, Any]]


def is_profile_question(question: str) -> bool:
    q = question.strip()
    if not q:
        return False
    if not any(k in q for k in _PROFILE_HINTS):
        return False
    # 장소 또는 용도 단서가 있어야 함
    if _DONG.search(q) or _GU.search(q):
        return True
    if any(k in q for k in _USAGE_ALIASES):
        return True
    if "건물" in q:
        return True
    return False


def answer_profile_question(
    conn: psycopg.Connection,
    question: str,
) -> ProfileAnswer | None:
    if not is_profile_question(question):
        return None

    q = question.strip()
    place = _extract_place(q)
    usage = _extract_usage(q)
    if not place and not usage:
        return None

    where: list[str] = []
    if place:
        if place.endswith("동"):
            where.append(f'("A4" LIKE \'% {place}\' OR "A4" = \'{place}\')')
        else:
            where.append(f'"A4" LIKE \'%{place}%\'')
    if usage:
        where.append(f'"A9" = \'{usage}\'')
    where_sql = " AND ".join(where)

    sql = f"""
SELECT
  COUNT(*) AS cnt,
  ROUND(AVG("A14")::numeric, 1) AS avg_area,
  ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY "A14")::numeric, 1) AS med_area,
  ROUND(MIN("A14")::numeric, 1) AS min_area,
  ROUND(MAX("A14")::numeric, 1) AS max_area,
  ROUND(AVG("A16")::numeric, 1) AS avg_height,
  ROUND(MAX("A16")::numeric, 1) AS max_height,
  ROUND(AVG("A26")::numeric, 1) AS avg_floors,
  ROUND(MAX("A26")::numeric, 0) AS max_floors,
  ROUND(AVG("A12")::numeric, 1) AS avg_bldg_area
FROM "AL_D010_26_20250704"
WHERE {where_sql}
""".strip()

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql)
        stats = cur.fetchone() or {}

        cur.execute(
            f"""
            SELECT "A11" AS structure, COUNT(*) AS n
            FROM "AL_D010_26_20250704"
            WHERE {where_sql}
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT 3
            """
        )
        structures = list(cur.fetchall())

        # 용도 미지정 시 용도 구성도 함께
        usages: list[dict[str, Any]] = []
        if not usage:
            cur.execute(
                f"""
                SELECT COALESCE("A9", '(미상)') AS usage, COUNT(*) AS n
                FROM "AL_D010_26_20250704"
                WHERE {where_sql}
                GROUP BY 1
                ORDER BY 2 DESC
                LIMIT 5
                """
            )
            usages = list(cur.fetchall())

    cnt = int(stats.get("cnt") or 0)
    label = _label(place, usage)
    if cnt == 0:
        return ProfileAnswer(
            intent="building_profile",
            answer=(
                f"{label}에 해당하는 건물을 찾지 못했습니다. "
                "동·구 이름이나 용도(아파트→공동주택 등)를 확인해 주세요."
            ),
            sql=sql,
            tables=["AL_D010_26_20250704"],
            rows=[],
        )

    lines = [
        f"{label} 기준으로 부산 GIS건물통합정보에서 {cnt:,}동을 집계했습니다.",
        "주요 특징은 다음과 같습니다.",
        (
            f"- 연면적: 평균 {_fmt(stats.get('avg_area'))}㎡"
            f" (중앙값 {_fmt(stats.get('med_area'))}㎡,"
            f" 최소 {_fmt(stats.get('min_area'))}㎡,"
            f" 최대 {_fmt(stats.get('max_area'))}㎡)"
        ),
        (
            f"- 높이: 평균 {_fmt(stats.get('avg_height'))}m"
            f" (최고 {_fmt(stats.get('max_height'))}m)"
        ),
        (
            f"- 지상층: 평균 {_fmt(stats.get('avg_floors'))}층"
            f" (최고 {_fmt(stats.get('max_floors'))}층)"
        ),
        f"- 건축면적: 평균 {_fmt(stats.get('avg_bldg_area'))}㎡",
    ]
    if structures:
        struct_txt = ", ".join(
            f"{s['structure'] or '미상'} {int(s['n']):,}동" for s in structures
        )
        lines.append(f"- 주요 구조: {struct_txt}")
    if usages:
        usage_txt = ", ".join(
            f"{u['usage']} {int(u['n']):,}동" for u in usages
        )
        lines.append(f"- 용도 구성(상위): {usage_txt}")
    if usage == "공동주택" and "아파트" in q:
        lines.append("참고: 질문의 ‘아파트’는 속성상 건축물용도명 ‘공동주택’으로 집계했습니다.")

    return ProfileAnswer(
        intent="building_profile",
        answer="\n".join(lines),
        sql=sql,
        tables=["AL_D010_26_20250704"],
        rows=[stats, *structures, *usages],
    )


def _extract_place(q: str) -> str | None:
    m = _DONG.search(q)
    if m:
        return m.group(1)
    m = _GU.search(q)
    if m:
        return m.group(1)
    return None


def _extract_usage(q: str) -> str | None:
    # 긴 별칭 우선
    for alias in sorted(_USAGE_ALIASES, key=len, reverse=True):
        if alias in q:
            return _USAGE_ALIASES[alias]
    return None


def _label(place: str | None, usage: str | None) -> str:
    parts: list[str] = []
    if place:
        parts.append(place)
    if usage:
        parts.append(usage)
    return " ".join(parts) if parts else "선택 조건"


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, float):
        if value.is_integer():
            return f"{int(value):,}"
        return f"{value:,.1f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)
