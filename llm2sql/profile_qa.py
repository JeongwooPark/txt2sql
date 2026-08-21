"""장소·용도 기반 건물 특징 요약(집계) 답변."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row

from llm2sql.answer import emit_text_chunks, narrate_building_profile
from llm2sql.domain import (
    USAGE_ALIASES,
    d198_table_for_gu,
    extract_gu,
    extract_place,
    extract_places,
    extract_usage,
    extract_usages,
    fix_dual_particles,
    is_busan_wide,
    place_a4_predicate,
    with_topic,
)
from llm2sql.progress import TokenCallback
from llm2sql.spatial_templates import admin_dong_where
from llm2sql.gazetteer import uses_admin_boundary

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
    "비교",
    "대비",
    "차이",
    "분석",
)

_FAR_HINTS = ("용적율", "용적률", "건폐율", "건폐률")
_INDUSTRIAL_INSIDE_HINTS = ("내", "안", "속한", "내부", "안쪽", "포함")


def _mentions_industrial_inside(question: str) -> bool:
    q = question.strip()
    if "산업단지" not in q:
        return False
    return any(k in q for k in _INDUSTRIAL_INSIDE_HINTS)


def _wants_far_focus(question: str) -> bool:
    return any(k in question for k in _FAR_HINTS)


def _wants_industrial_compare(question: str) -> bool:
    """같은 지역 전체 vs 산업단지 내 건물 특성 비교."""
    q = question.strip()
    if not _mentions_industrial_inside(q):
        return False
    return any(k in q for k in ("와", "과", "비교", "대비", "차이", "vs", "VS"))


def _far_select_exprs(prefix: str = "") -> str:
    """용적율(연면적/대지면적)·건폐율(건축면적/대지면적) 집계 조각."""
    a12 = f'{prefix}"A12"'
    a14 = f'{prefix}"A14"'
    a15 = f'{prefix}"A15"'
    far = f"(({a14})::numeric / ({a15})) * 100"
    bcr = f"(({a12})::numeric / ({a15})) * 100"
    far_ok = f"({a15}) > 10 AND ({a14}) > 0 AND {far} BETWEEN 1 AND 1500"
    bcr_ok = f"({a15}) > 10 AND ({a12}) > 0 AND {bcr} BETWEEN 0.1 AND 100"
    return f"""
  ROUND(AVG(CASE WHEN {far_ok} THEN {far} END)::numeric, 1) AS avg_far,
  ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {far}) FILTER (
    WHERE {far_ok}
  )::numeric, 1) AS med_far,
  ROUND(MAX(CASE WHEN {far_ok} THEN {far} END)::numeric, 1) AS max_far,
  COUNT(*) FILTER (WHERE {far_ok}) AS far_n,
  ROUND(AVG(CASE WHEN {bcr_ok} THEN {bcr} END)::numeric, 1) AS avg_bcr,
  ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {bcr}) FILTER (
    WHERE {bcr_ok}
  )::numeric, 1) AS med_bcr
""".strip()


@dataclass(frozen=True)
class ProfileAnswer:
    intent: str
    answer: str
    sql: str
    tables: list[str]
    rows: list[dict[str, Any]]


def is_usage_overview_question(question: str) -> bool:
    """지역 건물의 주요/상위 용도 구성 설명 질의."""
    q = question.strip()
    if not q or "용도" not in q:
        return False
    if any(k in q for k in ("컬럼", "칼럼", "속성", "필드", "스키마", "테이블명")):
        return False
    # 종류/건수 카운트는 intent_router 경로
    if any(
        k in q
        for k in ("몇 가지", "몇가지", "몇개", "몇 개", "건수", "개수", "채수")
    ):
        if not any(k in q for k in ("설명", "구성", "분포", "어떤")):
            return False
    if "몇" in q and not any(k in q for k in ("설명", "구성", "분포", "주요", "어떤")):
        return False
    # 특정 용도 건수·목록은 라우터/다른 경로
    if extract_usage(q) and any(
        k in q for k in ("몇", "건수", "개수", "채수", "목록", "어디", "위치")
    ):
        return False
    explainish = any(
        k in q
        for k in (
            "설명",
            "주요",
            "어떤",
            "알려",
            "보여",
            "구성",
            "분포",
            "종류",
            "무엇",
            "뭐야",
            "뭐가",
        )
    )
    if not explainish:
        return False
    if extract_place(q) or extract_gu(q):
        return True
    return any(k in q for k in ("건물", "건축물", "주택", "아파트"))


def answer_usage_overview_question(
    conn: psycopg.Connection,
    question: str,
    *,
    model: str | None = None,
    host: str | None = None,
    client: Any | None = None,
    on_token: TokenCallback | None = None,
    force: bool = False,
) -> ProfileAnswer | None:
    if not force and not is_usage_overview_question(question):
        return None

    q = question.strip()
    place = extract_place(q) or extract_gu(q)
    if not place:
        return None

    gu = extract_gu(q)
    # 동래/금정 + 주요 용도 → D198 A25, 그 외 → D010 A9
    use_major = any(k in q for k in ("주요용도", "주요 용도", "주요용도명"))
    d198 = d198_table_for_gu(gu) if use_major else None

    if d198:
        table = d198
        usage_col = "A25"
        field_label = "주요용도명"
        where_sql = place_a4_predicate(place)
    else:
        table = "AL_D010_26_20250704"
        usage_col = "A9"
        field_label = "건축물용도명"
        where_sql = place_a4_predicate(place)

    sql = f"""
