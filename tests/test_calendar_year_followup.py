from llm2sql.answer import _natural_threshold_list, _subject_phrase
from llm2sql.followup_qa import is_subset_followup, try_subset_followup
from llm2sql.intent_router import try_route
from llm2sql.session import SessionContext

_LAST_SQL = """
SELECT b."A0", b."A4", b."A5", b."A9", b."A12", b."A14", b."A16", b."A24", b."A26",
       COUNT(*) OVER() AS total_n
FROM "AL_D010_26_20250704" b
JOIN "BND_ADM_DONG_PG" d
  ON ST_Intersects(b.geometry, d.geometry)
WHERE d."ADM_NM" = '구서1동' AND d."ADM_CD" LIKE '21%' AND b."A14" >= 330.5785 AND b."A14" <= 661.157
ORDER BY b."A14" DESC NULLS LAST
LIMIT 100;
""".strip()


def _area_session() -> SessionContext:
    session = SessionContext()
    session.last_question = "구서1동에서 면적이 100평이상 200평이하 건물을 찾아라"
    session.last_full_question = session.last_question
    session.last_route = "building_area_threshold_list"
    session.last_sql = _LAST_SQL
    session.last_rows = [{"A24": "국도빌라", "A14": 659.84}]
    return session


def test_subset_followup_injects_calendar_year() -> None:
    session = _area_session()
    q = "이 중에 2000년 이후 건물은?"
    assert is_subset_followup(q, session)
    routed = try_subset_followup(q, session)
    assert routed is not None
    sql = routed.sql
    assert "JOIN" in sql
    assert "BND_ADM_DONG_PG" in sql
    assert "330.5785" in sql
    assert "661.157" in sql
    assert ">= '2000'" in sql
    assert 'b."A13"' in sql
    assert "LIMIT 100" in sql.upper()
    assert 'AL_D198' not in sql


def test_router_area_range_plus_calendar_year() -> None:
    from llm2sql.route_capability import select_execution_path
    from llm2sql.semantic_plan.compiler import compile_semantic_plan
    from llm2sql.semantic_plan.generator import try_heuristic_plan

    q = "구서1동에서 면적이 100평이상 200평이하 2000년 이후 건물을 찾아라"
    assert select_execution_path(q) == "semantic_plan"
    plan = try_heuristic_plan(q)
    assert plan is not None
    fields = {item.field for item in plan.filters}
    assert "approval_date" in fields
    assert "gross_floor_area_m2" in fields or "building_area_m2" in fields
    sql = compile_semantic_plan(plan).sql
    assert "2000" in sql
    assert '"A34"' not in sql
    phrase = _subject_phrase(q)
    assert "2000년 이후" in phrase
    assert "이상" in phrase
    assert "이하" in phrase


_MAP_SQL = """
SELECT COUNT(*) AS cnt
FROM "AL_D010_26_20250704"
WHERE "A3" LIKE '26410%';
""".strip()


def _map_session() -> SessionContext:
    session = SessionContext()
    session.last_question = "금정구 건물을 표시하라"
    session.last_full_question = session.last_question
    session.last_route = "building_map_display"
    session.last_sql = _MAP_SQL
    session.last_rows = [{"cnt": 38794}]
    return session


def test_subset_map_display_year_without_space() -> None:
    session = _map_session()
    q = "이중에 2000년 이후에 지어진 건물은?"
    assert is_subset_followup(q, session)
    routed = try_subset_followup(q, session)
    assert routed is not None
    sql = routed.sql
    assert routed.intent == "building_map_display"
    assert "COUNT(" in sql.upper()
    assert "26410" in sql
    assert ">= '2000'" in sql
    assert '"A13"' in sql
    assert "COUNT(*) OVER" not in sql.upper()
    assert "AL_D198" not in sql
    select_head = sql.split("FROM", 1)[0].upper()
    assert "A13" not in select_head


def test_name_lookup_does_not_steal_year_followup() -> None:
    from llm2sql.domain import looks_like_building_name_lookup
    from llm2sql.intent_router import try_route

    q = "이중에 2000년 이후에 지어진 건물은?"
    assert not looks_like_building_name_lookup(q)
    routed = try_route(q)
    assert routed is None or routed.intent != "building_name_lookup"


def test_threshold_list_mentions_approval_when_year_asked() -> None:
    q = "구서1동 건물 연면적 100평 이상 200평 이하 2000년 이후"
    text = _natural_threshold_list(
        q,
        sql='SELECT b."A14", b."A13"',
        rows=[{"A24": "국도빌라", "A14": 659.84, "A13": "20010315", "total_n": 1}],
        row_count=1,
        route="building_area_threshold_list",
    )
    assert "2000년 이후" in text
    assert "사용승인" in text
    assert "국도빌라" in text
