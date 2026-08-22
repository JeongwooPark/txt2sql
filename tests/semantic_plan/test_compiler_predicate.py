from llm2sql.semantic_plan.compiler import compile_semantic_plan
from llm2sql.semantic_plan.models import (
    FilterSpec,
    OperandSpec,
    PredicateSpec,
    SemanticQueryPlan,
)


def test_or_parentheses() -> None:
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
    sql = compile_semantic_plan(plan).sql
    assert " OR " in sql
    assert sql.count("(") >= 1
    assert "INSERT" not in sql.upper()


def test_between_and_params() -> None:
    plan = SemanticQueryPlan(
        query_kind="list",
        entity="building",
        filters=[
            FilterSpec(field="height_m", operator="between", value=50, value2=100, unit="m")
        ],
        select=["name", "height_m"],
        limit=100,
    )
    compiled = compile_semantic_plan(plan)
    assert "BETWEEN" in compiled.sql.upper()
    assert 50 in compiled.params or compiled.params


def test_field_to_field_no_literal_injection() -> None:
    plan = SemanticQueryPlan(
        query_kind="list",
        entity="building",
        filters=[
            FilterSpec(
                field="building_area_m2",
                operator="gt",
                value_field="gross_floor_area_m2",
            )
        ],
        select=["name", "building_area_m2", "gross_floor_area_m2"],
        limit=100,
    )
    sql = compile_semantic_plan(plan).sql
    assert '"A12"' in sql
    assert '"A14"' in sql
    assert "DROP" not in sql.upper()
    assert "';" not in sql
