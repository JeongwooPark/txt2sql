from llm2sql.semantic_plan.compiler import compile_semantic_plan
from llm2sql.semantic_plan.models import (
    AggregationSpec,
    ExpressionSpec,
    FilterSpec,
    OperandSpec,
    OrderSpec,
    PlaceSpec,
    PredicateSpec,
    RatioSpec,
    ScopeSpec,
    SemanticQueryPlan,
    SpatialRelationSpec,
    SpatialTargetSpec,
)


def _cmp(field: str, op: str, value: object) -> PredicateSpec:
    return PredicateSpec(
        op="cmp",
        operator=op,  # type: ignore[arg-type]
        left=OperandSpec(kind="field", field=field),
        right=OperandSpec(kind="literal", value=value),
    )


def test_compiler_does_not_invent_filter() -> None:
    plan = SemanticQueryPlan(
        query_kind="list",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="해운대구", kind="gu")),
        select=["name", "height_m"],
        order_by=[OrderSpec(field="height_m", direction="desc")],
        limit=10,
    )
    sql = compile_semantic_plan(plan).sql
    assert "<= 600" not in sql
    assert "* 8 + 30" not in sql


def test_compiler_does_not_invent_limit() -> None:
    plan = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="해운대구", kind="gu")),
    )
    sql = compile_semantic_plan(plan).sql.upper()
    assert "LIMIT" not in sql

    nearest = compile_semantic_plan(
        SemanticQueryPlan(
            query_kind="list",
            entity="building",
            spatial_relations=[
                SpatialRelationSpec(
                    relation="nearest",
                    target=SpatialTargetSpec(
                        place=PlaceSpec(name="연산동", kind="admin_dong")
                    ),
                )
            ],
        )
    ).sql.upper()
    assert "LIMIT" not in nearest


def test_compiler_does_not_invent_order_by() -> None:
    plan = SemanticQueryPlan(
        query_kind="aggregate",
        entity="building",
        aggregations=[AggregationSpec(function="count", alias="n")],
        group_by=["structure"],
    )
    sql = compile_semantic_plan(plan).sql.upper()
    assert "ORDER BY" not in sql


def test_compiler_preserves_ratio_denominator() -> None:
    plan = SemanticQueryPlan(
        query_kind="aggregate",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="영도구", kind="gu")),
        ratios=[
            RatioSpec(
                numerator_predicate=PredicateSpec(
                    op="and",
                    args=[
                        _cmp("ground_floors", "gte", 15),
                        _cmp("usage", "eq", "공동주택"),
                    ],
                ),
                denominator_predicate=_cmp("ground_floors", "gte", 15),
            )
        ],
    )
    sql = compile_semantic_plan(plan).sql
    assert sql.upper().count("FILTER") >= 2
    assert "공동주택" in sql
    assert "NULLIF(" in sql.upper()


def test_compiler_preserves_explicit_height_range() -> None:
    plan = SemanticQueryPlan(
        query_kind="list",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="중구", kind="gu")),
        filters=[
            FilterSpec(field="height_m", operator="between", value=1, value2=500),
        ],
        select=["name", "height_m"],
    )
    sql = compile_semantic_plan(plan).sql
    assert "1" in sql
    assert "500" in sql
    assert "<= 600" not in sql


def test_compiler_maps_aggregation_functions() -> None:
    plan = SemanticQueryPlan(
        query_kind="aggregate",
        entity="building",
        aggregations=[
            AggregationSpec(function="avg", field="height_m", alias="avg_h"),
            AggregationSpec(function="stddev", field="height_m", alias="sd_h"),
            AggregationSpec(
                function="percentile",
                field="height_m",
                percentile=0.9,
                alias="pctl",
            ),
        ],
    )
    sql = compile_semantic_plan(plan).sql.upper()
    assert "AVG(" in sql
    assert "STDDEV_POP(" in sql
    assert "PERCENTILE_CONT(0.9)" in sql


def test_compiler_compiles_typed_divide_expression() -> None:
    plan = SemanticQueryPlan(
        query_kind="aggregate",
        entity="building",
        aggregations=[
            AggregationSpec(
                function="avg",
                expression=ExpressionSpec(
                    kind="divide",
                    left=ExpressionSpec(kind="field", field="building_area_m2"),
                    right=ExpressionSpec(kind="field", field="gross_floor_area_m2"),
                ),
                alias="avg_ratio",
            )
        ],
    )
    sql = compile_semantic_plan(plan).sql.upper()
    assert "AVG(" in sql
    assert "NULLIF(" in sql