SELECT COALESCE("{usage_col}", '(미상)') AS usage, COUNT(*) AS n
FROM "{table}"
WHERE {where_sql} AND "{usage_col}" IS NOT NULL
GROUP BY 1
ORDER BY 2 DESC
LIMIT 10
""".strip()
    count_sql = f"""
SELECT COUNT(*) AS cnt, COUNT(DISTINCT "{usage_col}") AS kinds
FROM "{table}"
WHERE {where_sql} AND "{usage_col}" IS NOT NULL
""".strip()

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(count_sql)
        totals = cur.fetchone() or {}
        cur.execute(sql)
        usages_rows = list(cur.fetchall())

    total = int(totals.get("cnt") or 0)
    kinds = int(totals.get("kinds") or 0)
    label = place
    if total == 0 or not usages_rows:
        answer = (
            f"{label}에서 {field_label} 기준 건물 용도 자료를 찾지 못했습니다. "
            "지역명이나 데이터 범위를 확인해 주세요."
        )
        emit_text_chunks(answer, on_token)
        return ProfileAnswer(
            intent="usage_overview",
            answer=answer,
            sql=f"{count_sql};\n{sql}",
            tables=[table],
            rows=[],
        )

    top = [
        {
            "name": u.get("usage") or "미상",
            "count": int(u.get("n") or 0),
            "share_pct": round(100.0 * int(u.get("n") or 0) / total, 1),
        }
        for u in usages_rows
    ]
    payload = {
        "scope": label,
        "focus": "usage_overview",
        "usage_field": field_label,
        "building_count": total,
        "distinct_usage_count": kinds,
        "top_usages": top,
    }
    fallback = _prose_usage_overview(label, field_label, total, kinds, top)
    answer = _finalize_profile_answer(
        q,
        payload=payload,
        fallback=fallback,
        model=model,
        host=host,
        client=client,
        on_token=on_token,
    )
    return ProfileAnswer(
        intent="usage_overview",
        answer=answer,
        sql=f"{count_sql};\n{sql}",
        tables=[table],
        rows=[{"cnt": total, "kinds": kinds}, *usages_rows],
    )


def _prose_usage_overview(
    label: str,
    field_label: str,
    total: int,
    kinds: int,
    top: list[dict[str, Any]],
) -> str:
    parts = [
        f"{label} 건물을 {field_label} 기준으로 보면 "
        f"약 {total:,}동·{kinds}가지 용도가 확인됩니다."
    ]
    if top:
        lead = top[0]
        parts.append(
            f"가장 많은 용도는 {lead['name']}로 "
            f"{lead['count']:,}동(약 {lead['share_pct']}%)입니다."
        )
        if len(top) > 1:
            rest = ", ".join(
                f"{u['name']} {u['count']:,}동({u['share_pct']}%)" for u in top[1:5]
            )
            parts.append(f"이어서 {rest} 순으로 나타납니다.")
    parts.append(
        "위 비율은 해당 지역 건물 도형 건수를 기준으로 한 상위 용도 구성입니다."
    )
    return " ".join(parts)


def _wants_citywide_compare(question: str) -> bool:
    """부산시 전역(시 전체)과 특정 지역을 대비하는지."""
    q = question.strip()
    has_city = is_busan_wide(q) or any(
        k in q
        for k in (
            "전역",
            "시 전체",
            "시전체",
            "시 평균",
            "시평균",
            "부산 평균",
            "전체 평균",
        )
    )
    has_vs = any(k in q for k in ("대비", "비교", "차이", "보다", "비해"))
    return has_city and has_vs


def is_profile_question(question: str) -> bool:
    q = question.strip()
    if not q:
        return False
    # 용도 구성 설명은 전용 경로
    if is_usage_overview_question(q):
        return False
    # 특정 데이터셋 요약/설명은 프로필이 아님
    from llm2sql.meta_qa import _asks_dataset_summary, _named_dataset_question

    if _named_dataset_question(q) and (
        _asks_dataset_summary(q)
        or any(k in q for k in ("들어있는", "내용", "설명", "컬럼", "속성"))
    ):
        return False
    # 최고 높이/면적 건물 비교는 프로필 집계가 아님
    from llm2sql.rank_compare_qa import is_rank_compare_question

    if is_rank_compare_question(q):
        return False
    # 법정동→행정동 비율 질의는 공간 분배 라우트
    if any(k in q for k in ("몇%", "몇 %", "퍼센트씩", "몇 퍼센트", "%씩", "몇 프로")):
        return False
    if "행정동" in q and any(
        k in q for k in ("무엇", "목록", "내에", "안에", "구성")
    ):
        if not any(k in q for k in ("특징", "비교", "퍼센트", "건물", "아파트")):
            return False

    summary_hints = (
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
        "분석",
    )
    compare_hints = ("비교", "대비", "차이")
    has_summary = any(k in q for k in summary_hints) or _wants_far_focus(q)
    has_compare = any(k in q for k in compare_hints) or ("와" in q) or ("과" in q)
    if not has_summary and not has_compare:
        return False
    places = extract_places(q)
    usages = extract_usages(q)
    # '비교'만 있고 요약 의도가 없으면, 복수 장소/용도·시 전역·산업단지 대비일 때만
    if has_compare and not has_summary:
        if len(places) < 2 and len(usages) < 2:
            if not (_wants_citywide_compare(q) and places):
                if not (_wants_industrial_compare(q) and (places or extract_gu(q))):
                    return False
    if extract_places(q) or extract_gu(q):
        return True
    if any(k in q for k in USAGE_ALIASES):
        return True
    if "건물" in q or "건축물" in q or "아파트" in q:
        return True
    return False


def answer_profile_question(
    conn: psycopg.Connection,
    question: str,
    *,
    model: str | None = None,
    host: str | None = None,
    client: Any | None = None,
    on_token: TokenCallback | None = None,
    force: bool = False,
) -> ProfileAnswer | None:
    if not force and not is_profile_question(question):
        return None

    q = question.strip()
    place = extract_place(q)
    gu_name = extract_gu(q)
    if place:
        from llm2sql.gazetteer import is_locality

        if is_locality(place):
            from llm2sql.clarify_qa import _lookup_admin_dong, _lookup_places

            found = _lookup_places(conn, place, gu=gu_name)
            if not found:
                admin = _lookup_admin_dong(conn, place)
                # '%하동%'이 '하단동'에 걸리는 부분일치 오탐 제외
                if admin != place:
                    return None

    places = extract_places(q)
    usages = extract_usages(q)
    wants_compare = any(
        k in q for k in ("비교", "대비", "차이", "와 ", "과 ", "vs", "VS")
    ) or ("와" in q) or ("과" in q)
    far_focus = _wants_far_focus(q)

    if not places and not usages and not _mentions_industrial_inside(q):
        return None

    # 부산시 전역 대비 단일 지역 (예: 부산시 전역 대비 구서동 특성)
    if _wants_citywide_compare(q) and places:
        place = places[0]
        usage = usages[0] if usages else None
        return _answer_compare_groups(
            conn,
            q,
            groups_spec=[
                {
                    "place": place,
                    "usage": usage,
                    "label": _label(place, usage, q),
                },
                {
                    "place": None,
                    "usage": usage,
                    "label": "부산시 전역",
                },
            ],
            scope=f"{_label(place, usage, q)} · 부산시 전역",
            compare_kind="place",
            far_focus=far_focus,
            model=model,
            host=host,
            client=client,
            on_token=on_token,
        )

    # 지역 전체 vs 같은 지역 산업단지 내 (예: 사상구 아파트 vs 사상구 산업단지 내 아파트)
    if _wants_industrial_compare(q):
        place = places[0] if places else extract_gu(q) or extract_place(q)
        usage = usages[0] if usages else extract_usage(q)
        if place or usage:
            base_label = _label(place, usage, q)
            ind_label = _industrial_label(place, usage, q)
            return _answer_compare_groups(
                conn,
                q,
                groups_spec=[
                    {
                        "place": place,
                        "usage": usage,
                        "in_industrial": False,
                        "label": base_label,
                    },
                    {
                        "place": place,
                        "usage": usage,
                        "in_industrial": True,
                        "label": ind_label,
                    },
                ],
                scope=f"{base_label} · {ind_label}",
                compare_kind="industrial",
                far_focus=far_focus,
                model=model,
                host=host,
                client=client,
                on_token=on_token,
            )

    # 지역 간 비교 (구서동 vs 연산동)
    if len(places) >= 2:
        usage = usages[0] if usages else None
        return _answer_compare_groups(
            conn,
            q,
            groups_spec=[
                {"place": p, "usage": usage, "label": _label(p, usage, q)}
                for p in places[:3]
            ],
            scope=" · ".join(places[:3]),
            compare_kind="place",
            far_focus=far_focus,
            model=model,
            host=host,
            client=client,
            on_token=on_token,
        )

    # 같은 지역에서 용도 비교
    if wants_compare and len(usages) >= 2:
        place = places[0] if places else extract_place(q)
        return _answer_compare_groups(
            conn,
            q,
            groups_spec=[
                {
                    "place": place,
                    "usage": u,
                    "label": _label(place, u, q),
                }
                for u in usages[:3]
            ],
            scope=place or "선택 지역",
            compare_kind="usage",
            far_focus=far_focus,
            model=model,
            host=host,
            client=client,
            on_token=on_token,
        )

    place = places[0] if places else extract_place(q) or extract_gu(q)
    usage = usages[0] if usages else extract_usage(q)
    in_industrial = _mentions_industrial_inside(q)
    return _answer_single(
        conn,
        q,
        place,
        usage,
        in_industrial=in_industrial,
        far_focus=far_focus,
        model=model,
        host=host,
        client=client,
        on_token=on_token,
    )


def _use_admin_boundary(place: str | None) -> bool:
    """행정동 전용 명칭은 A4(법정동)가 아니라 경계 교차로 집계한다."""
    return uses_admin_boundary(place)


def _profile_from_where(
    *,
    place: str | None,
    usage: str | None,
    in_industrial: bool = False,
) -> tuple[str, str, str, bool]:
    """(컬럼 prefix, FROM, WHERE, 행정동경계 사용)."""
    admin = _use_admin_boundary(place)
    alias = admin or in_industrial
    prefix = "b." if alias else ""
    if admin:
        from_sql = (
            '"AL_D010_26_20250704" b\n'
            'JOIN "BND_ADM_DONG_PG" d\n'
            "  ON ST_Intersects(b.geometry, d.geometry)"
        )
        where = [admin_dong_where(str(place))]
    else:
        from_sql = (
            '"AL_D010_26_20250704" b' if alias else '"AL_D010_26_20250704"'
        )
        where: list[str] = []
        if place:
            pred = place_a4_predicate(place)
            if alias:
                pred = pred.replace('"A4"', 'b."A4"')
            where.append(pred)
    if usage:
        where.append(f'{prefix}"A9" = \'{usage}\'')
    if in_industrial:
        where.append(
            "EXISTS ("
            'SELECT 1 FROM "AL_D060_00_20250804" i '
            "WHERE ST_Intersects(b.geometry, i.geometry)"
            ")"
        )
    where_sql = " AND ".join(where) if where else "TRUE"
    return prefix, from_sql, where_sql, admin


def _stats_sql(where_sql: str, *, prefix: str = "", from_sql: str) -> str:
    far_exprs = _far_select_exprs(prefix)
    a12 = f'{prefix}"A12"'
    a14 = f'{prefix}"A14"'
    a16 = f'{prefix}"A16"'
    a26 = f'{prefix}"A26"'
    return f"""
