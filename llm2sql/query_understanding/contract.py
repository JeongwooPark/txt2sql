"""한국어 질문 → Query Contract. 원문 character span을 보존한다."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from llm2sql.query_understanding import operators as ops
from llm2sql.query_understanding.ambiguity import conflicting_ranges, unresolved_content_spans
from llm2sql.query_understanding.complexity import complexity_score
from llm2sql.query_understanding.spans import Span, dedupe_nested, find_all


class QueryContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    places: list[Span] = Field(default_factory=list)
    metrics: list[Span] = Field(default_factory=list)
    numbers: list[Span] = Field(default_factory=list)
    boolean_ops: list[Span] = Field(default_factory=list)
    aggregations: list[Span] = Field(default_factory=list)
    order: list[Span] = Field(default_factory=list)
    limits: list[Span] = Field(default_factory=list)
    outputs: list[Span] = Field(default_factory=list)
    comparisons: list[Span] = Field(default_factory=list)
    ranges: list[Span] = Field(default_factory=list)
    groups: list[Span] = Field(default_factory=list)
    unresolved_spans: list[Span] = Field(default_factory=list)
    coverage_ratio: float = 0.0
    boolean_structure_supported: bool = True
    aggregation_complete: bool = True
    all_numeric_expressions_bound: bool = True
    all_requested_outputs_bound: bool = True
    complexity: int = 0

    def consumed(self) -> list[Span]:
        return (
            self.places
            + self.metrics
            + self.numbers
            + self.boolean_ops
            + self.aggregations
            + self.order
            + self.limits
            + self.outputs
            + self.comparisons
            + self.ranges
            + self.groups
        )


def extract_contract(question: str) -> QueryContract:
    q = question
    places = _with_value(find_all(q, ops.PLACE_PATTERN, "place"), "place")
    metrics: list[Span] = []
    for text, field in ops.METRIC_MAP.items():
        for span in find_all(q, re.escape(text), "metric"):
            span.value = field
            metrics.append(span)
    metrics = dedupe_nested(metrics)

    aggregations: list[Span] = []
    for text, fn in ops.AGG_MAP.items():
        for span in find_all(q, re.escape(text), "aggregation"):
            span.value = fn
            aggregations.append(span)

    boolean_ops: list[Span] = []
    for pattern in ops.AND_PATTERNS:
        boolean_ops.extend(find_all(q, pattern, "and"))
    for pattern in ops.OR_PATTERNS:
        boolean_ops.extend(find_all(q, pattern, "or"))
    for pattern in ops.NOT_PATTERNS:
        boolean_ops.extend(find_all(q, pattern, "not"))
    boolean_ops = dedupe_nested(boolean_ops)

    ranges = _extract_ranges(q)
    numbers = _extract_numbers(q, ranges)
    order = _extract_order(q)
    limits = _extract_limits(q)
    outputs = _extract_outputs(q)
    comparisons = _extract_comparisons(q)
    groups: list[Span] = []
    for hint in ops.GROUP_HINTS:
        groups.extend(find_all(q, re.escape(hint), "group"))

    contract = QueryContract(
        question=q,
        places=places,
        metrics=metrics,
        numbers=numbers,
        boolean_ops=boolean_ops,
        aggregations=aggregations,
        order=order,
        limits=limits,
        outputs=outputs,
        comparisons=comparisons,
        ranges=ranges,
        groups=groups,
    )
    consumed = contract.consumed()
    conflicts = conflicting_ranges(ranges)
    leftover = unresolved_content_spans(q, consumed)
    contract.unresolved_spans = leftover + conflicts
    contract.boolean_structure_supported = not any(
        item.kind == "or" and not _or_has_two_operands(q, item) for item in boolean_ops
    )
    contract.aggregation_complete = _aggregation_complete(contract)
    contract.all_numeric_expressions_bound = all(
        item.meta.get("field") or item.kind == "limit" for item in numbers + ranges
    ) or not (numbers or ranges)
    if ranges:
        contract.all_numeric_expressions_bound = all(
            span.meta.get("low") is not None and span.meta.get("high") is not None
            for span in ranges
        )
    contract.all_requested_outputs_bound = True
    contract.coverage_ratio = _slot_coverage(contract)
    contract.complexity = complexity_score(
        boolean_ops=boolean_ops,
        aggregations=aggregations,
        comparisons=comparisons,
        ranges=ranges,
        groups=groups,
    )
    if conflicts:
        contract.boolean_structure_supported = False
        contract.coverage_ratio = min(contract.coverage_ratio, 0.99)
    return contract


def _with_value(spans: list[Span], key: str) -> list[Span]:
    for span in spans:
        span.value = span.text
        span.meta[key] = span.text
    return spans


def _extract_ranges(question: str) -> list[Span]:
    found: list[Span] = []
    for pattern in ops.RANGE_PATTERNS:
        for match in re.finditer(pattern, question):
            meta: dict[str, Any] = {
                "low": float(match.group("lo")),
                "high": float(match.group("hi")),
                "unit": match.groupdict().get("u2") or match.groupdict().get("u1"),
            }
            field = _nearest_metric(question, match.start())
            if field:
                meta["field"] = field
            found.append(
                Span(
                    kind="range",
                    text=match.group(0),
                    start=match.start(),
                    end=match.end(),
                    value=(meta["low"], meta["high"]),
                    meta=meta,
                )
            )
    return dedupe_nested(found)


def _extract_numbers(question: str, ranges: list[Span]) -> list[Span]:
    found: list[Span] = []
    for match in re.finditer(ops.NUMBER_UNIT_PATTERN, question):
        span = Span(
            kind="number",
            text=match.group(0),
            start=match.start(),
            end=match.end(),
            value=float(match.group("num")),
            meta={"unit": match.group("unit"), "field": _nearest_metric(question, match.start())},
        )
        if any(rng.contains(span) for rng in ranges):
            continue
        found.append(span)
    return found


def _extract_order(question: str) -> list[Span]:
    found: list[Span] = []
    for text in ops.SORT_ASC:
        for span in find_all(question, re.escape(text), "order"):
            span.value = "asc"
            found.append(span)
    for text in ops.SORT_DESC:
        for span in find_all(question, re.escape(text), "order"):
            span.value = "desc"
            found.append(span)
    return dedupe_nested(found)


def _extract_limits(question: str) -> list[Span]:
    found: list[Span] = []
    for match in re.finditer(ops.LIMIT_PATTERN, question):
        found.append(
            Span(
                kind="limit",
                text=match.group(0),
                start=match.start(),
                end=match.end(),
                value=int(match.group("n")),
            )
        )
    return found


def _extract_outputs(question: str) -> list[Span]:
    found: list[Span] = []
    for hint in ops.OUTPUT_HINTS:
        found.extend(find_all(question, re.escape(hint), "output"))
    return dedupe_nested(found)


def _extract_comparisons(question: str) -> list[Span]:
    found: list[Span] = []
    for pattern in ops.COMPARE_PATTERNS:
        for match in re.finditer(pattern, question):
            left = match.groupdict().get("left")
            right = match.groupdict().get("right")
            rel = "gt" if "큰" in match.group(0) or "높" in match.group(0) else "lt"
            found.append(
                Span(
                    kind="comparison",
                    text=match.group(0),
                    start=match.start(),
                    end=match.end(),
                    value={"left": ops.METRIC_MAP.get(left or "", left), "op": rel, "right": ops.METRIC_MAP.get(right or "", right)},
                    meta={"left": left, "right": right, "op": rel},
                )
            )
    return dedupe_nested(found)


def _nearest_metric(question: str, index: int) -> str | None:
    best: tuple[int, str] | None = None
    for text, field in ops.METRIC_MAP.items():
        pos = question.rfind(text, 0, index + 1)
        if pos < 0:
            continue
        dist = index - pos
        if best is None or dist < best[0]:
            best = (dist, field)
    return best[1] if best and best[0] <= 16 else None


def _or_has_two_operands(question: str, span: Span) -> bool:
    left = question[: span.start]
    right = question[span.end :]
    return bool(left.strip() and right.strip())


def _aggregation_complete(contract: QueryContract) -> bool:
    if not contract.aggregations:
        return True
    fns = {item.value for item in contract.aggregations}
    if "avg" in fns or "sum" in fns or "min" in fns or "max" in fns or "median" in fns:
        return bool(contract.metrics) or bool(contract.groups)
    return True


def _slot_coverage(contract: QueryContract) -> float:
    slots = (
        contract.places
        + contract.metrics
        + contract.aggregations
        + contract.boolean_ops
        + contract.ranges
        + contract.comparisons
        + contract.order
        + contract.limits
        + contract.groups
    )
    if contract.unresolved_spans:
        return 0.0 if not slots else round(
            max(0.0, (len(slots) - len(contract.unresolved_spans)) / max(len(slots), 1)),
            4,
        )
    if not slots:
        return 1.0
    bound = len(slots)
    if not contract.all_numeric_expressions_bound:
        bound -= 1
    if not contract.aggregation_complete:
        bound -= 1
    return round(max(0.0, bound / len(slots)), 4)
