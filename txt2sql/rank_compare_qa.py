"""복수 지역 최고(순위) 건물 비교."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row

from txt2sql.answer import (
    _fmt_area,
    _fmt_number,
    _row_floors,
    _row_height,
    _row_usage,
    emit_text_chunks,
    narrate_building_profile,
)
from txt2sql.domain import (
    extract_places,
    extract_usage,
    place_a4_predicate,
    sane_floor_area_sql,
    sane_footprint_sql,
    sane_height_sql,
)
from txt2sql.progress import TokenCallback

_COMPARE_HINTS = ("비교", "대비", "차이", "와", "과", "vs", "VS")


@dataclass(frozen=True)
class RankCompareAnswer:
    intent: str
    answer: str
    sql: str
    tables: list[str]
    rows: list[dict[str, Any]]


def _detect_metric(question: str) -> tuple[str, str, str] | None:
    """(metric_col, metric_name, extra_where) or None."""
    q = question
    if any(k in q for k in ("최고 높", "가장 높", "제일 높")) or (
        "높이" in q and any(k in q for k in ("최고", "가장", "제일", "최대", "1등"))
    ):
        return "A16", "높이", sane_height_sql("A16", "A26")
    if any(k in q for k in ("건물면적", "건축물면적", "건축면적")) and any(
        k in q
        for k in (
            "가장 큰",
            "제일 큰",
            "가장 넓",
            "제일 넓",
            "최대",
            "최고",
            "1등",
        )
    ):
        return "A12", "건물면적", sane_footprint_sql("A12", "A14")
    if "연면적" in q and any(
        k in q
        for k in (
            "가장 큰",
            "제일 큰",
            "가장 넓",
            "제일 넓",
            "최대",
            "최고",
            "1등",
        )
    ):
        return "A14", "연면적", sane_floor_area_sql("A14")
    if any(k in q for k in ("지상층", "층수", "최고층")) and any(
        k in q for k in ("가장", "제일", "최대", "최고", "1등")
    ):
        return "A26", "지상층", '"A26" > 0'
    return None


def is_rank_compare_question(question: str) -> bool:
    q = question.strip()
    if len(extract_places(q)) < 2:
        return False
    if _detect_metric(q) is None:
        return False
    # 비교 표현이 있거나, 복수 장소 + 최고/가장 표현이면 비교로 본다
    if any(k in q for k in _COMPARE_HINTS):
        return True
    return any(k in q for k in ("최고", "가장", "제일", "최대", "1등"))


def answer_rank_compare(
    conn: psycopg.Connection,
    question: str,
    *,
    model: str | None = None,
    host: str | None = None,
    client: Any | None = None,
    on_token: TokenCallback | None = None,
) -> RankCompareAnswer | None:
    if not is_rank_compare_question(question):
        return None

    q = question.strip()
    places = extract_places(q)[:3]
    metric = _detect_metric(q)
    if metric is None:
        return None
    metric_col, metric_name, sane = metric
    usage = extract_usage(q)

    winners: list[dict[str, Any]] = []
    sqls: list[str] = []
    rows: list[dict[str, Any]] = []

    for place in places:
        where = [place_a4_predicate(place), sane]
        if usage:
            where.append(f'"A9" = \'{usage}\'')
        where_sql = " AND ".join(where)
        sql = (
            'SELECT "A0", "A4", "A5", "A9", "A12", "A14", "A15", "A16", '
            '"A19", "A24", "A25", "A26"\n'
            'FROM "AL_D010_26_20250704"\n'
            f"WHERE {where_sql}\n"
            f'ORDER BY "{metric_col}" DESC NULLS LAST\n'
            "LIMIT 1;"
        )
        sqls.append(sql)
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql)
            row = cur.fetchone()
        if not row:
            winners.append({"place": place, "found": False})
            continue
        rows.append(row)
        metric_val = row.get(metric_col)
        winners.append(
            {
                "place": place,
                "found": True,
                "name": row.get("A24"),
                "address": row.get("A4"),
                "jibeon": row.get("A5"),
                "usage": _row_usage(row),
                "building_area_m2": row.get("A12"),
                "floor_area_m2": row.get("A14"),
                "height_m": _row_height(row),
                "floors": _row_floors(row),
                "metric": metric_name,
                "metric_value": metric_val,
            }
        )

    payload = {
        "compare": True,
        "compare_kind": "top_building",
        "metric": metric_name,
        "usage": usage,
        "apartment_note": bool(usage == "공동주택" and "아파트" in q),
        "groups": winners,
    }
    fallback = _prose_rank_compare(q, metric_name, winners)
    answer = _finalize(
        q,
        payload=payload,
        fallback=fallback,
        model=model,
        host=host,
        client=client,
        on_token=on_token,
    )
    return RankCompareAnswer(
        intent=f"building_rank_compare_{metric_name}",
        answer=answer,
        sql="\n;\n".join(sqls),
        tables=["AL_D010_26_20250704"],
        rows=rows,
    )


def _finalize(
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


def _prose_rank_compare(
    question: str,
    metric_name: str,
    winners: list[dict[str, Any]],
) -> str:
    found = [w for w in winners if w.get("found")]
    if not found:
        places = ", ".join(str(w.get("place")) for w in winners)
        return f"{places}에서 조건에 맞는 건물을 찾지 못했습니다."

    unit = {"높이": "m", "건물면적": "㎡", "연면적": "㎡", "지상층": "층"}.get(
        metric_name, ""
    )
    parts: list[str] = []
    for w in winners:
        place = w.get("place")
        if not w.get("found"):
            parts.append(f"{place}에서는 해당 건물을 찾지 못했습니다.")
            continue
        name = w.get("name")
        name_s = (
            str(name)
            if name not in (None, "") and str(name).lower() != "nan"
            else None
        )
        who = f"「{name_s}」" if name_s else f"지번 {w.get('jibeon')} 건물"
        if metric_name == "높이":
            lead = f"{place}에서 가장 높은 건물은 {who}입니다"
        elif metric_name == "지상층":
            lead = f"{place}에서 지상층이 가장 많은 건물은 {who}입니다"
        else:
            lead = f"{place}에서 {metric_name}이 가장 큰 건물은 {who}입니다"
        metric_shown = f"{_fmt_number(w.get('metric_value'))}{unit}"
        if unit == "㎡":
            metric_shown = _fmt_area(w.get("metric_value"), question)
        parts.append(
            f"{lead}. {metric_name} {metric_shown}, "
            f"위치 {w.get('address')}, 용도 {w.get('usage') or '—'}, "
            f"연면적 {_fmt_area(w.get('floor_area_m2'), question)}, "
            f"높이 {_fmt_number(w.get('height_m'))}m, "
            f"지상 {_fmt_number(w.get('floors'))}층입니다."
        )

    if len(found) >= 2:
        a, b = found[0], found[1]
        try:
            av = float(a.get("metric_value") or 0)
            bv = float(b.get("metric_value") or 0)
        except Exception:
            av = bv = 0.0
        if av or bv:
            winner = a if av >= bv else b
            loser = b if av >= bv else a
            adj = "높습니다" if metric_name == "높이" else "큽니다"
            win_m = (
                _fmt_area(winner.get("metric_value"), question)
                if unit == "㎡"
                else f"{_fmt_number(winner.get('metric_value'))}{unit}"
            )
            lose_m = (
                _fmt_area(loser.get("metric_value"), question)
                if unit == "㎡"
                else f"{_fmt_number(loser.get('metric_value'))}{unit}"
            )
            parts.append(
                f"비교하면 {winner.get('place')} 쪽이 "
                f"{win_m}로 더 {adj} "
                f"({loser.get('place')} {lose_m})."
            )
    if "아파트" in question:
        parts.append("아파트는 공동주택 용도로 집계했습니다.")
    return " ".join(parts)
