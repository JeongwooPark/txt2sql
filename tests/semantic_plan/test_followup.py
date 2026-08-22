from llm2sql.semantic_plan.followup import (
    apply_plan_delta,
    is_semantic_plan_followup,
    parse_followup_delta,
)
from llm2sql.semantic_plan.models import (
    FilterSpec,
    PlaceSpec,
    ScopeSpec,
    SemanticQueryPlan,
)
from llm2sql.session import SessionContext


def _base_plan() -> SemanticQueryPlan:
    return SemanticQueryPlan(
        query_kind="rank",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="해운대구", kind="gu")),
        filters=[FilterSpec(field="usage", operator="eq", value="공동주택")],
        select=["name", "gross_floor_area_m2"],
        order_by=[],
        limit=20,
    )


def test_add_filter_height() -> None:
    delta = parse_followup_delta("그중 100m 이상만")
    assert delta is not None
    assert any(item.field == "height_m" for item in delta.add_filters)
    merged = apply_plan_delta(_base_plan(), delta)
    fields = {item.field for item in merged.filters}
    assert "usage" in fields
    assert "height_m" in fields


def test_change_sort_and_limit() -> None:
    sort_delta = parse_followup_delta("높이 순으로 바꿔")
    assert sort_delta is not None and sort_delta.change_sort
    assert sort_delta.change_sort[0].field == "height_m"
    merged = apply_plan_delta(_base_plan(), sort_delta)
    assert merged.query_kind == "rank"
    assert merged.order_by[0].field == "height_m"

    limit_delta = parse_followup_delta("10개만 보여줘")
    assert limit_delta is not None
    assert limit_delta.change_limit == 10
    merged2 = apply_plan_delta(merged, limit_delta)
    assert merged2.limit == 10


def test_followup_merge_keeps_ready_score() -> None:
    from llm2sql.semantic_plan.validator import validate_semantic_plan

    delta = parse_followup_delta("건물명과 지번도 같이")
    assert delta is not None
    merged = apply_plan_delta(_base_plan(), delta)
    assert "name" in merged.select
    assert "lot_address" in merged.select
    checked = validate_semantic_plan(merged, "건물명과 지번도 같이")
    assert checked.status == "ready"
    assert checked.score >= 0.85


def test_followup_gate_keeps_new_place_independent() -> None:
    session = SessionContext()
    session.last_semantic_plan = _base_plan().model_dump()
    session.last_semantic_plan_route = "semantic_plan_rank"
    session.last_route = "semantic_plan_rank"
    assert is_semantic_plan_followup("그중 높이 순으로", session)
    assert not is_semantic_plan_followup("금정구 아파트가 몇 채야?", session)


def test_followup_from_router_d010_sql() -> None:
    session = SessionContext()
    session.last_sql = (
        'SELECT "A0" FROM "AL_D010_26_20250704" '
        "WHERE \"A4\" LIKE '%해운대구%' AND \"A9\" = '공동주택' "
        'ORDER BY "A14" DESC NULLS LAST LIMIT 20;'
    )
    session.last_route = "building_rank_연면적"
    session.last_full_question = "해운대구 아파트 중 연면적이 큰 20개 보여줘"
    assert is_semantic_plan_followup("그중 높이 80m 이상만", session)
    assert is_semantic_plan_followup("10개만 보여줘", session)
