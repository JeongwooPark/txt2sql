"""장소·용도 기반 건물 특징 요약(집계) 답변."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row

from llm2sql.answer import emit_text_chunks, narrate_building_profile
from llm2sql.domain import (
    DONG_RE,
    GU_RE,
    USAGE_ALIASES,
    extract_place,
    extract_places,
    extract_usage,
    extract_usages,
    place_a4_predicate,
)
from llm2sql.progress import TokenCallback

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
    # 최고 높이/면적 건물 비교는 프로필 집계가 아님
    from llm2sql.rank_compare_qa import is_rank_compare_question

    if is_rank_compare_question(q):
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
    )
    compare_hints = ("비교", "대비", "차이")
    has_summary = any(k in q for k in summary_hints)
    has_compare = any(k in q for k in compare_hints) or ("와" in q) or ("과" in q)
    if not has_summary and not has_compare:
        return False
    # '비교'만 있고 요약 의도가 없으면, 복수 장소/용도일 때만 프로필 비교
    if has_compare and not has_summary:
        places = extract_places(q)
        usages = extract_usages(q)
        if len(places) < 2 and len(usages) < 2:
            return False
    if DONG_RE.search(q) or GU_RE.search(q):
        return True
    if any(k in q for k in USAGE_ALIASES):
        return True
    if "건물" in q or "건축물" in q:
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
) -> ProfileAnswer | None:
    if not is_profile_question(question):
        return None

    q = question.strip()
    places = extract_places(q)
    usages = extract_usages(q)
    wants_compare = any(
        k in q for k in ("비교", "대비", "차이", "와 ", "과 ", "vs", "VS")
    ) or ("와" in q) or ("과" in q)

    if not places and not usages:
        return None

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
            model=model,
            host=host,
            client=client,
            on_token=on_token,
        )

    place = places[0] if places else extract_place(q)
    usage = usages[0] if usages else extract_usage(q)
    return _answer_single(
        conn,
        q,
        place,
        usage,
        model=model,
        host=host,
        client=client,
        on_token=on_token,
    )


def _stats_sql(where_sql: str) -> str:
    return f"""
SELECT
  COUNT(*) AS cnt,
  ROUND(AVG("A14")::numeric, 1) AS avg_area,
  ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY "A14")::numeric, 1) AS med_area,
  ROUND(MIN("A14")::numeric, 1) AS min_area,
  ROUND(MAX("A14")::numeric, 1) AS max_area,
  ROUND(AVG("A16") FILTER (WHERE "A16" > 0 AND "A16" <= 600)::numeric, 1) AS avg_height,
  ROUND(MAX("A16") FILTER (WHERE "A16" > 0 AND "A16" <= 600)::numeric, 1) AS max_height,
  ROUND(AVG("A26")::numeric, 1) AS avg_floors,
  ROUND(MAX("A26")::numeric, 0) AS max_floors,
  ROUND(AVG("A12") FILTER (
    WHERE "A12" > 0 AND "A12" <= 500000
      AND ("A14" IS NULL OR "A14" <= 0 OR "A12" <= "A14" * 1.05 + 50)
  )::numeric, 1) AS avg_bldg_area
