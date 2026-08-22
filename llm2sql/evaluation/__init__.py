"""평가 패키지: 의미 정확도와 실행 성공률을 분리한다."""

from llm2sql.evaluation.harness import evaluate_case
from llm2sql.evaluation.plan_compare import canonicalize_plan, classify_plan_errors, plans_match
from llm2sql.evaluation.results import compare_result_sets, result_hash
from llm2sql.evaluation.schema import EvalItemResult, EvalSummary, GoldPlanCase
from llm2sql.evaluation.taxonomy import ERROR_LABELS

__all__ = [
    "ERROR_LABELS",
    "EvalItemResult",
    "EvalSummary",
    "GoldPlanCase",
    "canonicalize_plan",
    "classify_plan_errors",
    "compare_result_sets",
    "evaluate_case",
    "plans_match",
    "result_hash",
]