SELECT
  COUNT(*) AS cnt,
  ROUND(AVG({a14})::numeric, 1) AS avg_area,
  ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {a14})::numeric, 1) AS med_area,
  ROUND(MIN({a14})::numeric, 1) AS min_area,
  ROUND(MAX({a14})::numeric, 1) AS max_area,
  ROUND(AVG({a16}) FILTER (WHERE {a16} > 0 AND {a16} <= 600)::numeric, 1) AS avg_height,
  ROUND(MAX({a16}) FILTER (WHERE {a16} > 0 AND {a16} <= 600)::numeric, 1) AS max_height,
  ROUND(AVG({a26})::numeric, 1) AS avg_floors,
  ROUND(MAX({a26})::numeric, 0) AS max_floors,
  ROUND(AVG({a12}) FILTER (
    WHERE {a12} > 0 AND {a12} <= 500000
      AND ({a14} IS NULL OR {a14} <= 0 OR {a12} <= {a14} * 1.05 + 50)
  )::numeric, 1) AS avg_bldg_area,
  {far_exprs}
FROM {from_sql}
WHERE {where_sql}
""".strip()


def _fetch_profile(
    conn: psycopg.Connection,
    *,
    place: str | None,
    usage: str | None,
    in_industrial: bool = False,
) -> tuple[str, dict[str, Any], list[dict[str, Any]], str]:
    prefix, from_sql, where_sql, _admin = _profile_from_where(
        place=place, usage=usage, in_industrial=in_industrial
    )
    sql = _stats_sql(where_sql, prefix=prefix, from_sql=from_sql)
    struct_col = f'{prefix}"A11"'
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql)
        stats = cur.fetchone() or {}
        cur.execute(
            f"""
            SELECT {struct_col} AS structure, COUNT(*) AS n
            FROM {from_sql}
            WHERE {where_sql}
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT 3
            """
        )
        structures = list(cur.fetchall())
    return where_sql, stats, structures, sql


def _far_fields(stats: dict[str, Any]) -> dict[str, Any]:
    return {
        "avg_far_pct": _num(stats.get("avg_far")),
        "median_far_pct": _num(stats.get("med_far")),
        "max_far_pct": _num(stats.get("max_far")),
        "far_sample_count": int(stats.get("far_n") or 0),
        "avg_bcr_pct": _num(stats.get("avg_bcr")),
        "median_bcr_pct": _num(stats.get("med_bcr")),
        "far_note": (
            "용적율은 연면적÷대지면적×100, 건폐율은 건축면적÷대지면적×100으로 "
            "대지면적·면적이 유효한 건물만 집계했습니다."
        ),
    }


def _answer_single(
    conn: psycopg.Connection,
    q: str,
    place: str | None,
    usage: str | None,
    *,
    in_industrial: bool = False,
    far_focus: bool = False,
    model: str | None = None,
    host: str | None = None,
    client: Any | None = None,
    on_token: TokenCallback | None = None,
) -> ProfileAnswer:
    where_sql, stats, structures, sql = _fetch_profile(
        conn, place=place, usage=usage, in_industrial=in_industrial
    )
    prefix, from_sql, where_sql, admin = _profile_from_where(
        place=place, usage=usage, in_industrial=in_industrial
    )
    usages_rows: list[dict[str, Any]] = []
    if not usage:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT COALESCE({prefix}"A9", '(미상)') AS usage, COUNT(*) AS n
                FROM {from_sql}
                WHERE {where_sql}
                GROUP BY 1
                ORDER BY 2 DESC
                LIMIT 5
                """
            )
            usages_rows = list(cur.fetchall())

    cnt = int(stats.get("cnt") or 0)
    label = (
        _industrial_label(place, usage, q)
        if in_industrial
        else _label(place, usage, q)
    )
    tables = ["AL_D010_26_20250704"]
    if in_industrial:
        tables.append("AL_D060_00_20250804")
    if admin:
        tables.append("BND_ADM_DONG_PG")
    if cnt == 0:
        answer = (
            f"{label}에 해당하는 건물을 찾지 못했습니다. "
            "동·구 이름이나 용도(아파트→공동주택 등)를 확인해 주세요."
        )
        emit_text_chunks(answer, on_token)
        return ProfileAnswer(
            intent="building_profile",
            answer=answer,
            sql=sql,
            tables=tables,
            rows=[],
        )

    apartment_note = bool(usage == "공동주택" and "아파트" in q)
    payload = {
        "scope": label,
        "building_count": cnt,
        "avg_floor_area_m2": _num(stats.get("avg_area")),
        "median_floor_area_m2": _num(stats.get("med_area")),
        "min_floor_area_m2": _num(stats.get("min_area")),
        "max_floor_area_m2": _num(stats.get("max_area")),
        "avg_height_m": _num(stats.get("avg_height")),
        "max_height_m": _num(stats.get("max_height")),
        "avg_floors": _num(stats.get("avg_floors")),
        "max_floors": _num(stats.get("max_floors")),
        "avg_building_area_m2": _num(stats.get("avg_bldg_area")),
        "in_industrial": in_industrial,
        "far_focus": far_focus,
        **_far_fields(stats),
        "top_structures": [
            {"name": s.get("structure") or "미상", "count": int(s.get("n") or 0)}
            for s in structures
        ],
        "top_usages": [
            {"name": u.get("usage") or "미상", "count": int(u.get("n") or 0)}
            for u in usages_rows
        ],
        "apartment_note": apartment_note,
    }
    answer = _finalize_profile_answer(
        q,
        payload=payload,
        fallback=_prose_single(
            label,
            stats,
            structures,
            usages_rows,
            apartment_note,
            far_focus=far_focus,
            in_industrial=in_industrial,
        ),
        model=model,
        host=host,
        client=client,
        on_token=on_token,
    )
    return ProfileAnswer(
        intent="building_profile",
        answer=answer,
        sql=sql,
        tables=tables,
        rows=[stats, *structures, *usages_rows],
    )


