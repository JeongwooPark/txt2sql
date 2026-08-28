"""Fast path / D010 / D198 / spatial selection."""

from txt2sql.planner.logical import build_logical_plan
from txt2sql.planner.physical import select_physical_plan
from txt2sql.query_ir.models import AggregationIR, QueryIR
from txt2sql.semantic_catalog.binding import SemanticBinding


def test_d010_selection() -> None:
    ir = QueryIR(task="aggregate", aggregations=[AggregationIR(function="avg", field="height_m")])
    logical = build_logical_plan(ir)
    logical.status = "READY"
    logical.reason_codes = []
    physical = select_physical_plan(logical)
    assert physical.strategy in {"D010_EXECUTOR", "FAST_SIMPLE_COUNT", "FAST_THRESHOLD", "GENERIC_SQL_EXECUTOR"}


def test_d198_selection() -> None:
    ir = QueryIR(task="group", aggregations=[AggregationIR(function="count")])
    logical = build_logical_plan(ir)
    logical.status = "READY"
    logical.bindings = [
        SemanticBinding(
            concept="building.usage",
            dataset="building_attr_d198",
            physical_field="usage",
            grain="building_attr",
            confidence=0.8,
            reason="test",
        )
    ]
    physical = select_physical_plan(logical)
    assert physical.strategy == "D198_EXECUTOR"


def test_d198_wins_over_d010_when_both_bound() -> None:
    ir = QueryIR(task="count", aggregations=[AggregationIR(function="count")])
    logical = build_logical_plan(ir)
    logical.status = "READY"
    logical.bindings = [
        SemanticBinding(
            concept="building.approval_date",
            dataset="building_attr_d198",
            physical_field="approval_date",
            grain="building_attr",
            confidence=0.9,
            reason="test",
        ),
        SemanticBinding(
            concept="building.height",
            dataset="building_gis_d010",
            physical_field="height_m",
            grain="building_unit",
            confidence=0.5,
            reason="test",
        ),
    ]
    physical = select_physical_plan(logical)
    assert physical.strategy == "D198_EXECUTOR"
