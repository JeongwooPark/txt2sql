"""filters[]와 predicate를 하나의 canonical PredicateSpec으로 합친다."""

from __future__ import annotations

from collections.abc import Iterator

from txt2sql.semantic_plan.migrate import filter_to_predicate
from txt2sql.semantic_plan.models import (
    FilterSpec,
    OperandSpec,
    PredicateSpec,
    SemanticQueryPlan,
)


def walk_predicate(pred: PredicateSpec | None) -> Iterator[PredicateSpec]:
    if pred is None:
        return
    yield pred
    for child in pred.args or []:
        yield from walk_predicate(child)


def has_op(pred: PredicateSpec | None, op: str) -> bool:
    return any(node.op == op for node in walk_predicate(pred))


def has_operator(pred: PredicateSpec | None, operator: str) -> bool:
    return any(
        node.op == "cmp" and node.operator == operator for node in walk_predicate(pred)
    )


def predicate_fields(pred: PredicateSpec | None) -> set[str]:
    found: set[str] = set()
    for node in walk_predicate(pred):
        if node.left and node.left.field:
            found.add(node.left.field)
        if node.right and node.right.field:
            found.add(node.right.field)
    return found


def predicate_literals(pred: PredicateSpec | None) -> list[object]:
    values: list[object] = []
    for node in walk_predicate(pred):
        if node.right and node.right.kind == "literal" and node.right.value is not None:
            values.append(node.right.value)
    return values


def predicate_atoms(pred: PredicateSpec | None) -> list[PredicateSpec]:
    return [node for node in walk_predicate(pred) if node.op == "cmp"]


def and_predicates(nodes: list[PredicateSpec | None]) -> PredicateSpec | None:
    cleaned = [item for item in nodes if item is not None]
    if not cleaned:
        return None
    if len(cleaned) == 1:
        return cleaned[0]
    return PredicateSpec(op="and", args=cleaned)


def effective_predicate(plan: SemanticQueryPlan) -> PredicateSpec | None:
    """predicate가 있어도 filters를 버리지 않고 AND로 결합한다."""
    nodes: list[PredicateSpec] = []
    if plan.predicate is not None:
        nodes.append(plan.predicate)
    nodes.extend(filter_to_predicate(item) for item in plan.filters)
    return and_predicates(nodes)


def range_bounds(
    pred: PredicateSpec | None, field: str
) -> tuple[object | None, object | None]:
    low: object | None = None
    high: object | None = None
    for node in predicate_atoms(pred):
        left = node.left.field if node.left else None
        if left != field:
            continue
        if (
            node.operator == "between"
            and node.right
            and isinstance(node.right.value, (list, tuple))
        ):
            raw = list(node.right.value)
            if len(raw) >= 2:
                return raw[0], raw[1]
        if node.operator in {"gte", "gt"} and node.right:
            low = node.right.value
        if node.operator in {"lte", "lt"} and node.right:
            high = node.right.value
    return low, high


def has_field_compare(pred: PredicateSpec | None) -> bool:
    for node in predicate_atoms(pred):
        if (
            node.left
            and node.left.kind == "field"
            and node.right
            and node.right.kind == "field"
        ):
            return True
    return False


def cmp_field(
    field: str,
    operator: str,
    value: object,
    *,
    unit: str | None = None,
    value_field: str | None = None,
) -> PredicateSpec:
    left = OperandSpec(kind="field", field=field)
    if value_field:
        right = OperandSpec(kind="field", field=value_field)
    else:
        right = OperandSpec(kind="literal", value=value, unit=unit)
    return PredicateSpec(op="cmp", operator=operator, left=left, right=right)


def filter_specs(plan: SemanticQueryPlan) -> list[FilterSpec]:
    return list(plan.filters)


def aggregation_functions(plan: SemanticQueryPlan) -> set[str]:
    return {item.function for item in plan.aggregations}
