"""Physical selection tests."""

import pytest

from txt2sql.planner.logical import build_logical_plan
from txt2sql.planner.physical import reject_partial_execution, select_physical_plan, PhysicalPlan
from txt2sql.query_ir.models import AggregationIR, PredicateIR, QueryIR, ScopeIR, SpatialIR


def test_fast_path_simple_count() -> None:
    ir = QueryIR(
        task="count",
        scope=ScopeIR(place="동래구"),
        aggregations=[AggregationIR(function="count")],
    )
    logical = build_logical_plan(ir)
    # force ready
    logical.status = "READY"
    logical.reason_codes = []
    physical = select_physical_plan(logical)
    assert physical.strategy == "FAST_SIMPLE_COUNT"
    assert physical.partial is False


def test_fast_threshold() -> None:
    ir = QueryIR(
        task="count",
        predicates=[PredicateIR(field="height_m", operator="gte", value=50)],
        aggregations=[AggregationIR(function="count")],
    )
    logical = build_logical_plan(ir)
    logical.status = "READY"
    logical.reason_codes = []
    physical = select_physical_plan(logical, question="높이 50m 이상 건물 몇 채")
    assert physical.strategy in {"D198_EXECUTOR", "FAST_THRESHOLD"}


def test_spatial_selection() -> None:
    ir = QueryIR(
        task="count",
        spatial=[SpatialIR(relation="within", target_place="해운대구")],
        aggregations=[AggregationIR(function="count")],
    )
    logical = build_logical_plan(ir)
    logical.status = "READY"
    physical = select_physical_plan(logical)
    assert physical.strategy == "SPATIAL_EXECUTOR"


def test_no_partial_coverage() -> None:
    ir = QueryIR(task="count", aggregations=[AggregationIR(function="count")])
    logical = build_logical_plan(ir)
    logical.status = "READY"
    physical = select_physical_plan(logical)
    reject_partial_execution(physical)
    bad = PhysicalPlan(
        strategy="FAST_SIMPLE_COUNT",
        logical=logical,
        cost=1,
        covered_ops=("Scan",),
        partial=False,
    )
    with pytest.raises(RuntimeError):
        reject_partial_execution(bad)
