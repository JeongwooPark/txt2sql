"""휴리스틱 Plan을 질문 contract 완전 소비 여부로만 채택한다."""

from __future__ import annotations

from llm2sql.domain import USAGE_ALIASES, extract_usages
from llm2sql.query_understanding.contract import QueryContract
from llm2sql.semantic_plan.models import SemanticQueryPlan


def accept_heuristic_plan(contract: QueryContract, plan: SemanticQueryPlan) -> bool:
    if plan.requires_clarification:
        return True
    if plan.unsupported_reason:
        return False
    if not (
        contract.boolean_structure_supported
        and contract.aggregation_complete
        and contract.all_numeric_expressions_bound
        and contract.all_requested_outputs_bound
        and not contract.unresolved_spans
    ):
        return False
    if any(span.kind == "or" for span in contract.boolean_ops):
        if not _or_bound(contract.question, plan):
            return False
    if any(span.kind == "not" for span in contract.boolean_ops):
        if not any(item.operator == "neq" for item in plan.filters):
            return False
        if plan.predicate is None or plan.predicate.op != "not":
            return False
    if contract.comparisons:
        if not any(item.value_field for item in plan.filters):
            return False
    if contract.ranges:
        if not any(item.operator == "between" for item in plan.filters):
            return False
        for span in contract.ranges:
            match = next(
                (
                    item
                    for item in plan.filters
                    if item.field == span.meta.get("field") and item.operator == "between"
                ),
                None,
            )
            if match is None or match.value is None or match.value2 is None:
                return False
    if contract.aggregations:
        wanted = [span.value for span in contract.aggregations]
        got = [item.function for item in plan.aggregations]
        if not got or got[0] not in wanted:
            return False
        if contract.groups and not plan.group_by:
            return False
    if contract.order:
        wanted_dir = contract.order[0].value
        if not plan.order_by or plan.order_by[0].direction != wanted_dir:
            return False
    if contract.limits:
        if plan.limit != contract.limits[0].value:
            return False
    if contract.places:
        if plan.scope is None or plan.scope.place is None:
            return False
    return True


def _or_bound(question: str, plan: SemanticQueryPlan) -> bool:
    if plan.predicate is not None and plan.predicate.op == "or" and len(plan.predicate.args or []) >= 2:
        return True
    aliases = [alias for alias in USAGE_ALIASES if alias in question]
    mapped = list(dict.fromkeys(USAGE_ALIASES[alias] for alias in aliases))
    usages = extract_usages(question)
    if len(aliases) >= 2 and len(mapped) == 1:
        return any(item.field == "usage" and item.value == mapped[0] for item in plan.filters) or (
            plan.predicate is not None and plan.predicate.op == "cmp"
        )
    if len(usages) < 2:
        return False
    return False
