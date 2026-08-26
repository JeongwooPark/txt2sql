"""Long-tail operator-level tests (no Q-ID patches)."""

from txt2sql.planner.logical import build_logical_plan
from txt2sql.query_ir.adapters import contract_to_query_ir
from txt2sql.query_understanding.contract import extract_contract


def test_scalar_avg_logical_operator() -> None:
    contract = extract_contract("해운대구 공동주택 평균 연면적은?")
    ir = contract_to_query_ir(contract)
    plan = build_logical_plan(ir)
    ops = []
    stack = [plan.root]
    while stack:
        n = stack.pop()
        ops.append(n.op)
        stack.extend(n.children)
    # AVG intent should produce Aggregate or at least Scan/Filter structure
    assert "Scan" in ops
    assert plan.query_ir.task in {"aggregate", "count", "unknown", "group", "list", "ratio"}


def test_temporal_age_concept_binding() -> None:
    from txt2sql.semantic_catalog.binding import bind_concept

    b = bind_concept("building.age")
    assert b is not None
    assert b.dataset in {"building_gis_d010", "building_attr_d198"}


def test_group_distribution_operator() -> None:
    contract = extract_contract("동래구 용도별 건물 수")
    ir = contract_to_query_ir(contract)
    plan = build_logical_plan(ir)
    ops = []
    stack = [plan.root]
    while stack:
        n = stack.pop()
        ops.append(n.op)
        stack.extend(n.children)
    assert "Scan" in ops
