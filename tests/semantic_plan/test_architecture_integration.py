from llm2sql.query_understanding.contract import extract_contract
from llm2sql.route_capability import select_execution_path
from llm2sql.semantic_plan.compiler import compile_semantic_plan
from llm2sql.semantic_plan.generator import try_heuristic_plan
from llm2sql.semantic_plan.normalizer import normalize_semantic_plan
from llm2sql.semantic_plan.validator import validate_semantic_plan


def _compile_question(question: str) -> tuple[object, object, str]:
    contract = extract_contract(question)
    plan = try_heuristic_plan(question)
    assert plan is not None
    plan = normalize_semantic_plan(plan, question)
    checked = validate_semantic_plan(plan, question)
    assert checked.status == "ready", checked.errors
    sql = compile_semantic_plan(checked.plan).sql
    return contract, checked.plan, sql


def test_architecture_group_rank_reaches_plan_sql() -> None:
    q = "사상구 공장 구조별 평균 연면적 상위 6개와 건수"
    contract = extract_contract(q)
    assert "structure" in contract.group_fields
    assert contract.limit == 6
    assert any(item.function == "avg" for item in contract.aggregation_requests)
    assert any(item.function == "count" for item in contract.aggregation_requests)
    assert select_execution_path(q) == "semantic_plan"
    _, plan, sql = _compile_question(q)
    assert "structure" in plan.group_by
    assert any(item.function == "avg" for item in plan.aggregations)
    assert any(item.function == "count" for item in plan.aggregations)
    assert plan.limit == 6
    upper = sql.upper()
    assert "GROUP BY" in upper
    assert "AVG(" in upper
    assert "COUNT(" in upper
    assert "LIMIT 6" in upper


def test_architecture_conditional_ratio_preserved() -> None:
    q = "영도구 15층 이상 건물 중 공동주택 비율 %"
    contract, plan, sql = _compile_question(q)
    assert contract.ratios
    assert plan.ratios
    assert plan.ratios[0].denominator_predicate is not None
    upper = sql.upper()
    assert "FILTER" in upper
    assert sql.upper().count("FILTER") >= 2
    assert "공동주택" in sql


def test_architecture_percentile_not_plain_rank() -> None:
    q = "사하구 공장 연면적 상위 10% 경계값(90백분위)"
    contract, plan, sql = _compile_question(q)
    assert contract.percentile_requests
    assert abs(contract.percentile_requests[0].percentile - 0.9) < 1e-9
    aggs = [item for item in plan.aggregations if item.function == "percentile"]
    assert aggs
    assert abs((aggs[0].percentile or 0) - 0.9) < 1e-9
    assert "PERCENTILE_CONT(0.9)" in sql.upper()
    assert select_execution_path(q) == "semantic_plan"


def test_architecture_derived_metric_divide() -> None:
    q = "수영구 숙박시설 중 연면적 대비 건축면적 비(평균 A12/A14)"
    contract, plan, sql = _compile_question(q)
    assert contract.derived_metrics
    exprs = [item.expression for item in plan.aggregations if item.expression]
    assert exprs and exprs[0].kind == "divide"
    upper = sql.upper()
    assert "AVG(" in upper
    assert "NULLIF(" in upper


def test_architecture_stddev_with_avg() -> None:
    q = "해운대구 건물 높이 평균과 표준편차"
    contract, plan, sql = _compile_question(q)
    fns = {item.function for item in contract.aggregation_requests}
    assert "avg" in fns
    assert "stddev" in fns
    plan_fns = {item.function for item in plan.aggregations}
    assert "avg" in plan_fns
    assert "stddev" in plan_fns
    upper = sql.upper()
    assert "AVG(" in upper
    assert "STDDEV_POP(" in upper
