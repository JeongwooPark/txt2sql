"""Unit tests for temporal + group semantic-v2 follow-up fixes."""

from __future__ import annotations

from txt2sql.planner.executor_adapter import build_execution_plan
from txt2sql.planner.semantic_executor import (
    build_sqp,
    compile_sql_from_bundle,
    should_try_semantic_v2,
)
from txt2sql.query_understanding.temporal import parse_temporal_filters


def test_recent_years_parses_as_relative_date_not_age() -> None:
    filters = parse_temporal_filters("장전1동에서 최근 10년 내 준공된 건물은 몇 채야?")
    assert len(filters) == 1
    assert filters[0].operator == "gt"
    assert filters[0].value == "rel_years:10"


def test_permit_date_not_approval_date() -> None:
    q = "금정구에서 허가일이 1995년 이전인 건물 수는?"
    bundle = build_execution_plan(q)
    assert bundle.logical.status == "READY"
    assert should_try_semantic_v2(bundle) is True
    sql, _ = compile_sql_from_bundle(bundle, question=q)
    assert "A33" in sql
    assert "A34" not in sql
    # No conflicting dual date predicates.
    assert sql.lower().count("a33") >= 1


def test_temporal_count_ready_and_d198() -> None:
    q = "금정구에서 2000년 이전 사용승인된 건물 수는?"
    bundle = build_execution_plan(q)
    assert bundle.logical.status == "READY"
    assert bundle.query_ir.temporal is not None
    assert bundle.query_ir.temporal.field == "approval_date"
    assert should_try_semantic_v2(bundle) is True
    sql, _ = compile_sql_from_bundle(bundle, question=q)
    assert "AL_D198" in sql
    assert "A34" in sql or "a34" in sql.lower()


def test_group_structure_avg_ready_and_order() -> None:
    q = "동래구 구조별 평균 높이를 구해줘"
    bundle = build_execution_plan(q)
    assert bundle.logical.status == "READY"
    assert any(d.field == "structure" for d in bundle.query_ir.dimensions)
    assert should_try_semantic_v2(bundle) is True
    plan = build_sqp(bundle.query_ir, question=q)
    assert plan.group_by
    assert plan.order_by
    assert plan.order_by[0].field != "count" or any(
        a.function == "count" for a in plan.aggregations
    )
    sql, _ = compile_sql_from_bundle(bundle, question=q)
    assert "GROUP BY" in sql.upper()
    assert "AVG" in sql.upper()
