"""Logical planner tests."""

from txt2sql.planner.logical import build_logical_plan
from txt2sql.query_ir.models import AggregationIR, DimensionIR, MeasureIR, PredicateIR, QueryIR, ScopeIR


def test_logical_plan_scan_filter_aggregate() -> None:
    ir = QueryIR(
        task="aggregate",
        entity="building",
        scope=ScopeIR(place="동래구"),
        predicates=[PredicateIR(field="usage", operator="eq", value="공동주택")],
        measures=[MeasureIR(concept="gross_floor_area_m2")],
        aggregations=[AggregationIR(function="avg", field="gross_floor_area_m2")],
    )
    plan = build_logical_plan(ir)
    assert plan.root.op in {"Aggregate", "Group", "Sort", "Limit", "Project"}
    ops = []
    node = plan.root
    while True:
        ops.append(node.op)
        if not node.children:
            break
        node = node.children[0]
    assert "Scan" in ops
    assert "Filter" in ops
    assert "Aggregate" in ops


def test_group_aggregate() -> None:
    ir = QueryIR(
        task="group",
        aggregations=[AggregationIR(function="count")],
        dimensions=[DimensionIR(field="usage")],
    )
    plan = build_logical_plan(ir)
    assert plan.status in {"READY", "REPLAN"}
    text = str(plan.root)
    # walk
    ops = []
    stack = [plan.root]
    while stack:
        n = stack.pop()
        ops.append(n.op)
        stack.extend(n.children)
    assert "Group" in ops


def test_ratio_percentile_nodes() -> None:
    ir = QueryIR(
        task="aggregate",
        aggregations=[
            AggregationIR(function="percentile", field="height_m", percentile=0.9),
            AggregationIR(function="ratio", has_denominator=True),
        ],
    )
    plan = build_logical_plan(ir)
    ops = []
    stack = [plan.root]
    while stack:
        n = stack.pop()
        ops.append(n.op)
        stack.extend(n.children)
    assert "Percentile" in ops
    assert "Ratio" in ops


def test_unresolved_blocks_ready() -> None:
    ir = QueryIR(task="aggregate", aggregations=[AggregationIR(function="avg", field=None)])
    plan = build_logical_plan(ir)
    assert plan.status in {"REPLAN", "CLARIFY", "UNSUPPORTED"}
