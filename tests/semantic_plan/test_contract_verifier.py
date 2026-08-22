from llm2sql.query_understanding.contract import extract_contract
from llm2sql.semantic_plan.contract_verifier import verify_contract
from llm2sql.semantic_plan.generator import try_heuristic_plan
from llm2sql.semantic_plan.models import (
    AggregationSpec,
    FilterSpec,
    PlaceSpec,
    ScopeSpec,
    SemanticQueryPlan,
)


def test_missing_not_is_hard_fail() -> None:
    plan = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="동래구", kind="gu")),
        filters=[FilterSpec(field="usage", operator="eq", value="공동주택")],
    )
    result = verify_contract("동래구 공동주택 제외한 건물 수", plan)
    assert result.ok is False
    assert result.hard_fail is True
    assert "P04" in result.reasons


def test_slot_below_threshold_blocks_even_if_overall_high() -> None:
    plan = SemanticQueryPlan(
        query_kind="aggregate",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="해운대구", kind="gu")),
        aggregations=[AggregationSpec(function="avg", field="height_m", alias="avg_height_m")],
        model_confidence=0.99,
    )
    result = verify_contract("해운대구 건물 높이 합계", plan, min_slot=0.85)
    assert result.ok is False
    assert any("slot_below_threshold" in item or "P05" in item for item in result.reasons)


def test_complete_sum_plan_passes() -> None:
    q = "해운대구 건물 높이 합계"
    plan = try_heuristic_plan(q)
    assert plan is not None
    result = verify_contract(q, plan)
    assert result.ok is True
    assert result.confidence.aggregation >= 0.85
