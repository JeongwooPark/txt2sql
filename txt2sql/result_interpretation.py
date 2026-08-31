"""Result interpretation layer (Phase 13) — separate from SQL generation."""

from __future__ import annotations

from typing import Any

from txt2sql.query_ir.models import QueryIR


def interpret_result(
    *,
    question: str,
    query_ir: QueryIR | dict[str, Any] | None,
    sql: str | None,
    column_semantics: dict[str, str] | None = None,
    rows: list[dict[str, Any]] | None,
    row_count: int = 0,
    units: dict[str, str] | None = None,
    scope: dict[str, Any] | None = None,
    metric: dict[str, Any] | None = None,
    dimensions: list[str] | None = None,
) -> dict[str, Any]:
    """Produce structured interpretation from query results."""
    ir = query_ir if isinstance(query_ir, dict) else (query_ir.model_dump() if query_ir else {})
    n = row_count or len(rows or [])
    task = ir.get("task") or "unknown"

    direct_answer = ""
    if n == 0:
        direct_answer = "조회 결과가 없습니다."
    elif n == 1 and rows:
        vals = [str(v) for v in rows[0].values() if v is not None]
        direct_answer = ", ".join(vals[:5])
    else:
        direct_answer = f"총 {n}건의 결과입니다."

    summary_parts = [f"질문 유형: {task}"]
    if scope:
        place = scope.get("canonical_name") or scope.get("place")
        if place:
            summary_parts.append(f"범위: {place}")
    if metric:
        op = metric.get("operator")
        measure = metric.get("measure")
        if op:
            summary_parts.append(f"지표: {op}" + (f"({measure})" if measure else ""))

    return {
        "direct_answer": direct_answer,
        "summary": "; ".join(summary_parts),
        "interpretation": direct_answer,
        "limitations": [] if n > 0 else ["결과 없음"],
        "table": rows[:100] if rows else [],
        "chart_candidate": task in {"group", "distribution", "rank"},
        "map_candidate": bool(ir.get("spatial")),
        "metric": metric,
        "scope": scope,
        "dimensions": dimensions or [],
        "row_count": n,
    }