def _answer_compare_groups(
    conn: psycopg.Connection,
    q: str,
    *,
    groups_spec: list[dict[str, Any]],
    scope: str,
    compare_kind: str,
    far_focus: bool = False,
    model: str | None = None,
    host: str | None = None,
    client: Any | None = None,
    on_token: TokenCallback | None = None,
) -> ProfileAnswer:
    sqls: list[str] = []
    all_rows: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    any_industrial = False
    any_admin = False

    for spec in groups_spec:
        place = spec.get("place")
        usage = spec.get("usage")
        in_industrial = bool(spec.get("in_industrial"))
        any_industrial = any_industrial or in_industrial
        admin = _use_admin_boundary(place)
        any_admin = any_admin or admin
        place_basis = "행정동 경계" if admin else "법정동 주소"
        label = spec.get("label") or (
            _industrial_label(place, usage, q)
            if in_industrial
            else _label(place, usage, q)
        )
        _, stats, structures, sql = _fetch_profile(
            conn,
            place=place,
            usage=usage,
            in_industrial=in_industrial,
        )
        sqls.append(sql)
        all_rows.append(
            {
                "place": place,
                "usage": usage,
                "label": label,
                "in_industrial": in_industrial,
                "place_basis": place_basis,
                **stats,
            }
        )
        groups.append(
            {
                "label": label,
                "place": place,
                "usage": usage,
                "in_industrial": in_industrial,
                "place_basis": place_basis,
                "building_count": int(stats.get("cnt") or 0),
                "avg_floor_area_m2": _num(stats.get("avg_area")),
                "median_floor_area_m2": _num(stats.get("med_area")),
                "avg_height_m": _num(stats.get("avg_height")),
                "max_height_m": _num(stats.get("max_height")),
                "avg_floors": _num(stats.get("avg_floors")),
                "max_floors": _num(stats.get("max_floors")),
                "avg_building_area_m2": _num(stats.get("avg_bldg_area")),
                **_far_fields(stats),
                "top_structures": [
                    {
                        "name": s.get("structure") or "미상",
                        "count": int(s.get("n") or 0),
                    }
                    for s in structures
                ],
            }
        )

    payload = {
        "scope": scope,
        "compare": True,
        "compare_kind": compare_kind,
        "far_focus": far_focus,
        "groups": groups,
        "apartment_note": "아파트" in q
        and any(g.get("usage") == "공동주택" for g in groups),
    }
    answer = _finalize_profile_answer(
        q,
        payload=payload,
        fallback=_prose_compare(
            scope, groups, q, compare_kind=compare_kind, far_focus=far_focus
        ),
        model=model,
        host=host,
        client=client,
        on_token=on_token,
    )
    tables = ["AL_D010_26_20250704"]
    if any_industrial:
        tables.append("AL_D060_00_20250804")
    if any_admin:
        tables.append("BND_ADM_DONG_PG")
    return ProfileAnswer(
        intent="building_profile_compare",
        answer=answer,
        sql="\n;\n".join(sqls),
        tables=tables,
        rows=all_rows,
    )


