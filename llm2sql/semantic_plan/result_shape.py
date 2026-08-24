"""결과 shape·정렬·anomaly. 0건은 정상 가능 결과이며 조건을 완화하지 않는다."""

from __future__ import annotations

from typing import Any

from llm2sql.semantic_plan.models import SemanticQueryPlan


def diagnose_result_shape(
    plan: SemanticQueryPlan,
    rows: list[dict[str, Any]] | None,
) -> list[str]:
    rows = rows or []
    errors: list[str] = []
    if plan.query_kind == "count":
        if len(rows) != 1:
            errors.append("Q03")
        elif rows and not any(isinstance(v, (int, float)) for v in rows[0].values()):
            errors.append("Q03")
    if plan.query_kind == "rank" and plan.limit and len(rows) > plan.limit:
        errors.append("Q03")
    if plan.query_kind == "list" and len(rows) > 5000:
        errors.append("Q03")
    if plan.query_kind in {"aggregate", "distribution"} and plan.aggregations and rows:
        aliases = {
            item.alias
            or (f"{item.function}_{item.field}" if item.field else item.function)
            for item in plan.aggregations
        }
        row0 = rows[0]
        if aliases and not any(alias in row0 for alias in aliases):
            numeric_cols = [k for k, v in row0.items() if isinstance(v, (int, float))]
            if len(numeric_cols) < len(plan.aggregations):
                errors.append("Q03")
        for key in plan.group_by:
            if key not in row0:
                errors.append("Q03")
                break
    if rows and all(all(v is None for v in row.values()) for row in rows):
        errors.append("Q03")
    return errors
