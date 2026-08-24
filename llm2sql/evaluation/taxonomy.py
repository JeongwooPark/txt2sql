"""평가·trace 공통 오류 taxonomy."""

from __future__ import annotations

from typing import Literal

ErrorCode = Literal[
    "R01",
    "P01",
    "P02",
    "P03",
    "P04",
    "P05",
    "P06",
    "P07",
    "S01",
    "S02",
    "S03",
    "S04",
    "G01",
    "G02",
    "Q01",
    "Q02",
    "Q03",
    "A01",
    "A02",
    "C01",
]

ERROR_LABELS: dict[str, str] = {
    "R01": "route_error",
    "P01": "entity_missing",
    "P02": "field_missing",
    "P03": "operator_error",
    "P04": "boolean_structure_error",
    "P05": "aggregate_error",
    "P06": "order_limit_error",
    "P07": "place_resolution_error",
    "S01": "table_link_error",
    "S02": "column_link_error",
    "S03": "value_link_error",
    "S04": "join_path_error",
    "G01": "spatial_relation_error",
    "G02": "srid_unit_error",
    "Q01": "sql_syntax_error",
    "Q02": "sql_execution_error",
    "Q03": "result_shape_error",
    "A01": "should_clarify_but_executed",
    "A02": "unnecessary_clarification",
    "C01": "followup_context_error",
}

ROOT_CAUSES = (
    "PREDICATE_DROPPED",
    "BOOLEAN_OR_DROPPED",
    "BOOLEAN_NOT_DROPPED",
    "RANGE_BOUND_DROPPED",
    "OUTPUT_SHAPE_MISMATCH",
    "ENTITY_SELECTION_ERROR",
    "SPATIAL_TARGET_DROPPED",
    "FOLLOWUP_CONTEXT_LOST",
    "EXECUTION_TIMEOUT",
)

_CODE_TO_ROOT = {
    "P04": "BOOLEAN_OR_DROPPED",
    "P03": "RANGE_BOUND_DROPPED",
    "P05": "OUTPUT_SHAPE_MISMATCH",
    "P01": "ENTITY_SELECTION_ERROR",
    "G01": "SPATIAL_TARGET_DROPPED",
    "C01": "FOLLOWUP_CONTEXT_LOST",
    "Q03": "OUTPUT_SHAPE_MISMATCH",
    "Q02": "EXECUTION_TIMEOUT",
    "R01": "ENTITY_SELECTION_ERROR",
}


def classify_root_causes(
    error_codes: list[str],
    *,
    sql: str | None = None,
    timed_out: bool = False,
) -> list[str]:
    causes: list[str] = []
    if timed_out or any("timeout" in code.lower() for code in error_codes):
        causes.append("EXECUTION_TIMEOUT")
    for code in error_codes:
        mapped = _CODE_TO_ROOT.get(code)
        if mapped and mapped not in causes:
            causes.append(mapped)
    if sql:
        upper = sql.upper()
        if " OR " not in upper and "BOOLEAN_OR_DROPPED" not in causes:
            if "P04" in error_codes:
                causes.append("BOOLEAN_OR_DROPPED")
        if "NOT " not in upper and "BOOLEAN_NOT_DROPPED" not in causes:
            if "P04" in error_codes:
                causes.append("BOOLEAN_NOT_DROPPED")
    return list(dict.fromkeys(causes))


def label(code: str) -> str:
    return ERROR_LABELS.get(code, "unknown")
