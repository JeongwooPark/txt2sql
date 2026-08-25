from txt2sql.semantic_plan.compiler import compile_semantic_plan
from txt2sql.semantic_plan.models import (
    FilterSpec,
    OperandSpec,
    PredicateSpec,
    SemanticQueryPlan,
)
from txt2sql.semantic_plan.predicate_utils import effective_predicate, has_op, range_bounds


def _or_usage() -> PredicateSpec:
    return PredicateSpec(
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


def test_effective_predicate_keeps_or_and_area_filter() -> None:
    plan = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        predicate=_or_usage(),
        filters=[
            FilterSpec(field="gross_floor_area_m2", operator="gte", value=1000),
        ],
    )
    pred = effective_predicate(plan)
    assert pred is not None
    assert has_op(pred, "or")
    sql = compile_semantic_plan(plan).sql.upper()
    assert " OR " in sql
    assert "A14" in sql
    assert "1000" in sql


def test_between_emits_low_and_high() -> None:
    plan = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        filters=[
            FilterSpec(
                field="height_m",
                operator="between",
                value=60,
                value2=120,
            )
        ],
    )
    sql = compile_semantic_plan(plan).sql.upper()
    assert "BETWEEN" in sql
    assert "60" in sql
    assert "120" in sql
    low, high = range_bounds(effective_predicate(plan), "height_m")
    assert low == 60
    assert high == 120


def test_not_in_emits_sql() -> None:
    plan = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        filters=[
            FilterSpec(
                field="usage",
                operator="not_in",
                value=["공장", "창고시설"],
            )
        ],
    )
    compiled = compile_semantic_plan(plan)
    assert "NOT IN" in compiled.sql.upper()
    assert "공장" in compiled.sql


def test_nested_or_and_not_parentheses() -> None:
    inner = PredicateSpec(op="not", args=[_or_usage()])
    plan = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        predicate=inner,
        filters=[FilterSpec(field="height_m", operator="gte", value=40)],
    )
    sql = compile_semantic_plan(plan).sql
    assert "NOT" in sql.upper()
    assert " OR " in sql.upper()
    assert sql.count("(") >= 2
