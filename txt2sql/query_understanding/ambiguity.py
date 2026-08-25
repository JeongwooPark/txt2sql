"""미해결·상충 span."""

from __future__ import annotations

from txt2sql.query_understanding.spans import Span


def conflicting_ranges(ranges: list[Span]) -> list[Span]:
    conflicts: list[Span] = []
    for left in ranges:
        for right in ranges:
            if left is right:
                continue
            if left.meta.get("field") and left.meta.get("field") == right.meta.get("field"):
                lo1, hi1 = left.meta.get("low"), left.meta.get("high")
                lo2, hi2 = right.meta.get("low"), right.meta.get("high")
                if None not in (lo1, hi1, lo2, hi2) and (hi1 < lo2 or hi2 < lo1):
                    conflicts.append(left)
    return conflicts


def unresolved_content_spans(
    question: str,
    consumed: list[Span],
    *,
    leftover_tokens: tuple[str, ...] = ("왜", "어떻게", "언제", "누구"),
) -> list[Span]:
    unresolved: list[Span] = []
    for token in leftover_tokens:
        start = 0
        while True:
            idx = question.find(token, start)
            if idx < 0:
                break
            span = Span(kind="unresolved", text=token, start=idx, end=idx + len(token))
            if not any(item.contains(span) or span.contains(item) for item in consumed):
                unresolved.append(span)
            start = idx + len(token)
    return unresolved
