"""SemanticQueryPlan canonical 비교. SQL 문자열은 사용하지 않는다."""

from __future__ import annotations

from typing import Any

from txt2sql.evaluation.taxonomy import ErrorCode
from txt2sql.semantic_plan.migrate import dict_predicate_to_spec, migrate_plan_v11
from txt2sql.semantic_plan.models import PredicateSpec, SemanticQueryPlan

_IDENTITY_SELECT = frozenset({"name", "legal_dong", "lot_address"})


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
        json_cell(item.get("value_field")),
        str(item.get("unit") or ""),
    )


def _as_predicate(raw: Any) -> PredicateSpec | None:
    if raw is None:
        return None
    if isinstance(raw, PredicateSpec):
        return raw
    if isinstance(raw, dict):
        return dict_predicate_to_spec(raw)
    return None


def _pred_shape(pred: PredicateSpec | None) -> Any:
    if pred is None:
        return None
    if pred.op in {"and", "or"}:
        args = sorted(
            (_pred_shape(child) for child in (pred.args or [])),
            key=lambda item: str(item),
        )
        return {"op": pred.op, "args": args}
    if pred.op == "not":
        child = _pred_shape(pred.args[0]) if pred.args else None
        return {"op": "not", "args": [child]}
    right = pred.right
    return {
        "op": "cmp",
        "operator": pred.operator,
        "left": pred.left.field if pred.left else None,
        "right_field": right.field if right and right.kind == "field" else None,
        "right_value": right.value if right and right.kind == "literal" else None,
    }


def canonicalize_plan(plan: SemanticQueryPlan | dict[str, Any]) -> dict[str, Any]:
    data = _dump(plan)
    raw_pred = data.get("predicate")
    try:
        migrated = migrate_plan_v11(SemanticQueryPlan.model_validate({**data, "predicate": None}))
        data = migrated.model_dump(mode="json")
        if raw_pred:
            data["predicate"] = _as_predicate(raw_pred).model_dump(mode="json") if _as_predicate(raw_pred) else raw_pred
    except Exception:
        pass
    filters = sorted(data.get("filters") or [], key=_filter_key)
    aggregations = sorted(
        [
            {"function": item.get("function"), "field": item.get("field")}
            for item in (data.get("aggregations") or [])
        ],
        key=lambda item: (str(item.get("function") or ""), str(item.get("field") or "")),
    )
    scope = data.get("scope") or {}
    place = (scope.get("place") or {}) if isinstance(scope, dict) else {}
    select = [name for name in (data.get("select") or []) if name not in _IDENTITY_SELECT]
    pred_spec = _as_predicate(data.get("predicate") or raw_pred)
    return {
        "query_kind": data.get("query_kind"),
        "entity": data.get("entity"),
        "place_name": (place.get("name") or "").strip(),
        "spatial_mode": scope.get("spatial_mode") if isinstance(scope, dict) else None,
        "filters": filters,
        "select": sorted(set(select)),
        "aggregations": aggregations,
        "group_by": list(data.get("group_by") or []),
        "order_by": [
            {"field": item.get("field"), "direction": item.get("direction")}
            for item in (data.get("order_by") or [])
        ],
        "limit": data.get("limit"),
        "spatial_relations": [
            {
                "relation": item.get("relation"),
                "place": ((item.get("target") or {}).get("place") or {}).get("name"),
                "distance_m": item.get("distance_m"),
            }
            for item in (data.get("spatial_relations") or [])
        ],
        "requires_clarification": bool(data.get("requires_clarification")),
        "predicate_shape": _pred_shape(pred_spec),
        "predicate_op": pred_spec.op if pred_spec else None,
        "unsupported_reason": bool(data.get("unsupported_reason")),
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
        else:
            errors.append("P03")

    gold_pred_op = gold_c.get("predicate_op")
    pred_pred_op = pred_c.get("predicate_op")
    if gold_pred_op in {"or", "not"} and gold_pred_op != pred_pred_op:
        errors.append("P04")
    if gold_c.get("predicate_shape") and gold_c.get("predicate_shape") != pred_c.get("predicate_shape"):
        if gold_pred_op in {"or", "not"}:
            errors.append("P04")

    if gold_c["aggregations"] or gold_c["query_kind"] == "aggregate":
        if (
            pred_c["aggregations"] != gold_c["aggregations"]
            or pred_c["query_kind"] != gold_c["query_kind"]
            or pred_c["group_by"] != gold_c["group_by"]
        ):
            errors.append("P05")

    if gold_c["order_by"] and pred_c["order_by"] != gold_c["order_by"]:
        errors.append("P06")
    if gold_c["limit"] is not None and pred_c["limit"] != gold_c["limit"]:
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
    pred_c = canonicalize_plan(predicted)
    gold_c = canonicalize_plan(gold)
    if gold_c["limit"] is None:
        pred_c = {**pred_c, "limit": None}
        gold_c = {**gold_c, "limit": None}
    return pred_c == gold_c
