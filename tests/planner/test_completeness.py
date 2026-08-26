"""Completeness / temporal planner tests."""

from txt2sql.planner.logical import build_logical_plan
from txt2sql.planner.validate import validate_logical_plan
from txt2sql.query_ir.models import AggregationIR, QueryIR, TemporalIR, UnresolvedIR


def test_completeness_clarify() -> None:
    ir = QueryIR(
        task="count",
        unresolved=[UnresolvedIR(code="CLARIFY_PLACE", message="어느 구?")],
        aggregations=[AggregationIR(function="count")],
    )
    plan = build_logical_plan(ir)
    assert validate_logical_plan(plan) == "CLARIFY"


def test_temporal_plan_node() -> None:
    ir = QueryIR(
        task="count",
        temporal=TemporalIR(field="approval_date", operator="gte", value="2000"),
        aggregations=[AggregationIR(function="count")],
    )
    plan = build_logical_plan(ir)
    ops = []
    stack = [plan.root]
    while stack:
        n = stack.pop()
        ops.append(n.op)
        stack.extend(n.children)
    assert "TemporalFilter" in ops