def _finalize_profile_answer(
    question: str,
    *,
    payload: dict[str, Any],
    fallback: str,
    model: str | None,
    host: str | None,
    client: Any | None,
    on_token: TokenCallback | None,
) -> str:
    if model and (client is not None or host):
        try:
            answer = narrate_building_profile(
                question,
                payload=payload,
                model=model,
                host=host,
                client=client,
                on_token=on_token,
            )
            answer = fix_dual_particles(answer)
            if payload.get("apartment_note") and "공동주택" not in answer:
                extra = " 아파트는 공동주택 용도로 집계했습니다."
                answer = answer.rstrip() + extra
                if on_token is not None:
                    emit_text_chunks(extra, on_token)
            return answer
        except Exception:
            pass
    fixed = fix_dual_particles(fallback)
    emit_text_chunks(fixed, on_token)
    return fixed


def _prose_single(
    label: str,
    stats: dict[str, Any],
    structures: list[dict[str, Any]],
    usages_rows: list[dict[str, Any]],
    apartment_note: bool,
    *,
    far_focus: bool = False,
    in_industrial: bool = False,
) -> str:
    cnt = int(stats.get("cnt") or 0)
    parts = [
        f"{with_topic(label)} 부산 건물자료 기준으로 {cnt:,}동입니다.",
    ]
    if far_focus or stats.get("avg_far") is not None:
        far_n = int(stats.get("far_n") or 0)
        parts.append(
            f"용적율(연면적÷대지면적)은 평균 {_fmt(stats.get('avg_far'))}%"
            f"(중앙값 {_fmt(stats.get('med_far'))}%, "
            f"최고 {_fmt(stats.get('max_far'))}%, "
            f"유효표본 {far_n:,}동)이고, "
            f"건폐율 평균은 {_fmt(stats.get('avg_bcr'))}%입니다."
        )
    if not far_focus:
        parts.append(
            f"연면적은 평균 {_fmt(stats.get('avg_area'))}㎡, "
            f"중앙값 {_fmt(stats.get('med_area'))}㎡ 정도이며 "
            f"최소 {_fmt(stats.get('min_area'))}㎡에서 "
            f"최대 {_fmt(stats.get('max_area'))}㎡까지 분포합니다."
        )
        parts.append(
            f"높이는 평균 {_fmt(stats.get('avg_height'))}m"
            f"(최고 {_fmt(stats.get('max_height'))}m), "
            f"지상층은 평균 {_fmt(stats.get('avg_floors'))}층"
            f"(최고 {_fmt(stats.get('max_floors'))}층)이고, "
            f"건축면적 평균은 {_fmt(stats.get('avg_bldg_area'))}㎡입니다."
        )
    if structures and not far_focus:
        struct_txt = ", ".join(
            f"{s['structure'] or '미상'} {int(s['n']):,}동" for s in structures
        )
        parts.append(f"주요 구조는 {struct_txt}입니다.")
    if usages_rows:
        usage_txt = ", ".join(
            f"{u['usage']} {int(u['n']):,}동" for u in usages_rows
        )
        parts.append(f"용도 구성은 {usage_txt} 순입니다.")
    if in_industrial:
        parts.append("산업단지 경계와 교차하는 건물만 집계했습니다.")
    if apartment_note:
        parts.append(
            "참고로 질문의 아파트는 건축물용도명 공동주택으로 집계했습니다."
        )
    return " ".join(parts)


