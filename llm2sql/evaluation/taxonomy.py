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


def label(code: str) -> str:
    return ERROR_LABELS.get(code, "unknown")
