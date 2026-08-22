"""질의 복잡도 점수. 휴리스틱 채택 여부를 돕는다."""

from __future__ import annotations

from llm2sql.query_understanding.spans import Span


def complexity_score(
    *,
    boolean_ops: list[Span],
    aggregations: list[Span],
    comparisons: list[Span],
    ranges: list[Span],
    groups: list[Span],
) -> int:
    score = 0
    if any(item.kind == "or" for item in boolean_ops):
        score += 2
    if any(item.kind == "not" for item in boolean_ops):
        score += 2
    score += len(aggregations)
    score += len(comparisons) * 2
    score += len(ranges)
    score += len(groups)
    return score


def is_hard_query(score: int) -> bool:
    return score >= 3
