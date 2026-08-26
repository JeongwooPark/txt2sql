"""QueryIR interaction layer: follow-up / visualize / metadata deltas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from txt2sql.query_ir.models import InteractionIR, OrderingIR, PredicateIR, QueryIR

InteractionIntent = Literal[
    "new_query",
    "refine_query",
    "explain_result",
    "visualize",
    "metadata",
    "help",
    "none",
]


class QueryIRDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal[
        "add_filter",
        "replace_filter",
        "remove_filter",
        "change_sort",
        "change_limit",
        "add_output",
        "change_group",
        "change_aggregate",
        "set_presentation",
    ]
    payload: dict[str, Any] = Field(default_factory=dict)


def classify_interaction_intent(question: str, *, has_session: bool = False) -> InteractionIntent:
    q = question.strip()
    if any(k in q for k in ("도움", "help", "어떻게 쓰", "사용법")):
        return "help"
    if any(k in q for k in ("메타", "스키마", "컬럼", "테이블 목록", "무슨 데이터")):
        return "metadata"
    # Session refine beats visualize: "그중 상위 10개 지도에서" is a delta, not a new viz query.
    if has_session and any(
        k in q for k in ("그중", "그 중", "그중에서", "상위", "만 보여", "필터", "다시")
    ):
        return "refine_query"
    if any(k in q for k in ("차트", "그래프", "시각화", "지도로", "맵으로", "지도에서")):
        return "visualize"
    if any(k in q for k in ("왜", "설명", "근거", "어떻게 계산")):
        return "explain_result"
    return "new_query"


def apply_delta(ir: QueryIR, delta: QueryIRDelta) -> QueryIR:
    data = ir.model_copy(deep=True)
    op = delta.op
    p = delta.payload
    if op == "add_filter":
        data.predicates.append(PredicateIR(**p))
    elif op == "replace_filter":
        field = p.get("field")
        data.predicates = [x for x in data.predicates if x.field != field]
        data.predicates.append(PredicateIR(**p))
    elif op == "remove_filter":
        field = p.get("field")
        data.predicates = [x for x in data.predicates if x.field != field]
    elif op == "change_sort":
        data.ordering = [OrderingIR(**p)]
    elif op == "change_limit":
        data.limit = int(p["limit"])
    elif op == "add_output":
        field = str(p.get("field") or "")
        if field and field not in data.outputs:
            data.outputs.append(field)
    elif op == "change_group":
        from txt2sql.query_ir.models import DimensionIR

        fields = list(p.get("fields") or [])
        data.dimensions = [DimensionIR(field=f) for f in fields]
    elif op == "change_aggregate":
        from txt2sql.query_ir.models import AggregationIR

        data.aggregations = [AggregationIR(**p)]
    elif op == "set_presentation":
        presentation = p.get("presentation")
        data.interaction = InteractionIR(
            intent=data.interaction.intent,
            presentation=presentation,
            deltas=list(data.interaction.deltas) + [delta.model_dump()],
        )
    return data


def refine_with_limit_and_map(previous: QueryIR, *, limit: int = 10) -> QueryIR:
    ir = apply_delta(previous, QueryIRDelta(op="change_limit", payload={"limit": limit}))
    return apply_delta(ir, QueryIRDelta(op="set_presentation", payload={"presentation": "map"}))
