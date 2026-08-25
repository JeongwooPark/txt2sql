from llm2sql.profile_qa import is_profile_question
from llm2sql.query_understanding.contract import extract_contract
from llm2sql.route_capability import (
    PROFILE,
    fully_supports,
    select_execution_path,
)


def test_contract_detects_group_rank_projection() -> None:
    q = "사상구 공장 구조별 평균 연면적 상위 6개와 건수"
    contract = extract_contract(q)
    assert "structure" in contract.group_fields
    assert contract.limit == 6
    assert contract.order_requests
    assert any(item.function == "avg" for item in contract.aggregation_requests)
    assert any(item.function == "count" for item in contract.aggregation_requests)
    assert contract.operation in {"group_rank", "rank", "aggregate"}


def test_contract_detects_percentile() -> None:
    c = extract_contract("사하구 공장 연면적 상위 10% 경계값(90백분위)")
    assert c.percentile_requests
    assert abs(c.percentile_requests[0].percentile - 0.9) < 1e-9


def test_contract_detects_conditional_ratio() -> None:
    c = extract_contract("영도구 15층 이상 건물 중 공동주택 비율 %")
    assert c.ratios
    assert c.ratios[0].has_denominator


def test_contract_detects_derived_metric() -> None:
    c = extract_contract("수영구 숙박시설 중 연면적 대비 건축면적 비(평균 A12/A14)")
    assert c.derived_metrics
    assert c.derived_metrics[0].kind == "divide"


def test_profile_route_rejected_when_rank_required() -> None:
    q = "해운대구 용적율 상위 10개 공동주택의 이름·용적율·높이"
    contract = extract_contract(q)
    assert is_profile_question(q)
    assert not fully_supports(PROFILE, contract)


def test_complex_query_reaches_semantic_plan() -> None:
    q = "사상구 공장 구조별 건수와 평균 연면적 상위 6"
    assert select_execution_path(q) == "semantic_plan"


def test_simple_count_stays_deterministic() -> None:
    q = "해운대구 건물 몇 채야"
    path = select_execution_path(q)
    assert path != "semantic_plan"
