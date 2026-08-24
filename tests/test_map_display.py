from llm2sql.answer import format_map_display_answer, format_success_template
from llm2sql.domain import wants_map_display
from llm2sql.intent_router import try_route
from llm2sql.map.sql import plan_map_sql
from llm2sql.profile_qa import is_profile_question
from llm2sql.semantic_plan.answer import format_semantic_answer
from llm2sql.semantic_plan.generator import try_heuristic_plan


def test_wants_map_display_geumjeong() -> None:
    q = "금정구 건물데이터를 표시하라"
    assert wants_map_display(q)
    assert not wants_map_display("구서1동에서 면적이 100평이상 200평이하 건물을 찾아라")
    assert not wants_map_display("연면적 표시명이 뭐야")
    assert not wants_map_display("차트로 표시해줘")


def test_router_map_display_is_count_not_list() -> None:
    q = "금정구 건물데이터를 표시하라"
    routed = try_route(q)
    assert routed is not None
    assert routed.intent == "building_map_display"
    assert "COUNT(" in routed.sql.upper()
    assert "26410" in routed.sql
    assert "%금정구%" not in routed.sql
    assert "LIMIT 100" not in routed.sql.upper()


def test_map_plan_features_not_boundary() -> None:
    q = "금정구 건물데이터를 표시하라"
    routed = try_route(q)
    assert routed is not None
    plan = plan_map_sql(
        question=q,
        sql=routed.sql,
        route=routed.intent,
        ok=True,
        map_limit=2000,
    )
    assert plan is not None
    assert plan.kind == "features"
    assert "geometry" in plan.sql.lower()
    assert "AL_D010" in plan.sql
    assert "LIMIT 2000" in plan.sql.upper()


def test_answer_does_not_list_addresses() -> None:
    q = "금정구 건물데이터를 표시하라"
    text = format_success_template(
        q,
        sql='SELECT COUNT(*) AS cnt FROM "AL_D010_26_20250704"',
        rows=[{"cnt": 12345}],
        row_count=1,
        route="building_map_display",
    )
    assert "지도에 표출" in text
    assert "두구동" not in text
    assert "1." not in text


def test_published_map_mentions_cap() -> None:
    q = "금정구 건물데이터를 표시하라"
    text = format_map_display_answer(
        q,
        rows=[{"cnt": 40000}],
        map_info={"available": True, "feature_count": 2000},
        include_map=True,
    )
    assert "지도에 표출" in text
    assert "2,000" in text
    assert "40,000" in text


def test_map_display_keeps_calendar_year() -> None:
    q = "금정구 2000년 이후 건물을 표시하라"
    routed = try_route(q)
    assert routed is not None
    assert routed.intent == "building_map_display"
    assert "COUNT(" in routed.sql.upper()
    assert "26410" in routed.sql
    assert ">= '2000'" in routed.sql
    assert '"A13"' in routed.sql
    plan = plan_map_sql(
        question=q,
        sql=routed.sql,
        route=routed.intent,
        ok=True,
        map_limit=2000,
    )
    assert plan is not None
    assert plan.kind == "features"
    assert ">= '2000'" in plan.sql
    assert '"A13"' in plan.sql


def test_map_followup_answer_mentions_year() -> None:
    text = format_map_display_answer(
        "금정구 건물을 표시하라 중에서 2000년 이후에 지어진 건물은?",
        rows=[{"cnt": 12000}],
        map_info={"available": True, "feature_count": 2000},
        include_map=True,
    )
    assert "2000년 이후" in text
    assert "12,000" in text
    assert "2,000" in text


def test_profile_does_not_steal_display() -> None:
    assert not is_profile_question("금정구 건물데이터를 표시하라")


def test_sqp_guesses_count_for_display() -> None:
    q = "금정구 건물데이터를 표시하라"
    plan = try_heuristic_plan(q)
    assert plan is not None
    assert plan.query_kind == "count"
    text = format_semantic_answer(
        q,
        plan=plan,
        rows=[{"count": 100}],
        row_count=1,
    )
    assert "지도에 표출" in text
    assert "조회했습니다" not in text or "표출" in text
