"""Logical + physical planner for QueryIR."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from txt2sql.query_ir.completeness import CompletenessReport, assess_completeness
from txt2sql.query_ir.models import QueryIR
from txt2sql.semantic_catalog.binding import BindingResult, SemanticBinding, bind_concepts

PlanStatus = Literal["READY", "REPLAN", "CLARIFY", "UNSUPPORTED"]

# Compatibility aliases for legacy policy codes
P03 = "P03"
P07 = "P07"
SEMANTIC_UNBOUND_METRIC = "SEMANTIC_UNBOUND_METRIC"
SEMANTIC_GRAIN_MISMATCH = "SEMANTIC_GRAIN_MISMATCH"
SEMANTIC_DATASET_CONFLICT = "SEMANTIC_DATASET_CONFLICT"
SEMANTIC_INCOMPLETE_AGGREGATION = "SEMANTIC_INCOMPLETE_AGGREGATION"
SEMANTIC_UNBOUND_TEMPORAL = "SEMANTIC_UNBOUND_TEMPORAL"
SEMANTIC_OUTPUT_MISMATCH = "SEMANTIC_OUTPUT_MISMATCH"


@dataclass
class LogicalNode:
    op: str
    args: dict[str, Any] = field(default_factory=dict)
    children: list[LogicalNode] = field(default_factory=list)


@dataclass
class LogicalPlan:
    root: LogicalNode
    query_ir: QueryIR
    bindings: list[SemanticBinding] = field(default_factory=list)
    binding_result: BindingResult | None = None
    completeness: CompletenessReport | None = None
    status: PlanStatus = "READY"
    reason_codes: list[str] = field(default_factory=list)

    @property
    def has_unresolved(self) -> bool:
        return self.status != "READY" or bool(self.reason_codes)


def _scan(entity: str) -> LogicalNode:
    return LogicalNode(op="Scan", args={"entity": entity})


def build_logical_plan(ir: QueryIR, *, bindings: BindingResult | None = None) -> LogicalPlan:
    tokens: list[str] = []
    for m in ir.measures:
        tokens.append(m.concept)
    for a in ir.aggregations:
        if a.field:
            tokens.append(a.field)
        if a.left:
            tokens.append(a.left)
        if a.right:
            tokens.append(a.right)
    for p in ir.predicates:
        if p.field:
            tokens.append(p.field)
        if p.value_field:
            tokens.append(p.value_field)
    for d in ir.dimensions:
        tokens.append(d.field)

    binding_result = bindings or bind_concepts(tokens)
    completeness = assess_completeness(ir)

    node = _scan(ir.entity)
    if ir.scope and ir.scope.place:
        node = LogicalNode(op="Filter", args={"scope": ir.scope.place}, children=[node])
    for pred in ir.predicates:
        if pred.children:
            node = LogicalNode(
                op="Filter",
                args={"logical": pred.logical_group, "children": len(pred.children)},
                children=[node],
            )
            continue
        node = LogicalNode(
            op="Filter",
            args={
                "field": pred.field,
                "operator": pred.operator,
                "value": pred.value,
                "value2": pred.value2,
                "value_field": pred.value_field,
                "negated": pred.negated,
            },
            children=[node],
        )
    if ir.temporal is not None:
        node = LogicalNode(op="TemporalFilter", args=ir.temporal.model_dump(), children=[node])
    for spatial in ir.spatial:
        node = LogicalNode(op="SpatialFilter", args=spatial.model_dump(), children=[node])

    if ir.outputs or ir.measures:
        fields = list(ir.outputs) or [m.concept for m in ir.measures]
        node = LogicalNode(op="Project", args={"fields": fields}, children=[node])

    for agg in ir.aggregations:
        op = {
            "ratio": "Ratio",
            "derived": "DerivedMetric",
            "percentile": "Percentile",
        }.get(agg.function, "Aggregate")
        node = LogicalNode(op=op, args=agg.model_dump(), children=[node])

    if ir.dimensions:
        node = LogicalNode(
            op="Group",
            args={"fields": [d.field for d in ir.dimensions], "bins": any(d.bins for d in ir.dimensions)},
            children=[node],
        )
    for cmp_ in ir.comparisons:
        node = LogicalNode(op="Compare", args=cmp_.model_dump(), children=[node])
    if ir.ordering:
        node = LogicalNode(
            op="Sort",
            args={"orders": [o.model_dump() for o in ir.ordering]},
            children=[node],
        )
    if ir.limit is not None:
        node = LogicalNode(op="Limit", args={"limit": ir.limit}, children=[node])

    reason_codes = list(completeness.reasons)
    reason_codes.extend(binding_result.unresolved and [f"SEMANTIC_UNBOUND_METRIC:{u}" for u in binding_result.unresolved] or [])
    reason_codes.extend(binding_result.conflicts)

    status: PlanStatus = completeness.status  # type: ignore[assignment]
    if binding_result.unresolved and status == "READY":
        status = "REPLAN"
    if any("CONFLICT" in c for c in binding_result.conflicts) and status == "READY":
        status = "REPLAN"

    # Map to legacy aliases when useful
    if SEMANTIC_UNBOUND_METRIC in reason_codes or any(r.startswith("SEMANTIC_UNBOUND_METRIC") for r in reason_codes):
        reason_codes.append(P03)
    if SEMANTIC_INCOMPLETE_AGGREGATION in reason_codes:
        reason_codes.append(P07)

    return LogicalPlan(
        root=node,
        query_ir=ir,
        bindings=list(binding_result.bindings),
        binding_result=binding_result,
        completeness=completeness,
        status=status,
        reason_codes=list(dict.fromkeys(reason_codes)),
    )


def assert_executable(plan: LogicalPlan) -> None:
    if plan.status != "READY" or plan.has_unresolved and plan.status != "READY":
        if plan.status != "READY":
            raise RuntimeError(f"logical plan not executable: {plan.status} {plan.reason_codes}")
