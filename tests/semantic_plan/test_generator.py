from llm2sql.semantic_plan.generator import parse_plan_json, try_heuristic_plan
from llm2sql.semantic_plan.models import SemanticPlanGenerationError


def test_parse_rejects_physical_column() -> None:
    raw = '{"query_kind":"list","entity":"building","select":["A16"]}'
    try:
        parse_plan_json(raw)
    except SemanticPlanGenerationError:
        return
    raise AssertionError("physical column should be rejected")


def test_parse_rejects_sql() -> None:
    raw = '{"query_kind":"list","entity":"building","select":["name"],"assumptions":["SELECT * FROM t"]}'
    try:
        parse_plan_json(raw)
    except SemanticPlanGenerationError:
        return
    raise AssertionError("SQL leak should be rejected")


def test_heuristic_mvp_height_list() -> None:
    plan = try_heuristic_plan(
        "해운대구 아파트 중 높이 70m 이상인 건물 이름과 높이"
    )
    assert plan is not None
    assert plan.entity == "building"
    assert plan.scope is not None and plan.scope.place is not None
    assert plan.scope.place.name == "해운대구"
    fields = {item.field for item in plan.filters}
    assert "usage" in fields
    assert "height_m" in fields
    assert "name" in plan.select
    assert "height_m" in plan.select


def test_heuristic_ambiguous_area() -> None:
    plan = try_heuristic_plan("면적이 가장 큰 건물")
    assert plan is not None
    assert plan.requires_clarification is True
