from txt2sql.semantic_plan.generator import try_heuristic_plan
from txt2sql.semantic_plan.models import (
    AggregationSpec,
    ExpressionSpec,
    OrderSpec,
    SemanticQueryPlan,
)
from txt2sql.semantic_plan.validator import validate_semantic_plan


def test_semantic_plan_supports_stddev() -> None:
    plan = try_heuristic_plan("해운대구 건물 높이 평균과 표준편차")
    assert plan is not None
    functions = [item.function for item in plan.aggregations]
    assert "stddev" in functions
    assert "avg" in functions


def test_semantic_plan_supports_percentile() -> None:
    plan = try_heuristic_plan("사하구 공장 연면적 상위 10% 경계값(90백분위)")
    assert plan is not None
    aggs = [item for item in plan.aggregations if item.function == "percentile"]
    assert aggs
    agg = aggs[0]
    assert agg.function == "percentile"
    assert abs((agg.percentile or 0) - 0.9) < 1e-9


def test_semantic_plan_supports_field_ratio_expression() -> None:
    plan = try_heuristic_plan("수영구 숙박시설 중 연면적 대비 건축면적 비(평균 A12/A14)")
    assert plan is not None
    exprs = [item.expression for item in plan.aggregations if item.expression is not None]
    assert exprs
    assert exprs[0].kind == "divide"


def test_semantic_plan_preserves_ratio_denominator() -> None:
    plan = try_heuristic_plan("영도구 15층 이상 건물 중 공동주택 비율 %")
    assert plan is not None
    assert plan.ratios
    ratio = plan.ratios[0]
    assert ratio.denominator_predicate is not None
    assert ratio.numerator_predicate is not None


def test_semantic_plan_supports_multiple_ratios() -> None:
    plan = try_heuristic_plan("해운대구 건물 중 높이 50m 이상 비율과 20층 이상 비율")
    assert plan is not None
    assert len(plan.ratios) == 2


def test_validator_allows_order_by_aggregation_alias() -> None:
    plan = SemanticQueryPlan(
        query_kind="aggregate",
        entity="building",
        aggregations=[AggregationSpec(function="count", alias="n")],
        group_by=["structure"],
        order_by=[OrderSpec(field="n", direction="desc")],
        limit=6,
    )
    result = validate_semantic_plan(plan, "구조별 건수 상위 6")
    assert result.status != "fallback"
    assert not any("unknown field: n" in e for e in result.errors)


def test_validator_blocks_aggregate_when_contract_group_is_dropped() -> None:
    plan = SemanticQueryPlan(
        query_kind="aggregate",
        entity="building",
        aggregations=[AggregationSpec(function="count", alias="n")],
    )
    result = validate_semantic_plan(plan, "용도별 건수")
    assert result.status == "fallback"
    assert "missing_group" in result.errors


def test_validator_requires_percentile_value() -> None:
    plan = SemanticQueryPlan(
        query_kind="aggregate",
        entity="building",
        aggregations=[
            AggregationSpec(function="percentile", field="height_m", percentile=None)
        ],
    )
    result = validate_semantic_plan(plan, "높이 백분위")
    assert result.status == "fallback"


def test_validator_rejects_divide_without_denominator() -> None:
    plan = SemanticQueryPlan(
        query_kind="aggregate",
        entity="building",
        aggregations=[
            AggregationSpec(
                function="avg",
                expression=ExpressionSpec(
                    kind="divide",
                    left=ExpressionSpec(kind="field", field="building_area_m2"),
                    right=None,
                ),
                alias="avg_ratio",
            )
        ],
    )
    result = validate_semantic_plan(plan, "건축면적 대비")
    assert result.status == "fallback"
