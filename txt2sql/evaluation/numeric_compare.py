"""Numeric comparison — delegates to EvaluationPolicy (no global tolerance)."""

from __future__ import annotations

from typing import Any

from txt2sql.evaluation.evaluation_policy import (
    SemanticEvalContext,
    compare_values,
    comparator_for_context,
    contexts_align,
    infer_gold_context,
    infer_pred_context,
    match_numbers_in_haystack,
    parse_numbers,
)

__all__ = [
    "SemanticEvalContext",
    "compare_values",
    "comparator_for_context",
    "contexts_align",
    "infer_gold_context",
    "infer_pred_context",
    "match_numbers_in_haystack",
    "parse_numbers",
    "scalar_match",
    "values_equal",
]


def values_equal(
    got: Any,
    expected: Any,
    *,
    gold_ctx: SemanticEvalContext | None = None,
    pred_ctx: SemanticEvalContext | None = None,
) -> bool:
    """Compare with policy. Without aligned contexts, uses integer_exact."""
    if gold_ctx is None:
        from txt2sql.evaluation.evaluation_policy import ComparatorSpec

        spec = ComparatorSpec(kind="integer_exact")
        return compare_values(got, expected, spec)
    if pred_ctx is not None and not contexts_align(gold_ctx, pred_ctx):
        return False
    spec = comparator_for_context(gold_ctx)
    return compare_values(got, expected, spec)


def scalar_match(
    answer: str,
    gold_nums: list[float],
    *,
    kind: str = "scalar",
    gold: str = "",
    question: str = "",
    rows: list[dict[str, Any]] | None = None,
    sql: str | None = None,
) -> tuple[bool, int]:
    """Policy-aware scalar match — requires semantic context alignment."""
    gold_ctx = infer_gold_context(kind=kind, gold=gold, question=question)
    pred_ctx = infer_pred_context(
        kind=kind, answer=answer, rows=rows, sql=sql, question=question
    )
    pred_nums = parse_numbers(answer)
    if rows:
        for row in rows:
            for v in row.values():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    pred_nums.append(float(v))
    ok, hits, _ = match_numbers_in_haystack(
        pred_nums, gold_nums, gold_ctx=gold_ctx, pred_ctx=pred_ctx
    )
    return ok, hits
