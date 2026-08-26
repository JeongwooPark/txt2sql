from txt2sql.planner.semantic_executor import build_sqp, should_try_semantic_v2
from txt2sql.planner.executor_adapter import build_execution_plan
from txt2sql.query_ir.models import AggregationIR, DimensionIR, QueryIR, ScopeIR, TemporalIR
from txt2sql.semantic_plan.compiler import compile_semantic_plan
from txt2sql.semantic_plan.models import FilterSpec
from txt2sql.query_ir.adapters import query_ir_to_semantic_plan


def test_temporal_ir_maps_to_filter() -> None:
    ir = QueryIR(
        task="count",
        entity="building",
        scope=ScopeIR(place="금정구"),
        temporal=TemporalIR(field="approval_date", operator="gte", value=2000),
    )
    plan = query_ir_to_semantic_plan(ir)
    assert any(f.field == "approval_date" for f in plan.filters)


def test_building_age_compiles_age_or_extract() -> None:
    from txt2sql.semantic_plan.models import SemanticQueryPlan

    plan = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        filters=[FilterSpec(field="building_age_years", operator="gte", value=30)],
        aggregations=[],
    )
    # need count aggregation
    from txt2sql.semantic_plan.models import AggregationSpec

    plan.aggregations = [AggregationSpec(function="count")]
    sql = compile_semantic_plan(plan).sql.upper()
    assert "AGE(" in sql or "EXTRACT(YEAR" in sql


def test_group_stable_order() -> None:
    ir = QueryIR(
        task="distribution",
        entity="building",
        scope=ScopeIR(place="해운대구"),
        dimensions=[DimensionIR(field="usage")],
        aggregations=[AggregationIR(function="count")],
    )
    plan = build_sqp(ir)
    assert plan.group_by
    assert plan.order_by
    assert plan.order_by[0].direction == "desc"
    assert any(o.field == plan.group_by[0] for o in plan.order_by)


def test_rank_gets_limit() -> None:
    ir = QueryIR(
        task="rank",
        entity="building",
        scope=ScopeIR(place="해운대구"),
        aggregations=[AggregationIR(function="max", field="height_m")],
    )
    plan = build_sqp(ir)
    assert plan.limit == 10
    assert plan.order_by


def test_should_try_skips_fast_simple_count() -> None:
    bundle = build_execution_plan("해운대구 건물 몇 채야?")
    # May or may not be FAST depending on contract; if FAST, should_try is False
    if bundle.physical.strategy in {"FAST_SIMPLE_COUNT", "FAST_THRESHOLD"}:
        assert should_try_semantic_v2(bundle) is False