FROM "AL_D010_26_20250704"
WHERE {where_sql}
""".strip()


def _fetch_profile(
    conn: psycopg.Connection,
    *,
    place: str | None,
    usage: str | None,
) -> tuple[str, dict[str, Any], list[dict[str, Any]], str]:
    where: list[str] = []
    if place:
        where.append(place_a4_predicate(place))
    if usage:
        where.append(f'"A9" = \'{usage}\'')
    where_sql = " AND ".join(where) if where else "TRUE"
    sql = _stats_sql(where_sql)

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
    return where_sql, stats, structures, sql


def _answer_single(
    conn: psycopg.Connection,
    q: str,
    place: str | None,
    usage: str | None,
    *,
    model: str | None = None,
    host: str | None = None,
    client: Any | None = None,
    on_token: TokenCallback | None = None,
) -> ProfileAnswer:
    where_sql, stats, structures, sql = _fetch_profile(
        conn, place=place, usage=usage
    )
    usages_rows: list[dict[str, Any]] = []
    if not usage:
        with conn.cursor(row_factory=dict_row) as cur:
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
            usages_rows = list(cur.fetchall())

    cnt = int(stats.get("cnt") or 0)
    label = _label(place, usage, q)
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
            tables=["AL_D010_26_20250704"],
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
        fallback=_prose_single(label, stats, structures, usages_rows, apartment_note),
        model=model,
        host=host,
        client=client,
        on_token=on_token,
    )
    return ProfileAnswer(
        intent="building_profile",
        answer=answer,
        sql=sql,
        tables=["AL_D010_26_20250704"],
        rows=[stats, *structures, *usages_rows],
    )


def _answer_compare_groups(
    conn: psycopg.Connection,
    q: str,
    *,
    groups_spec: list[dict[str, Any]],
    scope: str,
    compare_kind: str,
    model: str | None = None,
    host: str | None = None,
    client: Any | None = None,
    on_token: TokenCallback | None = None,
) -> ProfileAnswer:
    sqls: list[str] = []
    all_rows: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []

    for spec in groups_spec:
        place = spec.get("place")
        usage = spec.get("usage")
        label = spec.get("label") or _label(place, usage, q)
        _, stats, structures, sql = _fetch_profile(
            conn, place=place, usage=usage
        )
        sqls.append(sql)
        all_rows.append(
            {"place": place, "usage": usage, "label": label, **stats}
        )
        groups.append(
            {
                "label": label,
                "place": place,
                "usage": usage,
                "building_count": int(stats.get("cnt") or 0),
                "avg_floor_area_m2": _num(stats.get("avg_area")),
                "median_floor_area_m2": _num(stats.get("med_area")),
                "avg_height_m": _num(stats.get("avg_height")),
                "max_height_m": _num(stats.get("max_height")),
                "avg_floors": _num(stats.get("avg_floors")),
                "max_floors": _num(stats.get("max_floors")),
                "avg_building_area_m2": _num(stats.get("avg_bldg_area")),
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
        "groups": groups,
        "apartment_note": "아파트" in q
        and any(g.get("usage") == "공동주택" for g in groups),
    }
    answer = _finalize_profile_answer(
        q,
        payload=payload,
        fallback=_prose_compare(scope, groups, q, compare_kind=compare_kind),
        model=model,
        host=host,
        client=client,
        on_token=on_token,
    )
    return ProfileAnswer(
        intent="building_profile_compare",
        answer=answer,
        sql="\n;\n".join(sqls),
        tables=["AL_D010_26_20250704"],
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
            return narrate_building_profile(
                question,
                payload=payload,
                model=model,
                host=host,
                client=client,
                on_token=on_token,
            )
        except Exception:
            pass
    emit_text_chunks(fallback, on_token)
    return fallback


def _prose_single(
    label: str,
    stats: dict[str, Any],
    structures: list[dict[str, Any]],
    usages_rows: list[dict[str, Any]],
    apartment_note: bool,
) -> str:
    cnt = int(stats.get("cnt") or 0)
    parts = [
        f"{label}는 부산 건물자료 기준으로 {cnt:,}동입니다.",
        (
            f"연면적은 평균 {_fmt(stats.get('avg_area'))}㎡, "
            f"중앙값 {_fmt(stats.get('med_area'))}㎡ 정도이며 "
            f"최소 {_fmt(stats.get('min_area'))}㎡에서 "
            f"최대 {_fmt(stats.get('max_area'))}㎡까지 분포합니다."
        ),
        (
            f"높이는 평균 {_fmt(stats.get('avg_height'))}m"
            f"(최고 {_fmt(stats.get('max_height'))}m), "
            f"지상층은 평균 {_fmt(stats.get('avg_floors'))}층"
            f"(최고 {_fmt(stats.get('max_floors'))}층)이고, "
            f"건축면적 평균은 {_fmt(stats.get('avg_bldg_area'))}㎡입니다."
        ),
    ]
    if structures:
        struct_txt = ", ".join(
            f"{s['structure'] or '미상'} {int(s['n']):,}동" for s in structures
        )
        parts.append(f"주요 구조는 {struct_txt}입니다.")
    if usages_rows:
        usage_txt = ", ".join(
            f"{u['usage']} {int(u['n']):,}동" for u in usages_rows
        )
        parts.append(f"용도 구성은 {usage_txt} 순입니다.")
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
) -> str:
    if compare_kind == "place":
        parts = [f"{scope}의 건물 특징을 비교하면 다음과 같습니다."]
    else:
        parts = [f"{scope}에서 용도별 건물 특징을 비교하면 다음과 같습니다."]
    for g in groups:
        cnt = int(g.get("building_count") or 0)
        label = g.get("label") or "해당 조건"
        if cnt == 0:
            parts.append(f"{label}은(는) 해당 건물을 찾지 못했습니다.")
            continue
        parts.append(
            f"{label}은(는) {cnt:,}동으로, "
            f"평균 연면적 {_fmt(g.get('avg_floor_area_m2'))}㎡, "
            f"평균 높이 {_fmt(g.get('avg_height_m'))}m, "
            f"평균 지상 {_fmt(g.get('avg_floors'))}층입니다."
        )
    valid = [g for g in groups if int(g.get("building_count") or 0) > 0]
    if len(valid) >= 2:
        a, b = valid[0], valid[1]
        a_name, b_name = a["label"], b["label"]
        if (a.get("avg_floor_area_m2") or 0) and (b.get("avg_floor_area_m2") or 0):
            bigger = (
                a_name
                if float(a["avg_floor_area_m2"]) >= float(b["avg_floor_area_m2"])
                else b_name
            )
            parts.append(f"평균 연면적은 {bigger} 쪽이 더 큽니다.")
        if (a.get("avg_height_m") or 0) and (b.get("avg_height_m") or 0):
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
    if "아파트" in q:
        parts.append("아파트는 공동주택 용도로 집계했습니다.")
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
