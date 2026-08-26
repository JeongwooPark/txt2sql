from txt2sql.planner.semantic_executor import build_sqp, refine_query_ir_for_compile
from txt2sql.query_ir.models import AggregationIR, MeasureIR, QueryIR, ScopeIR
from txt2sql.semantic_plan.compiler import compile_semantic_plan


def test_scalar_aggregate_prefers_numeric_measure() -> None:
    ir = QueryIR(
        task="aggregate",
        entity="building",
        scope=ScopeIR(place="해운대구"),
        measures=[
            MeasureIR(concept="building.usage"),
            MeasureIR(concept="building.height"),
        ],
        aggregations=[AggregationIR(function="avg", field="usage")],
    )
    refined = refine_query_ir_for_compile(ir)
    assert refined.aggregations[0].field == "height_m"


def test_scalar_aggregate_compiles_avg_sql() -> None:
    ir = QueryIR(
        task="aggregate",
        entity="building",
        scope=ScopeIR(place="해운대구"),
        measures=[MeasureIR(concept="gross_floor_area_m2")],
        aggregations=[AggregationIR(function="avg", field="gross_floor_area_m2")],
    )
    plan = build_sqp(ir)
    compiled = compile_semantic_plan(plan)
    sql = compiled.sql.upper()
    assert "AVG(" in sql
    assert "SELECT" in sql


def test_scalar_grain_keeps_building_entity() -> None:
    ir = QueryIR(
        task="aggregate",
        entity="building",
        aggregations=[AggregationIR(function="avg", field="height_m")],
    )
    plan = build_sqp(ir)
    assert plan.entity == "building"
