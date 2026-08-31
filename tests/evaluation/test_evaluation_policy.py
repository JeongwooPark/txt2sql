"""EvaluationPolicy tests — metric-specific comparators, no global tolerance."""

from __future__ import annotations

from txt2sql.evaluation.evaluation_policy import (
    SemanticEvalContext,
    compare_values,
    comparator_for_context,
    contexts_align,
    infer_gold_context,
    match_numbers_in_haystack,
)


def test_count_uses_integer_exact() -> None:
    ctx = SemanticEvalContext(metric="count", unit="count", grain="building")
    spec = comparator_for_context(ctx)
    assert spec.kind == "integer_exact"
    assert compare_values(3021, 3021, spec)
    assert not compare_values(3021, 3020, spec)


def test_avg_uses_scalar_float_tolerance() -> None:
    ctx = SemanticEvalContext(metric="avg", unit="m2")
    spec = comparator_for_context(ctx)
    assert spec.kind == "scalar_float"
    assert compare_values(123.456, 123.457, spec)
    assert not compare_values(123.4, 124.0, spec)


def test_ratio_uses_ratio_comparator() -> None:
    ctx = SemanticEvalContext(metric="ratio", unit="pct")
    spec = comparator_for_context(ctx)
    assert spec.kind == "ratio"
    assert compare_values(24.7444, 24.75, spec)


def test_context_mismatch_blocks_tolerance() -> None:
    gold = SemanticEvalContext(metric="avg", unit="m2", grain="building")
    pred = SemanticEvalContext(metric="count", unit="count", grain="building")
    assert not contexts_align(gold, pred)
    ok, _, reason = match_numbers_in_haystack(
        [100.0], [100.0], gold_ctx=gold, pred_ctx=pred
    )
    assert not ok
    assert reason == "semantic-context-mismatch"


def test_unit_mismatch_blocks_tolerance() -> None:
    gold = SemanticEvalContext(metric="avg", unit="m2")
    pred = SemanticEvalContext(metric="avg", unit="pct")
    assert not contexts_align(gold, pred)


def test_infer_gold_context_ratio_from_pct() -> None:
    ctx = infer_gold_context(
        kind="scalar",
        gold="pct_violate=1.5357",
        question="위반건축물 비율",
    )
    assert ctx.metric == "ratio"
    assert ctx.unit == "pct"


def test_infer_gold_context_avg_from_gold_key() -> None:
    ctx = infer_gold_context(
        kind="scalar",
        gold="avg_h=46.0947",
        question="부산 전체 건물의 평균 높이를 알려줘",
    )
    assert ctx.metric == "avg"
    assert ctx.unit == "m"


def test_infer_pred_context_scalar_avg_not_count() -> None:
    from txt2sql.evaluation.evaluation_policy import infer_pred_context

    pred = infer_pred_context(
        kind="scalar",
        answer="부산의 집계 결과입니다. avg_height_m=46.094655, 건수=472620",
        rows=None,
        sql="SELECT AVG(height) AS avg_height_m, COUNT(*) AS n FROM buildings",
        question="부산 전체 건물의 평균 높이를 알려줘",
    )
    gold = infer_gold_context(
        kind="scalar",
        gold="avg_h=46.0947",
        question="부산 전체 건물의 평균 높이를 알려줘",
    )
    assert pred is not None
    assert pred.metric == "avg"
    assert contexts_align(gold, pred)


def test_distance_uses_meter_tolerance() -> None:
    ctx = SemanticEvalContext(metric="distance", unit="m")
    spec = comparator_for_context(ctx)
    assert spec.kind == "distance_m"
    assert compare_values(250.3, 250.0, spec)


def test_count_distinct_exact() -> None:
    ctx = SemanticEvalContext(
        metric="count_distinct", unit="count", grain="admin_dong", distinct=True
    )
    spec = comparator_for_context(ctx)
    assert spec.kind == "integer_exact"
    assert not compare_values(10, 11, spec)
