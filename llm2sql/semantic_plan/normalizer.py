"""Plan 값 정규화: 용도·단위·장소 canonical 값."""

from __future__ import annotations

from typing import Any

import psycopg

from llm2sql.domain import STRUCTURE_ALIASES, USAGE_ALIASES, extract_gu, extract_place
from llm2sql.semantic_plan.catalog import DEFAULT_LIST_SELECT, get_field
from llm2sql.semantic_plan.models import (
    FilterSpec,
    OrderSpec,
    SemanticQueryPlan,
    UnknownSemanticFieldError,
)
from llm2sql.units import convert_for_schema


def normalize_semantic_plan(
    plan: SemanticQueryPlan,
    question: str,
    *,
    conn: psycopg.Connection | None = None,
) -> SemanticQueryPlan:
    data = plan.model_dump()
    filters = [_normalize_filter(item, plan.entity) for item in plan.filters]
    data["filters"] = [item.model_dump() for item in filters if item is not None]

    if plan.scope and plan.scope.place:
        place = plan.scope.place
        guessed = extract_place(place.name) or extract_gu(place.name)
        if guessed:
            data["scope"]["place"]["name"] = guessed
        if place.kind == "unknown":
            token = guessed or place.name
            if token.endswith(("구", "군")):
                data["scope"]["place"]["kind"] = "gu"
            elif token.endswith("동"):
                data["scope"]["place"]["kind"] = "legal_dong"

    if plan.query_kind in {"list", "rank"} and not plan.select:
        data["select"] = list(DEFAULT_LIST_SELECT)
        if plan.query_kind == "rank" and plan.order_by:
            metric = plan.order_by[0].field
            if metric not in data["select"]:
                data["select"].append(metric)

    if plan.query_kind == "rank" and not plan.order_by:
        data["order_by"] = [
            OrderSpec(field="gross_floor_area_m2", direction="desc").model_dump()
        ]
        data["assumptions"] = list(plan.assumptions) + [
            "rank 지표가 없어 연면적 내림차순으로 가정"
        ]

    if plan.query_kind == "count":
        data["select"] = []
        data["limit"] = None

    if plan.query_kind == "list" and data.get("limit") is None:
        data["limit"] = 100

    if plan.query_kind == "rank" and data.get("limit") is None:
        data["limit"] = 10

    return SemanticQueryPlan.model_validate(data)


def _normalize_filter(spec: FilterSpec, entity: str) -> FilterSpec | None:
    try:
        field = get_field(entity, spec.field)
    except UnknownSemanticFieldError:
        return spec

    value: Any = spec.value
    unit = spec.unit
    if spec.field == "usage" and isinstance(value, str):
        compact = value.replace(" ", "")
        value = USAGE_ALIASES.get(value) or USAGE_ALIASES.get(compact) or value
        unit = None
    elif spec.field == "structure" and isinstance(value, str):
        for alias in sorted(STRUCTURE_ALIASES, key=len, reverse=True):
            if alias in value:
                value = alias
                break
    elif field.data_type == "number" and value is not None:
        schema_unit = "㎡" if field.unit == "m2" else ("m" if field.unit == "m" else "층")
        converted = convert_for_schema(value, unit, schema_unit)
        if converted is not None:
            value = converted.canonical
            unit = field.unit
        value2 = spec.value2
        if spec.operator == "between" and value2 is not None:
            converted2 = convert_for_schema(value2, spec.unit, schema_unit)
            if converted2 is not None:
                return spec.model_copy(
                    update={"value": value, "value2": converted2.canonical, "unit": field.unit}
                )
        return spec.model_copy(update={"value": value, "unit": unit})
    return spec.model_copy(update={"value": value, "unit": unit})
