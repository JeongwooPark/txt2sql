from llm2sql.semantic_plan.migrate import migrate_plan_v11, validate_predicate
from llm2sql.semantic_plan.models import (
    FilterSpec,
    OperandSpec,
    PredicateSpec,
    SemanticCompileError,
    SemanticQueryPlan,
)


def test_v1_filters_migrate_to_and_tree() -> None:
    plan = SemanticQueryPlan(
        query_kind="list",
        entity="building",
        filters=[
            FilterSpec(field="usage", operator="eq", value="공동주택"),
            FilterSpec(field="height_m", operator="gte", value=50, unit="m"),
        ],
        select=["name"],
    )
    v11 = migrate_plan_v11(plan)
    assert v11.version == "1.1"
    assert v11.predicate is not None
    assert v11.predicate.op == "and"
    assert len(v11.predicate.args or []) == 2
    dumped = v11.model_dump()
    roundtrip = SemanticQueryPlan.model_validate(dumped)
    assert roundtrip.predicate.op == "and"


def test_or_and_field_comparison() -> None:
    pred = PredicateSpec(
        op="or",
        args=[
            PredicateSpec(
                op="cmp",
                operator="eq",
                left=OperandSpec(kind="field", field="usage"),
                right=OperandSpec(kind="literal", value="공동주택"),
            ),
            PredicateSpec(
                op="cmp",
                operator="eq",
                left=OperandSpec(kind="field", field="usage"),
                right=OperandSpec(kind="literal", value="단독주택"),
            ),
        ],
    )
    plan = SemanticQueryPlan(query_kind="count", entity="building", predicate=pred)
    v11 = migrate_plan_v11(plan)
    assert v11.predicate.op == "or"
    cmp = PredicateSpec(
        op="cmp",
        operator="gt",
        left=OperandSpec(kind="field", field="building_area_m2"),
        right=OperandSpec(kind="field", field="gross_floor_area_m2"),
    )
    validate_predicate(cmp)


def test_predicate_limits() -> None:
    node = PredicateSpec(
        op="cmp",
        operator="eq",
        left=OperandSpec(kind="field", field="usage"),
        right=OperandSpec(kind="literal", value="x"),
    )
    deep = node
    for _ in range(8):
        deep = PredicateSpec(op="not", args=[deep])
    try:
        validate_predicate(deep)
    except SemanticCompileError:
        return
    raise AssertionError("expected depth error")
