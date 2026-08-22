"""SemanticQueryPlan canonical 비교. SQL 문자열은 사용하지 않는다."""

from __future__ import annotations

from typing import Any

from llm2sql.evaluation.taxonomy import ErrorCode
from llm2sql.semantic_plan.models import SemanticQueryPlan


def _dump(plan: SemanticQueryPlan | dict[str, Any]) -> dict[str, Any]:
    if isinstance(plan, SemanticQueryPlan):
        return plan.model_dump(mode="json")
    return dict(plan)


def json_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return "|".join(sorted(str(v) for v in value))
    return str(value)


def _filter_key(item: dict[str, Any]) -> tuple:
    return (
        str(item.get("field") or ""),
        str(item.get("operator") or ""),
        json_cell(item.get("value")),
        json_cell(item.get("value2")),
        str(item.get("unit") or ""),
    )


def canonicalize_plan(plan: SemanticQueryPlan | dict[str, Any]) -> dict[str, Any]:
    data = _dump(plan)
    filters = sorted(data.get("filters") or [], key=_filter_key)
    aggregations = sorted(
        data.get("aggregations") or [],
        key=lambda item: (str(item.get("function") or ""), str(item.get("field") or "")),
    )
    scope = data.get("scope") or {}
    place = (scope.get("place") or {}) if isinstance(scope, dict) else {}
    return {
        "query_kind": data.get("query_kind"),
        "entity": data.get("entity"),
        "place_name": (place.get("name") or "").strip(),
        "spatial_mode": scope.get("spatial_mode") if isinstance(scope, dict) else None,
        "filters": filters,
        "select": list(data.get("select") or []),
        "aggregations": aggregations,
        "group_by": list(data.get("group_by") or []),
        "order_by": list(data.get("order_by") or []),
        "limit": data.get("limit"),
        "spatial_relations": list(data.get("spatial_relations") or []),
        "requires_clarification": bool(data.get("requires_clarification")),
    }


def classify_plan_errors(
    predicted: SemanticQueryPlan | dict[str, Any] | None,
    gold: SemanticQueryPlan | dict[str, Any],
) -> list[ErrorCode]:
    gold_c = canonicalize_plan(gold)
    if predicted is None:
        return ["A02"] if gold_c["requires_clarification"] else ["P01"]
    pred_c = canonicalize_plan(predicted)
    errors: list[ErrorCode] = []

    if pred_c["requires_clarification"] and not gold_c["requires_clarification"]:
        errors.append("A02")
    if gold_c["requires_clarification"] and not pred_c["requires_clarification"]:
        errors.append("A01")
    if pred_c["entity"] != gold_c["entity"]:
        errors.append("P01")

    gold_filter_fields = {str(item.get("field")) for item in gold_c["filters"]}
    pred_filter_fields = {str(item.get("field")) for item in pred_c["filters"]}
    gold_out = set(gold_c["select"]) | {
        str(item.get("field") or "") for item in gold_c["aggregations"] if item.get("field")
    }
    pred_out = set(pred_c["select"]) | {
        str(item.get("field") or "") for item in pred_c["aggregations"] if item.get("field")
    }
    if gold_filter_fields - pred_filter_fields or gold_out - pred_out:
        errors.append("P02")

    if gold_c["filters"] != pred_c["filters"]:
        gold_ops = {(item.get("field"), item.get("operator")) for item in gold_c["filters"]}
        pred_ops = {(item.get("field"), item.get("operator")) for item in pred_c["filters"]}
        not_like = {"neq", "not_in", "not"}
        gold_has_not = any(item.get("operator") in not_like for item in gold_c["filters"])
        pred_has_not = any(item.get("operator") in not_like for item in pred_c["filters"])
        if gold_has_not != pred_has_not:
            errors.append("P04")
        elif gold_ops != pred_ops:
            errors.append("P03")
        else:
            errors.append("P03")

    if gold_c["aggregations"] or gold_c["query_kind"] == "aggregate":
        if (
            pred_c["aggregations"] != gold_c["aggregations"]
            or pred_c["query_kind"] != gold_c["query_kind"]
            or pred_c["group_by"] != gold_c["group_by"]
        ):
            errors.append("P05")

    if (gold_c["order_by"] or gold_c["limit"] is not None) and (
        pred_c["order_by"] != gold_c["order_by"] or pred_c["limit"] != gold_c["limit"]
    ):
        errors.append("P06")

    if gold_c["place_name"] != pred_c["place_name"] or (
        gold_c["spatial_mode"] and gold_c["spatial_mode"] != pred_c["spatial_mode"]
    ):
        errors.append("P07")

    if gold_c["spatial_relations"] != pred_c["spatial_relations"]:
        errors.append("G01")

    return list(dict.fromkeys(errors))


def plans_match(
    predicted: SemanticQueryPlan | dict[str, Any] | None,
    gold: SemanticQueryPlan | dict[str, Any],
) -> bool:
    if predicted is None:
        return False
    return canonicalize_plan(predicted) == canonicalize_plan(gold)
