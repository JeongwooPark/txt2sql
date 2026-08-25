"""직전 SemanticQueryPlan에 후속 delta를 병합한다.

LLM 없이 add_filter / change_sort / change_limit / add_select 를 처리한다.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from txt2sql.domain import (
    extract_gu,
    extract_industrial_names,
    extract_place,
    has_anaphora,
    looks_like_standalone_question,
)
from txt2sql.query_understanding.contract import extract_contract
from txt2sql.semantic_plan.generator import _agg_metrics, extract_plan_hints
from txt2sql.semantic_plan.migrate import filter_to_predicate
from txt2sql.semantic_plan.models import (
    AggregationSpec,
    FilterSpec,
    OrderSpec,
    PlaceSpec,
    QueryKind,
    ScopeSpec,
    SemanticQueryPlan,
    SpatialRelationSpec,
    SpatialTargetSpec,
)
from txt2sql.semantic_plan.predicate_utils import and_predicates
from txt2sql.session import SessionContext


class PlanDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    add_filters: list[FilterSpec] = Field(default_factory=list)
    change_sort: list[OrderSpec] | None = None
    change_limit: int | None = Field(default=None, ge=1, le=1000)
    add_select: list[str] = Field(default_factory=list)
    change_scope: ScopeSpec | None = None
    change_kind: QueryKind | None = None
    change_aggregations: list[AggregationSpec] | None = None
    add_spatial: list[SpatialRelationSpec] = Field(default_factory=list)


def is_semantic_plan_followup(question: str, session: SessionContext | None) -> bool:
    if session is None:
        return False
    q = question.strip()
    if not q:
        return False
    route = str(session.last_semantic_plan_route or session.last_route or "")
    has_plan = bool(session.last_semantic_plan)
    last_sql = str(session.last_sql or "")
    has_building_sql = "AL_D010" in last_sql or "AL_D198" in last_sql
    if has_plan:
        pass
    elif not has_building_sql:
        return False
    if route.startswith(("clarify", "chart_help", "guide")):
        return False
    if has_anaphora(q) or any(
        k in q for k in ("그중", "그 중", "이 중", "이중에", "이 중에", "그중에")
    ):
        return True
    if _is_short_attr_followup(q) and (
        session.focus_row or session.result_anchors
    ):
        return True
    delta = parse_followup_delta(q)
    events = parse_followup_events(q)
    if delta is None and not events:
        return False
    if extract_gu(q) or extract_place(q):
        token = extract_gu(q) or extract_place(q) or ""
        parent_blob = " ".join(
            [
                str(session.last_question or ""),
                str(session.last_full_question or ""),
                str(session.last_semantic_plan or ""),
            ]
        )
        if token and token not in parent_blob:
            return False
    if looks_like_standalone_question(q) and len(q) >= 28:
        return False
    return True


def _is_short_attr_followup(question: str) -> bool:
    q = question.strip()
    if any(k in q for k in ("지번", "주소", "높이", "이름", "건물명")) and len(q) <= 24:
        return True
    return False


def parse_followup_delta(question: str) -> PlanDelta | None:
    q = question.strip()
    if not q:
        return None
    hints = extract_plan_hints(q)
    add_filters: list[FilterSpec] = []
    if hints.get("usage"):
        add_filters.append(FilterSpec(field="usage", operator="eq", value=hints["usage"]))
    if hints.get("structure"):
        add_filters.append(
            FilterSpec(field="structure", operator="contains", value=hints["structure"])
        )
    for item in hints.get("numeric_expressions") or []:
        add_filters.append(
            FilterSpec(
                field=item["field"],
                operator=item["operator"],
                value=item["value"],
                unit=item.get("unit"),
            )
        )
    try:
        contract = extract_contract(q)
    except Exception:
        contract = None
    if contract is not None:
        bound_fields = {item.field for item in add_filters}
        for span in contract.ranges:
            field = span.meta.get("field")
            if not field or field in bound_fields:
                continue
            add_filters.append(
                FilterSpec(
                    field=field,
                    operator="between",
                    value=span.meta.get("low"),
                    value2=span.meta.get("high"),
                )
            )
            bound_fields.add(field)
        for span in contract.numbers:
            field = span.meta.get("field")
            if not field or field in bound_fields:
                continue
            rel = span.meta.get("rel") or span.meta.get("lo_rel") or "gte"
            op = {"이상": "gte", "초과": "gt", "이하": "lte", "미만": "lt"}.get(
                str(rel), "gte"
            )
            add_filters.append(
                FilterSpec(field=field, operator=op, value=span.value)
            )
            bound_fields.add(field)

    change_sort: list[OrderSpec] | None = None
    if any(k in q for k in ("높이 순", "높은 순", "높이순", "높이로")):
        change_sort = [OrderSpec(field="height_m", direction="desc", nulls="last")]
    elif any(k in q for k in ("연면적 순", "큰 순", "면적 순", "연면적으로")):
        change_sort = [
            OrderSpec(field="gross_floor_area_m2", direction="desc", nulls="last")
        ]
    elif any(k in q for k in ("층수 순", "높은 층", "층 순")):
        change_sort = [OrderSpec(field="ground_floors", direction="desc", nulls="last")]

    change_limit: int | None = None
    limit_m = re.search(
        r"(?:상위\s*)?(\d+)\s*(?:개|곳|채|동)\s*(?:만|로|으로)?",
        q,
    )
    if limit_m and any(k in q for k in ("만", "보여", "출력", "개", "상위")):
        change_limit = max(1, min(int(limit_m.group(1)), 1000))
    if change_limit is None and re.search(
        r"(첫\s*번째|첫번째|1번째|(?<![가-힣])그 건물(?!들)|해당 건물(?!들))",
        q,
    ):
        change_limit = 1

    add_select: list[str] = []
    if any(k in q for k in ("건물명", "이름도", "이름과", "이름")):
        add_select.append("name")
    if "지번" in q:
        add_select.append("lot_address")
    if any(k in q for k in ("법정동", "주소")):
        add_select.append("legal_dong")
    if "용도도" in q or "용도와" in q:
        add_select.append("usage")
    if "높이도" in q or "높이와" in q:
        add_select.append("height_m")

    change_kind: QueryKind | None = None
    if any(k in q for k in ("몇 채", "몇채", "건수", "채수", "얼마나")):
        change_kind = "count"

    change_aggregations: list[AggregationSpec] | None = None
    from txt2sql.query_understanding.operators import AGG_MAP

    picked_fn: str | None = None
    for text, fn in AGG_MAP.items():
        if text not in q:
            continue
        if text in {"최대", "최소"} and any(
            k in q for k in ("가장", "제일", "상위")
        ):
            continue
        picked_fn = fn
        break
    if picked_fn is not None:
        metrics = _agg_metrics(q)
        change_aggregations = [
            AggregationSpec(function=picked_fn, field=metric, alias=f"{picked_fn}_{metric}")
            for metric in metrics
        ]
        change_kind = "aggregate"
    if any(k in q for k in ("가장 높", "제일 높", "가장 높은", "제일 높은")):
        change_sort = [OrderSpec(field="height_m", direction="desc", nulls="last")]
        if change_limit is None:
            change_limit = 1
        if change_kind is None and change_aggregations is None:
            change_kind = "rank"
    elif any(k in q for k in ("가장 큰", "제일 큰", "가장 넓", "제일 넓")):
        change_sort = [
            OrderSpec(field="gross_floor_area_m2", direction="desc", nulls="last")
        ]
        if change_limit is None:
            change_limit = 1
        if change_kind is None and change_aggregations is None:
            change_kind = "rank"
    elif any(k in q for k in ("층수가 가장", "층이 가장", "가장 많은 층")):
        change_sort = [
            OrderSpec(field="ground_floors", direction="desc", nulls="last")
        ]
        if change_limit is None:
            change_limit = 1
        if change_kind is None and change_aggregations is None:
            change_kind = "rank"

    if change_kind == "rank" or (
        change_sort is not None and change_limit == 1 and change_aggregations is None
    ):
        for key in ("name", "legal_dong", "lot_address"):
            if key not in add_select:
                add_select.append(key)
        if any(k in q for k in ("층수", "지상층")) and "ground_floors" not in add_select:
            add_select.append("ground_floors")

    add_spatial: list[SpatialRelationSpec] = []
    if "산업단지" in q and any(k in q for k in ("안", "내", "교차", "속한")):
        names = extract_industrial_names(q)
        place = None
        if names:
            place = PlaceSpec(name="·".join(names[:4]), kind="unknown")
        add_spatial.append(
            SpatialRelationSpec(
                relation="intersects",
                target=SpatialTargetSpec(entity="industrial_complex", place=place),
            )
        )

    _subset = any(
        k in q for k in ("그중", "그 중", "이 중", "이중에", "이 중에", "그중에")
    )
    _listish = any(
        k in q
        for k in ("이름", "건물명", "지번", "목록", "보여", "리스트", "가장", "제일")
    )
    if (
        _subset
        and (add_filters or add_spatial)
        and not _listish
        and change_kind is None
        and change_aggregations is None
    ):
        change_kind = "count"

    if (
        not add_filters
        and change_sort is None
        and change_limit is None
        and not add_select
        and change_kind is None
        and change_aggregations is None
        and not add_spatial
    ):
        return None
    return PlanDelta(
        add_filters=add_filters,
        change_sort=change_sort,
        change_limit=change_limit,
        add_select=add_select,
        change_kind=change_kind,
        change_aggregations=change_aggregations,
        add_spatial=add_spatial,
    )


def apply_plan_delta(base: SemanticQueryPlan, delta: PlanDelta) -> SemanticQueryPlan:
    data: dict[str, Any] = base.model_dump()
    filters = list(base.filters)
    for spec in delta.add_filters:
        filters = [
            item
            for item in filters
            if not (item.field == spec.field and item.operator == spec.operator)
        ]
        filters.append(spec)
    data["filters"] = [item.model_dump() for item in filters]
    extras = [filter_to_predicate(spec) for spec in delta.add_filters]
    merged_pred = and_predicates([base.predicate, *extras])
    data["predicate"] = merged_pred.model_dump() if merged_pred is not None else None

    if delta.change_sort is not None:
        data["order_by"] = [item.model_dump() for item in delta.change_sort]
        if data.get("query_kind") == "list":
            data["query_kind"] = "rank"
        metric = delta.change_sort[0].field if delta.change_sort else None
        select = list(data.get("select") or [])
        if metric and metric not in select:
            select.append(metric)
        data["select"] = select

    if delta.change_limit is not None:
        data["limit"] = delta.change_limit

    if delta.add_select:
        select = list(data.get("select") or [])
        for key in delta.add_select:
            if key not in select:
                select.append(key)
        data["select"] = select
        if data.get("query_kind") == "count" and any(
            key in {"name", "lot_address"} for key in delta.add_select
        ):
            data["query_kind"] = "list"

    if delta.change_aggregations is not None:
        aggs = list(delta.change_aggregations)
        if not any(item.function == "count" for item in aggs):
            aggs.insert(0, AggregationSpec(function="count", field=None, alias="n"))
        data["aggregations"] = [item.model_dump() for item in aggs]
        data["query_kind"] = "aggregate"
        data["select"] = []
        data["limit"] = None

    if delta.change_scope is not None:
        data["scope"] = delta.change_scope.model_dump()

    if delta.change_kind is not None:
        data["query_kind"] = delta.change_kind
        if delta.change_kind in {"count", "rank", "list"}:
            data["aggregations"] = []
        if delta.change_kind == "count":
            data["select"] = []
            data["limit"] = None
            data["order_by"] = []
        if delta.change_kind == "rank":
            select = list(data.get("select") or [])
            for key in ("name", "legal_dong", "lot_address", "ground_floors"):
                if key not in select:
                    select.append(key)
            data["select"] = select
        if delta.change_kind == "aggregate":
            data["select"] = []
            data["limit"] = None
    elif delta.add_filters and base.query_kind == "count":
        data["query_kind"] = "count"
        data["select"] = []
        data["limit"] = None

    if delta.add_spatial:
        spatial = list(data.get("spatial_relations") or [])
        spatial.extend(item.model_dump() for item in delta.add_spatial)
        data["spatial_relations"] = spatial
        if data.get("query_kind") == "count":
            data["select"] = []
            data["limit"] = None

    assumptions = list(data.get("assumptions") or [])
    assumptions.append("plan_followup_delta")
    data["assumptions"] = assumptions
    return SemanticQueryPlan.model_validate(data)


PlanEventOp = Literal[
    "add_filter",
    "replace_filter",
    "remove_filter",
    "negate_filter",
    "change_scope",
    "change_order",
    "change_limit",
    "add_select",
    "change_kind",
    "add_spatial",
    "undo_last",
    "reset_to_base",
]


class PlanEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: PlanEventOp
    filter: FilterSpec | None = None
    field: str | None = None
    order_by: list[OrderSpec] | None = None
    limit: int | None = Field(default=None, ge=1, le=1000)
    scope: ScopeSpec | None = None
    select: list[str] = Field(default_factory=list)
    kind: QueryKind | None = None
    spatial: list[SpatialRelationSpec] = Field(default_factory=list)


def parse_followup_events(question: str) -> list[PlanEvent]:
    q = question.strip()
    if not q:
        return []
    if any(k in q for k in ("처음부터", "초기화", "원래대로")):
        return [PlanEvent(op="reset_to_base")]
    if any(k in q for k in ("방금 취소", "직전 취소", "되돌려", "직전을 취소")):
        return [PlanEvent(op="undo_last")]
    hints = extract_plan_hints(q)
    events: list[PlanEvent] = []
    if any(k in q for k in ("제외", "빼고", "아닌", "이외")) and hints.get("usage"):
        events.append(
            PlanEvent(
                op="negate_filter",
                filter=FilterSpec(field="usage", operator="eq", value=hints["usage"]),
            )
        )
    elif hints.get("usage") and any(k in q for k in ("바꿔", "대신", "으로 해")):
        events.append(
            PlanEvent(
                op="replace_filter",
                filter=FilterSpec(field="usage", operator="eq", value=hints["usage"]),
            )
        )
    delta = parse_followup_delta(q)
    if delta is not None:
        skip_usage_add = any(ev.op in {"negate_filter", "replace_filter"} for ev in events)
        for spec in delta.add_filters:
            if skip_usage_add and spec.field == "usage":
                continue
            events.append(PlanEvent(op="add_filter", filter=spec))
        if delta.change_sort is not None:
            events.append(PlanEvent(op="change_order", order_by=delta.change_sort))
        if delta.change_limit is not None:
            events.append(PlanEvent(op="change_limit", limit=delta.change_limit))
        if delta.add_select:
            events.append(PlanEvent(op="add_select", select=delta.add_select))
        if delta.change_scope is not None:
            events.append(PlanEvent(op="change_scope", scope=delta.change_scope))
        if delta.change_kind is not None:
            events.append(PlanEvent(op="change_kind", kind=delta.change_kind))
        if delta.add_spatial:
            events.append(PlanEvent(op="add_spatial", spatial=delta.add_spatial))
    if any(k in q for k in ("그 조건 빼", "필터 제거", "조건 제거")):
        field = "usage" if "용도" in q else None
        if field:
            events.append(PlanEvent(op="remove_filter", field=field))
    return events


def apply_plan_events(base: SemanticQueryPlan, events: list[PlanEvent]) -> SemanticQueryPlan:
    plan = base
    for event in events:
        if event.op in {"undo_last", "reset_to_base"}:
            continue
        plan = _apply_one_event(plan, event)
    assumptions = list(plan.assumptions or [])
    if events and "plan_followup_event" not in assumptions:
        assumptions.append("plan_followup_event")
    return plan.model_copy(update={"assumptions": assumptions})


def _apply_one_event(plan: SemanticQueryPlan, event: PlanEvent) -> SemanticQueryPlan:
    if event.op == "add_filter" and event.filter is not None:
        delta = PlanDelta(add_filters=[event.filter])
        return apply_plan_delta(plan, delta)
    if event.op == "replace_filter" and event.filter is not None:
        data = plan.model_dump()
        filters = [item for item in plan.filters if item.field != event.filter.field]
        filters.append(event.filter)
        data["filters"] = [item.model_dump() for item in filters]
        return SemanticQueryPlan.model_validate(data)
    if event.op == "remove_filter":
        field = event.field or (event.filter.field if event.filter else None)
        data = plan.model_dump()
        data["filters"] = [
            item.model_dump() for item in plan.filters if field and item.field != field
        ]
        return SemanticQueryPlan.model_validate(data)
    if event.op == "negate_filter" and event.filter is not None:
        data = plan.model_dump()
        rest = [
            item
            for item in plan.filters
            if not (item.field == event.filter.field and item.value == event.filter.value)
        ]
        negated = event.filter.model_copy(
            update={"operator": "neq" if event.filter.operator == "eq" else "eq"}
        )
        rest.append(negated)
        data["filters"] = [item.model_dump() for item in rest]
        return SemanticQueryPlan.model_validate(data)
    if event.op == "change_order" and event.order_by is not None:
        return apply_plan_delta(plan, PlanDelta(change_sort=event.order_by))
    if event.op == "change_limit" and event.limit is not None:
        return apply_plan_delta(plan, PlanDelta(change_limit=event.limit))
    if event.op == "change_scope" and event.scope is not None:
        return apply_plan_delta(plan, PlanDelta(change_scope=event.scope))
    if event.op == "add_select" and event.select:
        return apply_plan_delta(plan, PlanDelta(add_select=event.select))
    if event.op == "change_kind" and event.kind is not None:
        return apply_plan_delta(plan, PlanDelta(change_kind=event.kind))
    if event.op == "add_spatial" and event.spatial:
        return apply_plan_delta(plan, PlanDelta(add_spatial=event.spatial))
    return plan


def apply_followup_history(
    question: str,
    base: SemanticQueryPlan | dict[str, Any],
    prior_events: list[PlanEvent | dict[str, Any]] | None = None,
    *,
    base_override: SemanticQueryPlan | dict[str, Any] | None = None,
) -> tuple[SemanticQueryPlan, list[PlanEvent]] | None:
    new_events = parse_followup_events(question)
    if not new_events:
        return None
    root = base_override if base_override is not None else base
    plan = (
        root
        if isinstance(root, SemanticQueryPlan)
        else SemanticQueryPlan.model_validate(root)
    )
    combined: list[PlanEvent] = []
    for item in prior_events or []:
        combined.append(item if isinstance(item, PlanEvent) else PlanEvent.model_validate(item))
    for event in new_events:
        if event.op == "undo_last":
            if combined:
                combined.pop()
            continue
        if event.op == "reset_to_base":
            combined = []
            continue
        combined.append(event)
    plan = apply_plan_events(plan, combined)
    delta = parse_followup_delta(question)
    if delta is not None and delta.change_aggregations:
        plan = apply_plan_delta(
            plan,
            PlanDelta(
                change_aggregations=delta.change_aggregations,
                change_kind="aggregate",
            ),
        )
    if delta is not None and delta.add_spatial:
        plan = apply_plan_delta(
            plan,
            PlanDelta(
                add_spatial=delta.add_spatial,
                change_kind=delta.change_kind,
            ),
        )
    return plan, combined


def apply_result_anchor(
    question: str,
    plan: SemanticQueryPlan,
    session: SessionContext | None,
) -> SemanticQueryPlan:
    """그 건물/첫번째는 직전 결과 앵커를 고른다. 없으면 직전 rank를 limit 1로 유지."""
    if session is None:
        return plan
    if not re.search(
        r"(첫\s*번째|첫번째|1번째|(?<![가-힣])그 건물(?!들)|해당 건물(?!들)|"
        r"(?<![가-힣])그 아파트(?!들)|지번\s*알려|주소\s*알려|높이는\s*[?？]?$)",
        question,
    ):
        return plan
    anchors = list(session.result_anchors or [])
    data = plan.model_dump()
    if anchors:
        picked = anchors[0]
        filters = list(plan.filters)
        if picked.identity:
            filters.append(FilterSpec(field="id", operator="eq", value=picked.identity))
        elif picked.label:
            filters.append(FilterSpec(field="name", operator="eq", value=picked.label))
        data["filters"] = [item.model_dump() for item in filters]
        extras = [filter_to_predicate(item) for item in filters[len(plan.filters) :]]
        merged_pred = and_predicates([plan.predicate, *extras])
        data["predicate"] = merged_pred.model_dump() if merged_pred is not None else None
    data["limit"] = 1
    if data.get("query_kind") == "count":
        data["query_kind"] = "list"
    select = list(data.get("select") or [])
    if "지번" in question and "lot_address" not in select:
        select.append("lot_address")
        data["select"] = select
    if re.search(r"높이", question) and "height_m" not in select:
        select.append("height_m")
        data["select"] = select
    return SemanticQueryPlan.model_validate(data)


_COUNT_SPOKEN = re.compile(r"(모두\s*)?\d[\d,]*\s*(동|채|건)입니다")


def apply_count_display_followup(
    question: str,
    plan: SemanticQueryPlan,
    session: SessionContext | None,
) -> SemanticQueryPlan:
    """목록 SQL이 COUNT(*) OVER 또는 'N동입니다'면 그중만 필터도 count로 본다."""
    if session is None:
        return plan
    q = question.strip()
    if not any(k in q for k in ("그중", "그 중", "이 중", "이중에", "이 중에", "그중에")):
        return plan
    if any(
        k in q
        for k in ("이름", "건물명", "지번", "목록", "보여", "리스트", "가장", "제일")
    ):
        return plan
    if plan.query_kind in {"aggregate", "rank", "distribution"}:
        return plan
    sql = str(session.last_sql or "")
    answer = str(session.last_answer or "")
    over = bool(re.search(r"COUNT\s*\(\s*\*\s*\)\s+OVER", sql, re.I))
    spoken = bool(_COUNT_SPOKEN.search(answer))
    dumped = session.last_semantic_plan or {}
    dumped_count = dumped.get("query_kind") == "count"
    delta = parse_followup_delta(q)
    filter_only = bool(
        delta
        and (delta.add_filters or delta.add_spatial)
        and delta.change_kind in {None, "count"}
    )
    if not (over or spoken or dumped_count or plan.query_kind == "count" or filter_only):
        return plan
    if plan.query_kind == "count" and plan.limit is None:
        return plan
    data = plan.model_dump()
    data["query_kind"] = "count"
    data["select"] = []
    data["limit"] = None
    data["order_by"] = []
    return SemanticQueryPlan.model_validate(data)


def merge_followup_plan(
    question: str,
    base: SemanticQueryPlan | dict[str, Any],
) -> SemanticQueryPlan | None:
    plan = (
        base
        if isinstance(base, SemanticQueryPlan)
        else SemanticQueryPlan.model_validate(base)
    )
    history = apply_followup_history(question, plan)
    if history is None:
        return None
    return history[0]
