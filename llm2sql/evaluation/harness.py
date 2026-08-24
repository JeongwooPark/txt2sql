"""route / Plan / result / clarify를 분리 평가한다."""

from __future__ import annotations

from typing import Any

from llm2sql.evaluation.plan_compare import classify_plan_errors, plans_match
from llm2sql.evaluation.results import compare_result_sets
from llm2sql.evaluation.schema import EvalItemResult, GoldPlanCase
from llm2sql.evaluation.taxonomy import classify_root_causes
from llm2sql.semantic_plan.models import SemanticQueryPlan


def evaluate_case(
    case: GoldPlanCase,
    *,
    predicted_plan: SemanticQueryPlan | dict[str, Any] | None = None,
    predicted_route: str | None = None,
    predicted_rows: list[dict[str, Any]] | None = None,
    predicted_clarify: bool | None = None,
    sql_executed: bool | None = None,
    latency_ms: int | None = None,
) -> EvalItemResult:
    error_codes: list[str] = []
    route_match = None
    if case.gold_route is not None:
        route_match = predicted_route == case.gold_route
        if not route_match:
            error_codes.append("R01")

    plan_match = None
    if case.gold_plan is not None:
        plan_match = plans_match(predicted_plan, case.gold_plan)
        if not plan_match:
            error_codes.extend(classify_plan_errors(predicted_plan, case.gold_plan))

    result_match = None
    if case.gold_result_hash:
        compared = compare_result_sets(
            predicted_rows,
            None,
            mode=case.result_mode,
            gold_hash=case.gold_result_hash,
        )
        result_match = compared["match"]
        if not result_match:
            error_codes.append("Q03")

    clarify_match = None
    gold_clarify = case.gold_clarify or bool(
        case.gold_plan and case.gold_plan.get("requires_clarification")
    )
    if predicted_clarify is not None or gold_clarify:
        pred_c = bool(predicted_clarify)
        clarify_match = pred_c == gold_clarify
        if gold_clarify and not pred_c:
            error_codes.append("A01")
        if pred_c and not gold_clarify:
            error_codes.append("A02")

    passed = not error_codes
    unique = list(dict.fromkeys(error_codes))
    return EvalItemResult.model_validate(
        {
            "id": case.id,
            "question": case.question,
            "status": case.status,
            "pass": passed,
            "error_codes": unique,
            "predicted_route": predicted_route,
            "gold_route": case.gold_route,
            "route_match": route_match,
            "plan_match": plan_match,
            "result_match": result_match,
            "clarify_match": clarify_match,
            "predicted_clarify": predicted_clarify,
            "gold_clarify": gold_clarify,
            "sql_executed": sql_executed,
            "latency_ms": latency_ms,
            "root_causes": classify_root_causes(unique, timed_out="Q02" in unique),
            "selected_route": predicted_route,
        }
    )
