"""질문 원문 character span."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Span(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    text: str
    start: int
    end: int
    value: Any | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

    def contains(self, other: Span) -> bool:
        return self.start <= other.start and other.end <= self.end


def find_all(question: str, pattern: str, kind: str, flags: int = 0) -> list[Span]:
    spans: list[Span] = []
    for match in re.finditer(pattern, question, flags):
        spans.append(
            Span(kind=kind, text=match.group(0), start=match.start(), end=match.end())
        )
    return spans


def dedupe_nested(spans: list[Span]) -> list[Span]:
    ordered = sorted(spans, key=lambda item: (item.start, -(item.end - item.start)))
    kept: list[Span] = []
    for span in ordered:
        if any(prev.contains(span) and prev.kind == span.kind for prev in kept):
            continue
        kept.append(span)
    return sorted(kept, key=lambda item: item.start)
