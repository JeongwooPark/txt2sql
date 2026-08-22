"""직전 SemanticQueryPlan에 후속 delta를 병합한다.

LLM 없이 add_filter / change_sort / change_limit / add_select 를 처리한다.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from llm2sql.domain import extract_gu, extract_place, has_anaphora, looks_like_standalone_question
from llm2sql.semantic_plan.generator import extract_plan_hints
from llm2sql.semantic_plan.models import (
    FilterSpec,
    OrderSpec,
    QueryKind,
    ScopeSpec,
    SemanticQueryPlan,
)
from llm2sql.session import SessionContext


class PlanDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    add_filters: list[FilterSpec] = Field(default_factory=list)
    change_sort: list[OrderSpec] | None = None
    change_limit: int | None = Field(default=None, ge=1, le=1000)
    add_select: list[str] = Field(default_factory=list)
    change_scope: ScopeSpec | None = None
    change_kind: QueryKind | None = None


def is_semantic_plan_followup(question: str, session: SessionContext | None) -> bool:
    if session is None:
        return False
    q = question.strip()
    if not q:
        return False
    route = str(session.last_semantic_plan_route or session.last_route or "")
    has_plan = bool(session.last_semantic_plan)
    has_d010 = bool(session.last_sql and "AL_D010" in session.last_sql)
    if has_plan:
        if not route.startswith("semantic_plan_") and not has_d010:
            return False
    elif not has_d010:
        return False
    if route.startswith(("clarify", "chart_help", "guide")):
        return False
    delta = parse_followup_delta(q)
    events = parse_followup_events(q)
    if delta is None and not events:
        return False
    if has_anaphora(q) or any(k in q for k in ("그중", "그 중", "이 중", "그중에")):
        return True
    if extract_gu(q) or extract_place(q):
        return False
    if looks_like_standalone_question(q) and len(q) >= 28:
        return False
    return True


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

    add_select: list[str] = []
    if any(k in q for k in ("건물명", "이름도", "이름과")):
        add_select.append("name")
    if "지번" in q:
        add_select.append("lot_address")
    if "용도도" in q or "용도와" in q:
        add_select.append("usage")
    if "높이도" in q or "높이와" in q:
        add_select.append("height_m")

    change_kind: QueryKind | None = None
    if any(k in q for k in ("몇 채", "몇채", "건수")):
        change_kind = "count"

    if (
        not add_filters
        and change_sort is None
        and change_limit is None
        and not add_select
        and change_kind is None
    ):
        return None
    return PlanDelta(
        add_filters=add_filters,
        change_sort=change_sort,
        change_limit=change_limit,
        add_select=add_select,
        change_kind=change_kind,
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
        if data.get("query_kind") == "count":
            data["query_kind"] = "list"

    if delta.change_scope is not None:
        data["scope"] = delta.change_scope.model_dump()

    if delta.change_kind is not None:
        data["query_kind"] = delta.change_kind
        if delta.change_kind == "count":
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
    return apply_plan_events(plan, combined), combined


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
