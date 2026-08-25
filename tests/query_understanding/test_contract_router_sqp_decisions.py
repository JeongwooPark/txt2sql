"""Contract → Capability → Router/SQP 결정 케이스 A–F."""

from llm2sql.intent_router import try_route
from llm2sql.profile_qa import is_profile_question
from llm2sql.query_understanding.contract import extract_contract
from llm2sql.route_capability import (
    PROFILE,
    fully_supports,
    legacy_route_eligible,
    select_execution_path,
)
from llm2sql.semantic_plan.contract_verifier import verify_contract
from llm2sql.semantic_plan.generator import try_heuristic_plan


def test_case_a_simple_count_uses_router() -> None:
    q = "금정구 건축물은 몇 채야?"
    path = select_execution_path(q)
    assert path != "semantic_plan"
    routed = try_route(q)
    assert routed is not None
    assert legacy_route_eligible(routed.intent, extract_contract(q))


def test_case_b_group_multi_agg_uses_sqp() -> None:
    q = (
        "사상구 공장을 구조별로 나누고 "
        "건수와 평균 연면적을 구해서 "
        "평균 연면적 상위 6개를 보여줘"
    )
    contract = extract_contract(q)
    assert "structure" in contract.group_fields
    assert any(item.function == "count" for item in contract.aggregation_requests)
    assert any(item.function == "avg" for item in contract.aggregation_requests)
    assert contract.limit == 6
    assert select_execution_path(q) == "semantic_plan"
    plan = try_heuristic_plan(q, contract=contract)
    assert plan is not None
    assert "structure" in plan.group_by
    plan_fns = {item.function for item in plan.aggregations}
    assert "count" in plan_fns
    assert "avg" in plan_fns
    assert plan.limit == 6
    assert verify_contract(q, plan, contract=contract).ok is True


def test_case_c_conditional_ratio_uses_sqp() -> None:
    q = "15층 이상 건물 중 공동주택 비율"
    contract = extract_contract(q)
    assert contract.ratios
    assert contract.ratios[0].has_denominator
    assert select_execution_path(q) == "semantic_plan"
    plan = try_heuristic_plan(q, contract=contract)
    assert plan is not None
    assert plan.ratios
    assert plan.ratios[0].denominator_predicate is not None
    assert verify_contract(q, plan, contract=contract).ok is True


def test_case_d_percentile_uses_sqp_not_rank() -> None:
    q = "건물 높이 상위 10% 경계값"
    contract = extract_contract(q)
    assert contract.percentile_requests
    assert abs(contract.percentile_requests[0].percentile - 0.9) < 1e-9
    assert select_execution_path(q) == "semantic_plan"
    routed = try_route(q)
    if routed is not None:
        assert routed.intent.startswith("building_rank_")
        assert not legacy_route_eligible(routed.intent, contract)
    plan = try_heuristic_plan(q, contract=contract)
    assert plan is not None
    assert any(
        item.function == "percentile" and item.percentile is not None
        and abs(item.percentile - 0.9) < 1e-9
        for item in plan.aggregations
    )


def test_case_e_derived_metric_uses_typed_divide() -> None:
    q = "건축면적/연면적 비율의 평균"
    contract = extract_contract(q)
    assert contract.derived_metrics
    assert contract.derived_metrics[0].kind == "divide"
    assert select_execution_path(q) == "semantic_plan"
    plan = try_heuristic_plan(q, contract=contract)
    assert plan is not None
    divides = [
        item.expression
        for item in plan.aggregations
        if item.expression is not None and item.expression.kind == "divide"
    ]
    assert divides
    assert divides[0].left is not None and divides[0].left.field == "building_area_m2"
    assert divides[0].right is not None and divides[0].right.field == "gross_floor_area_m2"


def test_case_f_profile_does_not_execute_rank_projection() -> None:
    q = "해운대구 공동주택 용적률 상위 10개 이름과 높이"
    contract = extract_contract(q)
    assert is_profile_question(q)
    assert not fully_supports(PROFILE, contract)
    assert select_execution_path(q) != "building_profile"
    assert select_execution_path(q) == "semantic_plan"
    plan = try_heuristic_plan(q, contract=contract)
    assert plan is not None
    assert "name" in plan.select
    assert "height_m" in plan.select


def test_regression_simple_count_stays_router() -> None:
    assert select_execution_path("해운대구 건물 몇 채야") != "semantic_plan"


def test_regression_area_threshold_count_stays_router() -> None:
    q = "해운대구 공동주택 중 건축면적이 1000㎡ 이상인 건물 수"
    path = select_execution_path(q)
    assert path != "semantic_plan"
    routed = try_route(q)
    assert routed is not None
    assert routed.intent == "building_area_threshold_count"
