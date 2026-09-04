"""Phase 6 operator-level fixtures (not Q-ID hardcoding)."""

from txt2sql.intent_router import try_route
from txt2sql.query_ir import QueryIR, assess_completeness
from txt2sql.query_ir.models import AggregationIR, DimensionIR, ScopeIR


def test_group_task_requires_dimensions() -> None:
    ir = QueryIR(task="group", entity="building", scope=ScopeIR(place="동래구"))
    report = assess_completeness(ir)
    assert report.scope_binding == "FAIL"
    assert "SEMANTIC_INCOMPLETE_DIMENSION" in report.reasons


def test_group_with_dimensions_ready() -> None:
    ir = QueryIR(
        task="group",
        entity="building",
        scope=ScopeIR(place="동래구"),
        dimensions=[DimensionIR(field="legal_dong")],
        aggregations=[AggregationIR(function="count")],
    )
    report = assess_completeness(ir)
    assert report.status == "READY"


def test_industrial_admin_sig_group_route() -> None:
    q = "산업단지와 겹치는 행정동 수를 구·군별로 집계해줘"
    routed = try_route(q)
    assert routed is not None
    assert routed.intent == "industrial_admin_sig_group"
    assert "GROUP BY" in routed.sql.upper()


def test_d198_legal_dong_topn_route() -> None:
    q = "동래구에서 1980년 이전 준공 건물 수가 가장 많은 법정동 5곳을 보여줘"
    routed = try_route(q)
    assert routed is not None
    assert routed.intent == "d198_legal_dong_topn"
    assert "LIMIT 5" in routed.sql.upper()


def test_non_violation_count_route() -> None:
    from txt2sql.count_routes import match_priority_count_route

    q = "부산에서 위반건축물이 아닌 건물은 몇 채야?"
    hit = match_priority_count_route(q)
    assert hit is not None
    assert hit.intent == "non_violation_building_count"


def test_basic_zone_entity_completeness() -> None:
    ir = QueryIR(task="meta", entity="basic_zone")
    report = assess_completeness(ir)
    assert report.dataset_binding == "FAIL"
