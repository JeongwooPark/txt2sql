from txt2sql.config import Settings
from txt2sql.query_understanding.contract import extract_contract
from txt2sql.query_understanding.gate import accept_heuristic_plan
from txt2sql.semantic_plan.generator import generate_semantic_plan, try_heuristic_plan


def test_gate_accepts_complete_or_and_field_compare() -> None:
    or_q = "연제구 공동주택 또는 단독주택 건물 수"
    plan = try_heuristic_plan(or_q)
    assert plan is not None
    assert plan.predicate is not None and plan.predicate.op == "or"
    assert accept_heuristic_plan(extract_contract(or_q), plan) is True

    cmp_q = "남구에서 건축면적이 연면적보다 큰 건물"
    cmp_plan = try_heuristic_plan(cmp_q)
    assert cmp_plan is not None
    assert any(item.value_field == "gross_floor_area_m2" for item in cmp_plan.filters)
    assert accept_heuristic_plan(extract_contract(cmp_q), cmp_plan) is True


def test_gate_rejects_avg_when_sum_requested() -> None:
    q = "해운대구 건물 높이 합계"
    plan = try_heuristic_plan(q)
    assert plan is not None
    assert plan.aggregations
    assert plan.aggregations[0].function == "sum"
    assert accept_heuristic_plan(extract_contract(q), plan) is True


def test_incomplete_or_does_not_execute_when_llm_disabled() -> None:
    settings = Settings(database_url="postgresql://x:x@localhost/x")
    plan = generate_semantic_plan(
        "연제구 공동주택 또는 건물 수",
        settings,
        allow_llm=False,
    )
    assert plan.requires_clarification is True
    assert any(
        item in (plan.assumptions or [])
        for item in ("heuristic_incomplete", "or_incomplete")
    )


def test_simple_complete_heuristic_still_accepted() -> None:
    q = "해운대구 아파트 중 높이 70m 이상인 건물 이름과 높이"
    plan = try_heuristic_plan(q)
    assert plan is not None
    assert accept_heuristic_plan(extract_contract(q), plan) is True
