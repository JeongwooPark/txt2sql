from txt2sql.evaluation.harness import evaluate_case
from txt2sql.evaluation.plan_compare import classify_plan_errors, plans_match
from txt2sql.evaluation.results import result_hash
from txt2sql.evaluation.schema import GoldPlanCase
from txt2sql.semantic_plan.models import SemanticQueryPlan


def _gold(**kwargs) -> dict:
    base = {
        "version": "1.0",
        "query_kind": "aggregate",
        "entity": "building",
        "scope": {"place": {"name": "해운대구", "kind": "gu"}, "spatial_mode": "auto"},
        "filters": [],
        "select": [],
        "aggregations": [{"function": "sum", "field": "height_m", "alias": "sum_height_m"}],
        "group_by": [],
        "order_by": [],
        "limit": None,
        "spatial_relations": [],
        "requires_clarification": False,
    }
    base.update(kwargs)
    return base


def test_result_hash_ignores_row_order() -> None:
    a = [{"name": "A", "n": 1}, {"name": "B", "n": 2}]
    b = [{"n": 2, "name": "B"}, {"n": 1, "name": "A"}]
    assert result_hash(a, mode="set") == result_hash(b, mode="set")
    assert result_hash(a, mode="sequence") != result_hash(list(reversed(a)), mode="sequence")


def test_sql_token_is_not_a_pass_signal() -> None:
    case = GoldPlanCase(
        id="T1",
        question="합계",
        status="verified",
        gold_plan=_gold(),
    )
    predicted = _gold(aggregations=[{"function": "avg", "field": "height_m", "alias": "avg_height_m"}])
    scored = evaluate_case(case, predicted_plan=predicted)
    assert scored.pass_ is False
    assert "P05" in scored.error_codes


def test_plan_match_and_aggregate_error() -> None:
    gold = _gold()
    pred_ok = SemanticQueryPlan.model_validate(gold)
    assert plans_match(pred_ok, gold)
    pred_bad = _gold(aggregations=[{"function": "avg", "field": "height_m", "alias": "avg_height_m"}])
    assert classify_plan_errors(pred_bad, gold) == ["P05"]


def test_clarify_and_route_codes() -> None:
    case = GoldPlanCase(
        id="T2",
        question="모호",
        status="verified",
        gold_plan=_gold(requires_clarification=True, aggregations=[]),
        gold_route="semantic_plan_clarify",
        gold_clarify=True,
    )
    scored = evaluate_case(
        case,
        predicted_plan=_gold(requires_clarification=False, aggregations=[]),
        predicted_route="rag_sql",
        predicted_clarify=False,
    )
    assert scored.pass_ is False
    assert "A01" in scored.error_codes
    assert "R01" in scored.error_codes


def test_result_hash_mismatch_is_q03() -> None:
    case = GoldPlanCase(
        id="T3",
        question="list",
        status="verified",
        gold_plan=_gold(query_kind="list", aggregations=[]),
        gold_result_hash=result_hash([{"id": 1}]),
    )
    scored = evaluate_case(
        case,
        predicted_plan=_gold(query_kind="list", aggregations=[]),
        predicted_rows=[{"id": 2}],
    )
    assert scored.result_match is False
    assert "Q03" in scored.error_codes
