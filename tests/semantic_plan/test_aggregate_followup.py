"""Phase 6.4 aggregate follow-up fixtures (Q500 pattern)."""

from txt2sql.followup_qa import (
    is_aggregate_value_top_followup,
    try_add_avg_to_group_followup,
    try_aggregate_top_value_followup,
    try_group_prior_result_followup,
)
from txt2sql.semantic_plan.followup import apply_aggregate_followup
from txt2sql.semantic_plan.models import AggregationSpec, SemanticQueryPlan
from txt2sql.session import SessionContext


def test_aggregate_value_top_detected() -> None:
    assert is_aggregate_value_top_followup("가장 큰 값 하나만")
    assert not is_aggregate_value_top_followup("가장 큰 건물 하나만")


def test_group_prior_result_preserves_where() -> None:
    session = SessionContext(
        last_sql=(
            'SELECT COUNT(*) AS "count"\n'
            'FROM "AL_D010_26_20250704" b\n'
            'WHERE b."A4" LIKE \'%동래구%\' AND b."A16"::float8 >= 50;'
        ),
        last_route="followup_count_display",
    )
    routed = try_group_prior_result_followup("그 결과를 법정동별로 묶어줘", session)
    assert routed is not None
    assert "GROUP BY" in routed.sql.upper()
    assert "동래구" in routed.sql
    assert "COUNT(*)" in routed.sql.upper()


def test_aggregate_top_value_orders_by_avg() -> None:
    session = SessionContext(
        last_sql=(
            'SELECT b."A4" AS "legal_dong", COUNT(*) AS "n", '
            'AVG(b."A16"::float8) AS "avg_h"\n'
            'FROM "AL_D010_26_20250704" b\n'
            'WHERE b."A4" LIKE \'%동래구%\'\n'
            'GROUP BY b."A4";'
        ),
        last_route="semantic_plan_aggregate",
    )
    routed = try_aggregate_top_value_followup("가장 큰 값 하나만", session)
    assert routed is not None
    assert 'ORDER BY "avg_h" DESC' in routed.sql
    assert "LIMIT 1" in routed.sql.upper()


def test_add_avg_to_group_sql() -> None:
    session = SessionContext(
        last_sql=(
            'SELECT b."A4" AS "legal_dong", COUNT(*) AS "n"\n'
            'FROM "AL_D010_26_20250704" b\n'
            'WHERE b."A4" LIKE \'%동래구%\' AND b."A16"::float8 >= 50\n'
            'GROUP BY b."A4"\n'
            'ORDER BY "n" DESC NULLS LAST;'
        ),
        last_question="그중 높이 50m 이상만",
        last_route="semantic_plan_aggregate",
    )
    routed = try_add_avg_to_group_followup("평균도 같이 계산해줘", session)
    assert routed is not None
    assert 'AVG(b."A16"' in routed.sql
    assert '"avg_h"' in routed.sql


def test_apply_aggregate_adds_avg_height() -> None:
    plan = SemanticQueryPlan.model_validate(
        {
            "entity": "building",
            "query_kind": "aggregate",
            "group_by": ["legal_dong"],
            "aggregations": [{"function": "count", "alias": "n"}],
            "filters": [],
        }
    )
    session = SessionContext(
        last_sql='SELECT COUNT(*) FROM t WHERE "A16" >= 50',
        last_question="그중 높이 50m 이상만",
    )
    merged = apply_aggregate_followup("평균도 같이 계산해줘", plan, session)
    fns = [a.function for a in merged.aggregations]
    fields = [a.field for a in merged.aggregations if a.field]
    assert "avg" in fns
    assert "height_m" in fields
