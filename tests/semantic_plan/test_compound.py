from llm2sql.intent_router import should_defer_compound_to_plan, try_route
from llm2sql.semantic_plan.compiler import compile_semantic_plan
from llm2sql.semantic_plan.generator import try_heuristic_plan
from llm2sql.semantic_plan.normalizer import normalize_semantic_plan
from llm2sql.semantic_plan.validator import validate_semantic_plan


def _sql(question: str) -> str:
    plan = try_heuristic_plan(question)
    assert plan is not None
    plan = normalize_semantic_plan(plan, question)
    checked = validate_semantic_plan(plan, question)
    assert checked.status == "ready", checked.errors
    return compile_semantic_plan(checked.plan).sql


def test_router_keeps_simple_area_count() -> None:
    q = "해운대구 공동주택 중 건축면적이 1000㎡ 이상인 건물 수"
    assert not should_defer_compound_to_plan(q)
    routed = try_route(q)
    assert routed is not None
    assert routed.intent == "building_area_threshold_count"


def test_router_misses_height_and_gfa() -> None:
    q = "해운대구 아파트 중 높이 70m 이상이고 연면적 10000㎡ 이상인 건물 이름과 높이"
    assert should_defer_compound_to_plan(q)
    assert try_route(q) is None
    sql = _sql(q)
    assert '"A16"' in sql
    assert '"A14"' in sql
    assert "공동주택" in sql


def test_router_misses_spatial_inside_rank() -> None:
    q = "연산동 안에 있는 공동주택 중 연면적 상위 10개"
    assert should_defer_compound_to_plan(q)
    assert try_route(q) is None
    sql = _sql(q)
    assert "ST_Intersects" in sql
    assert "BND_ADM" in sql
    assert "LIMIT 10" in sql.upper()


def test_router_misses_buffer_plus_height() -> None:
    q = "구서동 주변 500m 이내에 있는 공동주택 중 높이 40m 이상"
    assert should_defer_compound_to_plan(q)
    assert try_route(q) is None
    sql = _sql(q)
    assert "ST_DWithin" in sql
    assert '"A16"' in sql


def test_heuristic_floor_without_prefix() -> None:
    plan = try_heuristic_plan("금정구에서 연면적 5000㎡ 이상이고 15층 이상인 철근콘크리트 건물")
    assert plan is not None
    fields = {item.field for item in plan.filters}
    assert "gross_floor_area_m2" in fields
    assert "ground_floors" in fields
    assert "structure" in fields


def test_router_list_when_names_requested() -> None:
    q = "강서구 공장 중 연면적 5000㎡ 이상인 건물 이름과 연면적"
    assert not should_defer_compound_to_plan(q)
    routed = try_route(q)
    assert routed is not None
    assert routed.intent == "building_area_threshold_list"
    assert "AS cnt" not in routed.sql
    assert "A24" in routed.sql
