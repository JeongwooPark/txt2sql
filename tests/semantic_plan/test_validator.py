from txt2sql.semantic_plan.models import FilterSpec, PlaceSpec, ScopeSpec, SemanticQueryPlan
from txt2sql.semantic_plan.validator import validate_semantic_plan


def test_unknown_field_falls_back() -> None:
    plan = SemanticQueryPlan(
        query_kind="list",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="해운대구", kind="gu")),
        filters=[FilterSpec(field="시가총액", operator="eq", value=1)],
        select=["name"],
    )
    result = validate_semantic_plan(plan, "해운대구 건물의 시가총액")
    assert result.status == "fallback"
    assert any("unknown field" in e for e in result.errors)


def test_contains_on_height_falls_back() -> None:
    plan = SemanticQueryPlan(
        query_kind="list",
        entity="building",
        filters=[FilterSpec(field="height_m", operator="contains", value="100")],
        select=["name"],
    )
    result = validate_semantic_plan(plan, "높이 포함")
    assert result.status == "fallback"


def test_bare_area_clarifies() -> None:
    plan = SemanticQueryPlan(
        query_kind="rank",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="해운대구", kind="gu")),
        select=["name"],
    )
    result = validate_semantic_plan(plan, "면적이 가장 큰 건물")
    assert result.status == "clarify"


def test_age_question_falls_back() -> None:
    plan = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="금정구", kind="gu")),
    )
    result = validate_semantic_plan(plan, "금정구에서 30년 넘은 건물 몇 채")
    assert result.status == "fallback"
