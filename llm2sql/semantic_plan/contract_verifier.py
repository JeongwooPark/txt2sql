"""Contract span이 Plan 노드에 연결됐는지 검증하고 slot confidence를 계산한다."""

from __future__ import annotations

from dataclasses import dataclass, field

from llm2sql.query_understanding.contract import QueryContract, extract_contract
from llm2sql.semantic_plan.models import PlanConfidence, SemanticQueryPlan
from llm2sql.semantic_plan.predicate_utils import (
    effective_predicate,
    has_field_compare,
    has_op,
    has_operator,
    predicate_fields,
    range_bounds,
)


@dataclass
class ContractVerifyResult:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    confidence: PlanConfidence = field(default_factory=PlanConfidence)
    hard_fail: bool = False


def _slot(value: float) -> float:
    return max(0.0, min(1.0, value))


def verify_contract(
    question: str,
    plan: SemanticQueryPlan,
    *,
    contract: QueryContract | None = None,
    min_slot: float = 0.85,
) -> ContractVerifyResult:
    contract = contract or extract_contract(question)
    reasons: list[str] = []
    if plan.requires_clarification:
        return ContractVerifyResult(
            ok=False,
            reasons=["clarify"],
            confidence=PlanConfidence(overall=0.0),
            hard_fail=False,
        )

    entity_score = 1.0 if plan.entity in {
        "building",
        "admin_area",
        "basic_zone",
        "industrial_complex",
    } else 0.4
    if contract.places:
        place_ok = bool(plan.scope and plan.scope.place and plan.scope.place.name)
        if not place_ok:
            from llm2sql.domain import is_busan_wide

            place_ok = is_busan_wide(question)
        if not place_ok:
            place_ok = any(
                getattr(rel.target, "entity", None) == "industrial_complex"
                or (
                    rel.target.place is not None
                    and bool((rel.target.place.name or "").strip())
                )
                for rel in plan.spatial_relations
            )
        scope_score = 1.0 if place_ok else 0.0
        if not place_ok:
            reasons.append("P07")
    else:
        scope_score = 1.0

    pred = effective_predicate(plan)
    pred_fields = {item.field for item in plan.filters}
    pred_fields |= predicate_fields(pred)
    pred_fields |= {item.field for item in plan.aggregations if item.field}
    pred_fields |= set(plan.select)
    pred_fields |= set(plan.group_by)
    for ratio in plan.ratios:
        pred_fields |= predicate_fields(ratio.numerator_predicate)
        pred_fields |= predicate_fields(ratio.denominator_predicate)
    metric_fields = {span.value for span in contract.metrics if span.value}
    field_hits = len(metric_fields & pred_fields)
    fields_score = 1.0 if not metric_fields else field_hits / len(metric_fields)

    pred_score = 1.0
    if any(span.kind == "or" for span in contract.boolean_ops):
        if not has_op(pred, "or"):
            pred_score = 0.0
            reasons.append("P04")
    if any(span.kind == "not" for span in contract.boolean_ops):
        has_not = has_op(pred, "not") or any(item.operator == "neq" for item in plan.filters)
        if not has_not:
            pred_score = 0.0
            reasons.append("P04")
    if contract.ranges:
        range_ok = has_operator(pred, "between")
        if not range_ok:
            for span in contract.ranges:
                field = span.meta.get("field")
                low, high = range_bounds(pred, field) if field else (None, None)
                if low is None or high is None:
                    range_ok = False
                    break
                range_ok = True
        if not range_ok:
            pred_score = min(pred_score, 0.0)
            reasons.append("P03")
    if contract.comparisons:
        has_ff = has_field_compare(pred) or any(item.value_field for item in plan.filters)
        if not has_ff:
            pred_score = 0.0
            reasons.append("P03")

    agg_score = 1.0
    plan_fns = {item.function for item in plan.aggregations}
    if plan.query_kind == "count":
        plan_fns.add("count")
    wanted_aggs = {item.function for item in contract.aggregation_requests}
    if wanted_aggs and not wanted_aggs <= plan_fns:
        agg_score = 0.0
        reasons.append("missing_aggregation")
        reasons.append("P05")
    if contract.aggregations:
        wanted = {span.value for span in contract.aggregations}
        got = {item.function for item in plan.aggregations}
        if not got or not wanted.issubset(got):
            agg_score = 0.0
            reasons.append("P05")
        if contract.groups and not plan.group_by:
            agg_score = 0.0
            reasons.append("P05")
    if contract.group_fields:
        if not set(contract.group_fields) <= set(plan.group_by):
            agg_score = 0.0
            reasons.append("missing_group")
            reasons.append("P05")

    if contract.order:
        want_dir = contract.order[0].value
        got_dir = plan.order_by[0].direction if plan.order_by else None
        if got_dir != want_dir:
            reasons.append("P06")
            agg_score = min(agg_score, 0.2)
    if contract.order_requests and not plan.order_by:
        reasons.append("missing_order")
        agg_score = min(agg_score, 0.0)
    elif contract.order_requests and contract.order_requests[0].field:
        got_field = plan.order_by[0].field if plan.order_by else None
        if got_field != contract.order_requests[0].field:
            reasons.append("missing_order_field")
            agg_score = min(agg_score, 0.0)

    if contract.limit is not None and plan.limit != contract.limit:
        reasons.append("missing_limit")
        agg_score = min(agg_score, 0.0)

    if plan.query_kind in {"list", "rank"} and contract.output_fields:
        got_out = (
            set(plan.select)
            | {item.field for item in plan.projections}
            | {item.field for item in plan.aggregations if item.field}
        )
        if not set(contract.output_fields) <= got_out:
            reasons.append("missing_output")
            agg_score = min(agg_score, 0.0)

    if contract.ratios:
        if not plan.ratios:
            reasons.append("missing_ratio")
            agg_score = min(agg_score, 0.0)
        elif any(item.has_denominator for item in contract.ratios) and any(
            item.denominator_predicate is None for item in plan.ratios
        ):
            reasons.append("missing_ratio_denominator")
            agg_score = min(agg_score, 0.0)

    spatial_score = 1.0
    if contract.places and plan.spatial_relations:
        spatial_score = 1.0

    slots = {
        "entity": _slot(entity_score),
        "scope": _slot(scope_score),
        "fields": _slot(fields_score),
        "predicates": _slot(pred_score),
        "aggregation": _slot(agg_score),
        "spatial": _slot(spatial_score),
    }
    overall = sum(slots.values()) / len(slots)
    confidence = PlanConfidence(**slots, overall=_slot(overall))
    hard = bool(reasons)
    below = [name for name, val in slots.items() if val < min_slot]
    if below:
        reasons.append("slot_below_threshold:" + ",".join(below))
        hard = True
    ok = not hard
    return ContractVerifyResult(ok=ok, reasons=reasons, confidence=confidence, hard_fail=hard)


def _predicate_fields(pred) -> set[str]:
    found: set[str] = set()
    if pred is None:
        return found
    if pred.left and pred.left.field:
        found.add(pred.left.field)
    if pred.right and pred.right.field:
        found.add(pred.right.field)
    for child in pred.args or []:
        found |= _predicate_fields(child)
    return found
