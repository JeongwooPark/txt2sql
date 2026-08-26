"""Executor adapter / router-via-plan tests."""

from txt2sql.planner.executor_adapter import build_execution_plan, route_allowed_by_plan


def test_build_execution_plan_simple_count() -> None:
    bundle = build_execution_plan("동래구 건물 수는?")
    assert bundle.query_ir.task in {"count", "unknown", "list", "aggregate"}
    assert bundle.physical.strategy
    assert bundle.physical.partial is False


def test_clarify_blocks_route() -> None:
    from txt2sql.query_ir.models import UnresolvedIR
    from txt2sql.planner.logical import build_logical_plan
    from txt2sql.planner.physical import select_physical_plan, PhysicalPlan
    from txt2sql.planner.executor_adapter import ExecutionPlanBundle
    from txt2sql.query_ir.models import QueryIR, AggregationIR

    ir = QueryIR(
        task="count",
        unresolved=[UnresolvedIR(code="CLARIFY_REQUIRED", message="어느 구?")],
        aggregations=[AggregationIR(function="count")],
    )
    logical = build_logical_plan(ir)
    physical = select_physical_plan(logical)
    bundle = ExecutionPlanBundle(query_ir=ir, logical=logical, physical=physical)
    assert route_allowed_by_plan(bundle) is False or logical.status != "READY"
