from txt2sql.semantic_plan.compiler import compile_semantic_plan
from txt2sql.semantic_plan.models import (
    FilterSpec,
    PlaceSpec,
    ScopeSpec,
    SemanticQueryPlan,
)


def test_and_subset_sql_contains_both_conditions() -> None:
    wide = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="해운대구", kind="gu")),
        filters=[FilterSpec(field="height_m", operator="gte", value=30)],
    )
    narrow = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="해운대구", kind="gu")),
        filters=[
            FilterSpec(field="height_m", operator="gte", value=30),
            FilterSpec(field="ground_floors", operator="gte", value=10),
        ],
    )
    wide_sql = compile_semantic_plan(wide).sql
    narrow_sql = compile_semantic_plan(narrow).sql
    assert "A16" in wide_sql
    assert "A16" in narrow_sql
    assert 'A26"::float8 >=' in narrow_sql or 'A26"::float8 >=' in narrow_sql.replace(" ", "")
    assert ">= 10" in narrow_sql
    assert ">= 10" not in wide_sql


def test_between_is_subset_of_lower_bound_only() -> None:
    lower = compile_semantic_plan(
        SemanticQueryPlan(
            query_kind="count",
            entity="building",
            filters=[FilterSpec(field="height_m", operator="gte", value=20)],
        )
    ).sql.upper()
    both = compile_semantic_plan(
        SemanticQueryPlan(
            query_kind="count",
            entity="building",
            filters=[
                FilterSpec(field="height_m", operator="between", value=20, value2=40)
            ],
        )
    ).sql.upper()
    assert "20" in lower
    assert "BETWEEN" in both
    assert "40" in both