def _prose_compare(
    scope: str,
    groups: list[dict[str, Any]],
    q: str,
    *,
    compare_kind: str = "usage",
    far_focus: bool = False,
) -> str:
    citywide = any(str(g.get("label") or "") == "부산시 전역" for g in groups)
    if compare_kind == "industrial":
        parts = [
            f"{scope}의 용적율·건물 특성을 비교하면 다음과 같습니다."
            if far_focus
            else f"{scope}의 건물 특징을 비교하면 다음과 같습니다."
        ]
    elif citywide:
        parts = [f"{scope} 건물 특징을 비교하면 다음과 같습니다."]
    elif compare_kind == "place":
        parts = [f"{scope}의 건물 특징을 비교하면 다음과 같습니다."]
    else:
        parts = [f"{scope}에서 용도별 건물 특징을 비교하면 다음과 같습니다."]
    admins = [
        str(g.get("place"))
        for g in groups
        if _use_admin_boundary(g.get("place"))
    ]
    legals = [
        str(g.get("place"))
        for g in groups
        if g.get("place")
        and not _use_admin_boundary(g.get("place"))
        and str(g.get("label") or "") != "부산시 전역"
    ]
    if admins and legals:
        parts.append(
            f"{'·'.join(admins)}은 행정동 경계, "
            f"{'·'.join(legals)}은 법정동 주소 기준으로 집계했습니다."
        )
    for g in groups:
        cnt = int(g.get("building_count") or 0)
        label = g.get("label") or "해당 조건"
        if cnt == 0:
            parts.append(f"{with_topic(str(label))} 해당 건물을 찾지 못했습니다.")
            continue
        if far_focus:
            parts.append(
                f"{with_topic(str(label))} {cnt:,}동으로, "
                f"평균 용적율 {_fmt(g.get('avg_far_pct'))}%"
                f"(중앙값 {_fmt(g.get('median_far_pct'))}%, "
                f"유효 {_fmt(g.get('far_sample_count'))}동), "
                f"평균 건폐율 {_fmt(g.get('avg_bcr_pct'))}%입니다."
            )
        else:
            parts.append(
                f"{with_topic(str(label))} {cnt:,}동으로, "
                f"평균 연면적 {_fmt(g.get('avg_floor_area_m2'))}㎡, "
                f"평균 높이 {_fmt(g.get('avg_height_m'))}m, "
                f"평균 지상 {_fmt(g.get('avg_floors'))}층"
                + (
                    f", 평균 용적율 {_fmt(g.get('avg_far_pct'))}%"
                    if g.get("avg_far_pct") is not None
                    else ""
                )
                + "입니다."
            )
    valid = [g for g in groups if int(g.get("building_count") or 0) > 0]
    if len(valid) >= 2:
        a, b = valid[0], valid[1]
        a_name, b_name = a["label"], b["label"]
        if far_focus and (a.get("avg_far_pct") or 0) and (b.get("avg_far_pct") or 0):
            higher = (
                a_name
                if float(a["avg_far_pct"]) >= float(b["avg_far_pct"])
                else b_name
            )
            parts.append(
                f"평균 용적율은 {higher} 쪽이 더 높습니다 "
                f"({a_name} {_fmt(a.get('avg_far_pct'))}%, "
                f"{b_name} {_fmt(b.get('avg_far_pct'))}%)."
            )
        elif (a.get("avg_floor_area_m2") or 0) and (b.get("avg_floor_area_m2") or 0):
            bigger = (
                a_name
                if float(a["avg_floor_area_m2"]) >= float(b["avg_floor_area_m2"])
                else b_name
            )
            parts.append(f"평균 연면적은 {bigger} 쪽이 더 큽니다.")
        if (a.get("avg_height_m") or 0) and (b.get("avg_height_m") or 0) and not far_focus:
            taller = (
                a_name
                if float(a["avg_height_m"]) >= float(b["avg_height_m"])
                else b_name
            )
            parts.append(f"평균 높이는 {taller} 쪽이 더 높습니다.")
        if (a.get("building_count") or 0) and (b.get("building_count") or 0):
            more = (
                a_name
                if int(a["building_count"]) >= int(b["building_count"])
                else b_name
            )
            parts.append(
                f"동 수는 {more} 쪽이 더 많습니다 "
                f"({a_name} {int(a['building_count']):,}동, "
                f"{b_name} {int(b['building_count']):,}동)."
            )
            if citywide and a_name != "부산시 전역":
                share = (
                    100.0
                    * int(a["building_count"])
                    / max(int(b["building_count"]), 1)
                )
                parts.append(
                    f"{a_name} 건물 수는 부산시 전역의 약 {share:.1f}% 수준입니다."
                )
    if "아파트" in q:
        parts.append("아파트는 공동주택 용도로 집계했습니다.")
    if far_focus:
        parts.append(
            "용적율·건폐율은 대지면적과 면적이 유효한 건물만으로 계산했습니다."
        )
    return " ".join(parts)


def _label(place: str | None, usage: str | None, q: str) -> str:
    parts: list[str] = []
    if place:
        parts.append(place)
    if usage:
        if usage == "공동주택" and "아파트" in q:
            parts.append("아파트(공동주택)")
        else:
            parts.append(usage)
    return " ".join(parts) if parts else "선택 조건"


def _industrial_label(place: str | None, usage: str | None, q: str) -> str:
    base = _label(place, usage, q)
    if not base or base == "선택 조건":
        return "산업단지 내 건물"
    if "산업단지" in base:
        return base
    return f"{base} · 산업단지 내"


def _num(value: Any) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, float):
        return int(value) if value.is_integer() else round(value, 1)
    if isinstance(value, int):
        return value
    try:
        return float(value)
    except Exception:
        return None


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
