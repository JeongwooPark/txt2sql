"""SQP 경로 한국어 답변. 단순 count/list/rank/distribution은 템플릿만 사용한다."""

from __future__ import annotations

from typing import Any

from txt2sql.semantic_plan.models import SemanticQueryPlan
from txt2sql.units import sql_number


def format_semantic_answer(
    question: str,
    *,
    plan: SemanticQueryPlan,
    rows: list[dict[str, Any]],
    row_count: int,
) -> str:
    place = ""
    if plan.scope and plan.scope.place and plan.scope.place.name:
        place = plan.scope.place.name
    prefix = f"{place}의 " if place else ""

    if row_count == 0:
        return f"{prefix}조건에 해당하는 건물을 찾지 못했습니다."

    from txt2sql.domain import wants_map_display
    from txt2sql.answer import format_map_display_answer

    if wants_map_display(question):
        return format_map_display_answer(question, rows=rows, include_map=True)

    if plan.query_kind == "count":
        value = _first_number(rows, ("count", "n", "cnt"))
        shown = f"{int(value):,}" if value is not None else str(row_count)
        return f"{prefix}조건에 해당하는 건물은 {shown}건입니다."

    if plan.query_kind == "aggregate":
        parts: list[str] = []
        row = rows[0]
        for key, val in row.items():
            if val is None:
                continue
            parts.append(f"{_label(key)} { _fmt(val)}")
        if parts:
            return f"{prefix}집계 결과입니다. " + ", ".join(parts) + "."
        return f"{prefix}집계 결과를 조회했습니다."

    if plan.query_kind == "distribution":
        lines = [f"{prefix}분포를 조회했습니다."]
        for i, row in enumerate(rows[:12], start=1):
            name = _first_text(row, ("usage", "legal_dong", "structure", "ground_floors"))
            n = _first_number(row, ("n", "count", "cnt"))
            if name is None:
                continue
            n_txt = f"{int(n):,}" if n is not None else ""
            lines.append(f"{i}. {name} {n_txt}건".strip())
        if row_count > 12:
            lines.append(f"외 {row_count - 12}개 구간")
        return "\n".join(lines)

    kind_label = "상위" if plan.query_kind == "rank" else "조건에 해당하는"
    lines = [f"{prefix}{kind_label} 건물 {row_count}건을 조회했습니다."]
    for i, row in enumerate(rows[:10], start=1):
        lines.append(f"{i}. {_row_line(row)}")
    if row_count > 10:
        lines.append(f"외 {row_count - 10}건")
    return "\n".join(lines)


def format_semantic_clarify(plan: SemanticQueryPlan) -> str:
    bits = [item.strip() for item in plan.ambiguities if item and item.strip()]
    if not bits:
        bits = ["질문을 더 구체적으로 알려 주세요."]
    return "확인이 필요합니다. " + " ".join(bits)


def _row_line(row: dict[str, Any]) -> str:
    name = _first_text(row, ("name", "A24"))
    dong = _first_text(row, ("legal_dong", "A4"))
    lot = _first_text(row, ("lot_address", "A5"))
    height = row.get("height_m", row.get("A16"))
    area = row.get("gross_floor_area_m2", row.get("A14"))
    bits: list[str] = []
    if name:
        bits.append(name)
    loc = " ".join(p for p in (dong, lot) if p)
    if loc:
        bits.append(loc)
    if height not in (None, ""):
        bits.append(f"높이 {_fmt(height)}m")
    if area not in (None, "") and not bits:
        bits.append(f"연면적 {_fmt(area)}㎡")
    elif area not in (None, "") and name:
        bits.append(f"연면적 {_fmt(area)}㎡")
    return " · ".join(bits) or str(row)


def _first_text(row: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        val = row.get(key)
        if val not in (None, ""):
            return str(val).strip()
    return None


def _first_number(rows: list[dict[str, Any]] | dict[str, Any], keys: tuple[str, ...]) -> float | None:
    row = rows[0] if isinstance(rows, list) and rows else rows
    if not isinstance(row, dict):
        return None
    for key in keys:
        if key in row and row[key] is not None:
            try:
                return float(row[key])
            except (TypeError, ValueError):
                continue
    if len(row) == 1:
        only = next(iter(row.values()))
        try:
            return float(only)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
    return None


def _fmt(value: object) -> str:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return str(value)
    if abs(number - round(number)) < 1e-6:
        return f"{int(round(number)):,}"
    return sql_number(number)


def _label(key: str) -> str:
    labels = {
        "count": "건수",
        "n": "건수",
        "avg_height_m": "평균 높이",
        "avg_gross_floor_area_m2": "평균 연면적",
        "usage": "용도",
        "height_m": "높이",
        "gross_floor_area_m2": "연면적",
    }
    return labels.get(key, key)
