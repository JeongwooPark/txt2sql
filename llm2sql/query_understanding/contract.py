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
    places = _drop_false_places(q, places)
    metrics: list[Span] = []
    for text, field in ops.METRIC_MAP.items():
        for span in find_all(q, re.escape(text), "metric"):
            span.value = field
            metrics.append(span)
    metrics = dedupe_nested(metrics)
    if "기초구역" in q:
        for span in metrics:
            if span.value == "gross_floor_area_m2":
                span.value = "area_m2"

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
    if "기초구역" in q:
        for span in numbers + ranges:
            if span.meta.get("field") == "gross_floor_area_m2":
                span.meta["field"] = "area_m2"

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
    _bind_or_operands(q, boolean_ops)
    contract.all_requested_outputs_bound = _outputs_bound(outputs)
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


def _drop_false_places(question: str, spans: list[Span]) -> list[Span]:
    """공동주택·시설 안의 '동' 조각은 장소가 아니다."""
    kept: list[Span] = []
    for span in spans:
        after = question[span.end : span.end + 3]
        if after.startswith(("주택", "시설", "차", "력", "원", "사")):
            continue
        if span.text in {"공동", "동"}:
            continue
        kept.append(span)
    return kept


def _with_value(spans: list[Span], key: str) -> list[Span]:
    for span in spans:
        span.value = span.text
        span.meta[key] = span.text
    return spans


def _extract_ranges(question: str) -> list[Span]:
    found: list[Span] = []
    for pattern in ops.RANGE_PATTERNS:
        for match in re.finditer(pattern, question):
            gd = match.groupdict()
            meta: dict[str, Any] = {
                "low": float(match.group("lo")),
                "high": float(match.group("hi")),
                "unit": gd.get("u2") or gd.get("u1"),
                "lo_rel": gd.get("lo_rel") or "이상",
                "hi_rel": gd.get("hi_rel")
                or ("사이" if "사이" in match.group(0) else "까지"),
            }
            field = _nearest_metric(question, match.start())
            if "층" in match.group(0) and "지하" not in match.group(0):
                field = "ground_floors"
            elif "층" in match.group(0) and "지하" in question[max(0, match.start() - 4) : match.start()]:
                field = "basement_floors"
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
            meta={"unit": match.group("unit"), "field": None},
        )
        if any(rng.contains(span) for rng in ranges):
            continue
        found.append(span)
    _bind_numbers_greedily(question, found)
    return found


def _extract_order(question: str) -> list[Span]:
    found: list[Span] = []
    for text in ops.SORT_ASC:
        for span in find_all(question, re.escape(text), "order"):
            if question[: span.start].rstrip().endswith("보다"):
                continue
            span.value = "asc"
            found.append(span)
    for text in ops.SORT_DESC:
        for span in find_all(question, re.escape(text), "order"):
            if question[: span.start].rstrip().endswith("보다"):
                continue
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
        for span in find_all(question, re.escape(hint), "output"):
            span.value = ops.OUTPUT_FIELD_MAP.get(hint, hint)
            span.meta["field"] = span.value
            found.append(span)
    return dedupe_nested(found)


def _extract_comparisons(question: str) -> list[Span]:
    found: list[Span] = []
    for pattern in ops.COMPARE_PATTERNS:
        for match in re.finditer(pattern, question):
            left = match.groupdict().get("left")
            right = match.groupdict().get("right")
            rel = "lt" if any(k in match.group(0) for k in ("작", "낮")) else "gt"
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
    candidates: list[tuple[int, int, int, str]] = []
    for text, field in ops.METRIC_MAP.items():
        pos = question.rfind(text, 0, index + 1)
        if pos < 0:
            continue
        dist = index - pos
        if dist > 16:
            continue
        candidates.append((pos, pos + len(text), len(text), field))
    if not candidates:
        return None
    kept = [
        item
        for item in candidates
        if not any(
            item[0] >= other[0] and item[1] <= other[1] and other[2] > item[2]
            for other in candidates
        )
    ]
    kept.sort(key=lambda item: (index - item[0], -item[2]))
    return kept[0][3]


def _or_has_two_operands(question: str, span: Span) -> bool:
    left_tok, right_tok = _or_operand_tokens(question, span)
    return bool(left_tok and right_tok)


def _or_operand_tokens(question: str, span: Span) -> tuple[str, str]:
    left = re.findall(r"[가-힣A-Za-z0-9]+", question[: span.start])
    right = re.findall(r"[가-힣A-Za-z0-9]+", question[span.end :])
    skip = {"그리고", "이면서", "중", "그", "이", "저", "및"}
    left_tok = next((t for t in reversed(left) if t not in skip), "")
    right_tok = next((t for t in right if t not in skip), "")
    return left_tok, right_tok


def _bind_or_operands(question: str, boolean_ops: list[Span]) -> None:
    for span in boolean_ops:
        if span.kind != "or":
            continue
        left_tok, right_tok = _or_operand_tokens(question, span)
        span.meta["left"] = left_tok
        span.meta["right"] = right_tok
        span.value = (left_tok, right_tok)


def _outputs_bound(outputs: list[Span]) -> bool:
    if not outputs:
        return True
    return all(bool(item.value) for item in outputs)


def _bind_numbers_greedily(question: str, numbers: list[Span]) -> None:
    used_spans: set[tuple[int, int]] = set()
    for span in numbers:
        field, metric_span = _nearest_unused_metric(question, span.start, used_spans)
        span.meta["field"] = field
        if metric_span is not None:
            used_spans.add(metric_span)


def _nearest_unused_metric(
    question: str,
    index: int,
    used: set[tuple[int, int]],
) -> tuple[str | None, tuple[int, int] | None]:
    candidates: list[tuple[int, int, int, str]] = []
    for text, field in ops.METRIC_MAP.items():
        pos = question.rfind(text, 0, index + 1)
        if pos < 0:
            continue
        dist = index - pos
        if dist > 24:
            continue
        span = (pos, pos + len(text))
        if span in used:
            continue
        candidates.append((pos, pos + len(text), len(text), field))
    if not candidates:
        return None, None
    kept = [
        item
        for item in candidates
        if not any(
            item[0] >= other[0] and item[1] <= other[1] and other[2] > item[2]
            for other in candidates
        )
    ]
    kept.sort(key=lambda item: (index - item[0], -item[2]))
    best = kept[0]
    return best[3], (best[0], best[1])


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
        + contract.outputs
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
    if not contract.all_requested_outputs_bound:
        bound -= 1
    return round(max(0.0, bound / len(slots)), 4)
