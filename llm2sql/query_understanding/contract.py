"""한국어 질문 → Query Contract. 원문 character span을 보존한다."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from llm2sql.query_understanding import operators as ops
from llm2sql.query_understanding.ambiguity import conflicting_ranges, unresolved_content_spans
from llm2sql.query_understanding.complexity import complexity_score
from llm2sql.query_understanding.spans import Span, dedupe_nested, find_all


class AggregationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    function: str
    field: str | None = None
    percentile: float | None = None


class RatioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    has_denominator: bool = False


class DerivedMetricRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = "divide"
    left: str
    right: str


class PercentileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    percentile: float
    field: str | None = None


class OrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direction: str = "desc"
    field: str | None = None


class ContractCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_complete: bool = True
    predicate_complete: bool = True
    aggregation_complete: bool = True
    grouping_complete: bool = True
    output_complete: bool = True
    ordering_complete: bool = True

    def all_ok(self) -> bool:
        return (
            self.entity_complete
            and self.predicate_complete
            and self.aggregation_complete
            and self.grouping_complete
            and self.output_complete
            and self.ordering_complete
        )


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
    operation: str | None = None
    group_fields: list[str] = Field(default_factory=list)
    aggregation_requests: list[AggregationRequest] = Field(default_factory=list)
    ratios: list[RatioRequest] = Field(default_factory=list)
    derived_metrics: list[DerivedMetricRequest] = Field(default_factory=list)
    percentile_requests: list[PercentileRequest] = Field(default_factory=list)
    output_fields: list[str] = Field(default_factory=list)
    order_requests: list[OrderRequest] = Field(default_factory=list)
    limit: int | None = None
    fixed_bins: bool = False
    wants_spatial: bool = False
    wants_basement: bool = False
    wants_count: bool = False
    wants_temporal: bool = False
    # 결과 형태. count는 단일 스칼라. 구간별·연도별은 group.
    query_kind: str = "count"
    datasets: list[str] = Field(default_factory=list)
    spatial_path: str | None = None

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

    def coverage(self) -> ContractCoverage:
        grouping_complete = (not self.groups) or bool(self.group_fields)
        ordering_complete = (not self.order) or bool(self.order_requests)
        return ContractCoverage(
            entity_complete=True,
            predicate_complete=self.boolean_structure_supported
            and self.all_numeric_expressions_bound,
            aggregation_complete=self.aggregation_complete,
            grouping_complete=grouping_complete,
            output_complete=self.all_requested_outputs_bound,
            ordering_complete=ordering_complete,
        )

    def is_sufficient(self) -> bool:
        """Router에 넘길 만큼 Contract가 닫혀 있는지."""
        return self.coverage().all_ok()


# BIN_HINTS(구간별)에 없는 그룹 표현. extract의 fixed_bins와 별도로 kind만 맞춘다.
_GROUP_KIND_RE = re.compile(r"(연도별|단위로\s*묶)")


_COUNTISH = (
    "몇 채",
    "몇채",
    "건수",
    "채수",
    "개수",
    "채야",
    "건물 수",
    "건물수",
    "몇 개",
    "몇개",
    "수는",
    "개가",
)


def _explicit_count(question: str) -> bool:
    if any(k in question for k in _COUNTISH):
        return True
    return bool(re.search(r"몇\s*(채|동|개)(?!%)", question))


def extract_contract(question: str, binding: Any | None = None) -> QueryContract:
    q = question
    if binding is None:
        from llm2sql.query_understanding.bind import bind_catalog

        binding = bind_catalog(q)
    places = _with_value(find_all(q, ops.PLACE_PATTERN, "place"), "place")
    places = _drop_false_places(q, places)
    metrics: list[Span] = []
    for text, field in ops.METRIC_MAP.items():
        for span in find_all(q, re.escape(text), "metric"):
            span.value = field
            metrics.append(span)
    metrics.extend(_categorical_metrics(q))
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
    outputs = _extract_outputs(q)
    comparisons = _extract_comparisons(q)
    groups: list[Span] = []
    for hint in ops.GROUP_HINTS:
        for span in find_all(q, re.escape(hint), "group"):
            span.value = ops.GROUP_FIELD_MAP.get(hint, hint)
            groups.append(span)
    groups = dedupe_nested(groups)
    if "기초구역" in q:
        for span in numbers + ranges:
            if span.meta.get("field") == "gross_floor_area_m2":
                span.meta["field"] = "area_m2"

    limits = _extract_limits(q, places)
    percentile_requests = _extract_percentiles(q)
    ratios = _extract_ratios(q)
    derived_metrics = _extract_derived(q)
    fixed_bins = any(h in q for h in ops.BIN_HINTS)
    wants_spatial = any(
        h in q
        for h in (
            "안에",
            "내에",
            "내부",
            "안쪽",
            "주변",
            "이내",
            "반경",
            "버퍼",
            "교차",
            "겹치",
            "맞닿",
            "경계 안",
            "경계안",
        )
    ) or bool(getattr(binding, "spatial_path", None))
    wants_basement = bool(re.search(r"지하(?!철)", q))
    wants_count = _explicit_count(q)
    from llm2sql.query_understanding.temporal import parse_temporal_filters
    from llm2sql.domain import looks_like_age_question

    wants_temporal = bool(parse_temporal_filters(q)) or looks_like_age_question(q)

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
        percentile_requests=percentile_requests,
        ratios=ratios,
        derived_metrics=derived_metrics,
        fixed_bins=fixed_bins,
        wants_spatial=wants_spatial,
        wants_basement=wants_basement,
        wants_count=wants_count,
        wants_temporal=wants_temporal,
        datasets=[item.id for item in getattr(binding, "datasets", [])],
        spatial_path=(
            f"{binding.spatial_path.left_entity}:{binding.spatial_path.op}:{binding.spatial_path.right_entity}"
            if getattr(binding, "spatial_path", None) is not None
            else None
        ),
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
    _finalize_requests(contract)
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


def _extract_limits(question: str, places: list[Span] | None = None) -> list[Span]:
    found: list[Span] = []
    places = places or []
    for match in re.finditer(ops.LIMIT_PATTERN, question):
        if question[match.end() : match.end() + 1] == "%":
            continue
        start, end = match.start(), match.end()
        if any(item.start <= start and end <= item.end for item in places):
            continue
        found.append(
            Span(
                kind="limit",
                text=match.group(0),
                start=start,
                end=end,
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
    unit_fields = {
        "층": "ground_floors",
        "m": "height_m",
        "미터": "height_m",
        "㎡": "gross_floor_area_m2",
        "m2": "gross_floor_area_m2",
        "평": "gross_floor_area_m2",
    }
    for span in numbers:
        field, metric_span = _nearest_unused_metric(question, span.start, used_spans)
        if not field:
            field = unit_fields.get(str(span.meta.get("unit") or ""))
        if str(span.meta.get("unit") or "") == "층":
            window = question[max(0, span.start - 6) : span.start]
            if re.search(r"지하(?!철)", window):
                field = "basement_floors"
            elif "지상" in window:
                field = "ground_floors"
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
    if "avg" in fns or "sum" in fns or "min" in fns or "max" in fns or "median" in fns or "stddev" in fns:
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


def _extract_percentiles(question: str) -> list[PercentileRequest]:
    found: list[PercentileRequest] = []
    field = _nearest_metric(question, len(question))
    for match in re.finditer(r"상위\s*(\d+(?:\.\d+)?)\s*%", question):
        pct = float(match.group(1))
        found.append(
            PercentileRequest(percentile=max(0.0, min(1.0, 1.0 - pct / 100.0)), field=field)
        )
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*백분위", question):
        pct = float(match.group(1))
        if pct > 1:
            pct = pct / 100.0
        found.append(PercentileRequest(percentile=max(0.0, min(1.0, pct)), field=field))
    return found


def _extract_ratios(question: str) -> list[RatioRequest]:
    if not any(h in question for h in ops.RATIO_HINTS):
        return []
    hits = sum(question.count(h) for h in ("비율", "퍼센트", "몇%"))
    hits += len(re.findall(r"(?<!\d)%", question))
    n = 2 if hits >= 2 or question.count("비율") >= 2 else 1
    has_den = "중" in question or "/" in question or "대비" in question
    return [RatioRequest(has_denominator=has_den) for _ in range(n)]


def _extract_derived(question: str) -> list[DerivedMetricRequest]:
    if "대비" in question or "비(" in question or re.search(r"건축면적\s*/\s*연면적", question):
        if "건축면적" in question and "연면적" in question:
            return [
                DerivedMetricRequest(
                    kind="divide",
                    left="building_area_m2",
                    right="gross_floor_area_m2",
                )
            ]
    return []


def _finalize_requests(contract: QueryContract) -> None:
    q = contract.question
    contract.group_fields = [
        str(item.value) for item in contract.groups if item.value
    ]
    seen_fn: list[str] = []
    for item in contract.aggregations:
        fn = str(item.value or "")
        if fn and fn not in seen_fn:
            seen_fn.append(fn)
            field = contract.metrics[0].value if contract.metrics else None
            contract.aggregation_requests.append(
                AggregationRequest(function=fn, field=str(field) if field else None)
            )
    if contract.wants_count and "count" not in seen_fn:
        contract.aggregation_requests.append(AggregationRequest(function="count"))
    for item in contract.percentile_requests:
        contract.aggregation_requests.append(
            AggregationRequest(
                function="percentile",
                field=item.field,
                percentile=item.percentile,
            )
        )
    contract.output_fields = [
        str(item.value) for item in contract.outputs if item.value
    ]
    for item in contract.order:
        contract.order_requests.append(
            OrderRequest(direction=str(item.value or "desc"))
        )
    if (
        not contract.order_requests
        and not contract.percentile_requests
        and any(h in q for h in ops.RANK_HINTS)
        and "백분위" not in q
        and not re.search(r"상위\s*\d+\s*%", q)
    ):
        contract.order_requests.append(OrderRequest(direction="desc"))
    if contract.limits:
        contract.limit = int(contract.limits[-1].value)
    if contract.ratios:
        contract.operation = "ratio"
    elif contract.percentile_requests:
        contract.operation = "percentile"
    elif contract.group_fields and (contract.order_requests or contract.limit):
        contract.operation = "group_rank"
    elif contract.order_requests or (contract.limit and any(h in q for h in ops.RANK_HINTS)):
        contract.operation = "rank"
    elif contract.aggregation_requests:
        contract.operation = "aggregate"
    elif contract.output_fields:
        contract.operation = "list"
    else:
        # 건수 단서가 없으면 기본 count. 목록은 output_fields가 있을 때만.
        contract.operation = "count"
    contract.query_kind = _infer_query_kind(contract)


def _looks_like_group(contract: QueryContract) -> bool:
    """구간·그룹 질의. '건수'가 있어도 스칼라 count가 아니다."""
    if contract.fixed_bins or contract.operation == "group_rank":
        return True
    if contract.group_fields and contract.aggregation_requests:
        return True
    return bool(_GROUP_KIND_RE.search(contract.question or ""))


def _infer_query_kind(contract: QueryContract) -> str:
    if contract.ratios:
        return "ratio"
    if contract.operation == "percentile":
        return "scalar"
    if _looks_like_group(contract):
        return "group"
    if contract.operation == "rank":
        return "rank"
    if contract.operation == "list":
        return "list"
    fns = {item.function for item in contract.aggregation_requests if item.function}
    # avg·percentile과 count가 같이 있으면 한 행 다중 지표(scalar)
    if fns - {"count"}:
        return "scalar"
    if contract.wants_count or (contract.operation == "aggregate" and fns <= {"count"}):
        return "count"
    return contract.operation or "count"


def merge_contract(
    prev: QueryContract,
    delta: QueryContract,
    binding: Any | None = None,
) -> QueryContract:
    """직전 Contract에 후속 Δ를 병합한다. 직전 SQL을 재사용하지 않는다.

    결합 문장에 앞 질문의 '몇 채'가 남아 extract가 count로 기울 수 있다.
    Δ가 구간·목록이면 그걸 이긴다.
    """
    prev_q = (prev.question or "").strip()
    delta_q = (delta.question or "").strip()
    combined = prev_q
    if delta_q and delta_q not in prev_q:
        combined = f"{prev_q} {delta_q}".strip()
    merged = extract_contract(combined, binding=binding)
    if not delta.places and prev.places and not merged.places:
        merged.places = list(prev.places)
    if delta.fixed_bins or delta.group_fields or _GROUP_KIND_RE.search(
        delta.question or ""
    ):
        merged.query_kind = "group"
        merged.wants_count = False
    elif delta.wants_count:
        merged.wants_count = True
        merged.query_kind = "count"
        merged.operation = "aggregate"
    elif delta.query_kind and delta.query_kind != "count":
        merged.query_kind = delta.query_kind
        merged.wants_count = False
        if delta.query_kind == "list":
            merged.operation = "list"
    elif delta.query_kind and delta.query_kind != prev.query_kind:
        merged.query_kind = delta.query_kind
    if prev.datasets and not merged.datasets:
        merged.datasets = list(prev.datasets)
    return merged


def _categorical_metrics(question: str) -> list[Span]:
    from llm2sql.domain import (
        USAGE_ALIASES,
        extract_special_land,
        extract_structures,
    )

    found: list[Span] = []
    occupied: list[tuple[int, int]] = []
    for alias in sorted(USAGE_ALIASES, key=len, reverse=True):
        start = 0
        while True:
            i = question.find(alias, start)
            if i < 0:
                break
            end = i + len(alias)
            if not any(not (end <= a or i >= b) for a, b in occupied):
                occupied.append((i, end))
                found.append(
                    Span(
                        kind="metric",
                        text=alias,
                        start=i,
                        end=end,
                        value="usage",
                        meta={"field": "usage", "canonical": USAGE_ALIASES[alias]},
                    )
                )
            start = end
    for alias, pattern in extract_structures(question):
        i = question.find(alias)
        if i < 0:
            continue
        found.append(
            Span(
                kind="metric",
                text=alias,
                start=i,
                end=i + len(alias),
                value="structure",
                meta={"field": "structure", "pattern": pattern},
            )
        )
    for hint in ("위반건축물", "위반건축", "위반 건축"):
        i = question.find(hint)
        if i < 0:
            continue
        found.append(
            Span(
                kind="metric",
                text=hint,
                start=i,
                end=i + len(hint),
                value="violation_status",
                meta={"field": "violation_status"},
            )
        )
        break
    special = extract_special_land(question)
    if special is not None:
        label, _sql = special
        i = question.find(label) if label in question else 0
        found.append(
            Span(
                kind="metric",
                text=label,
                start=max(0, i),
                end=max(0, i) + len(label),
                value="special_land",
                meta={"field": "special_land"},
            )
        )
    return found

