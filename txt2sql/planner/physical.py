"""Physical plan selection from LogicalPlan (no NL re-interpretation)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from txt2sql.planner.logical import LogicalPlan

PhysicalStrategy = Literal[
    "FAST_SIMPLE_COUNT",
    "FAST_THRESHOLD",
    "D010_EXECUTOR",
    "D198_EXECUTOR",
    "BASIC_ZONE_EXECUTOR",
    "SPATIAL_EXECUTOR",
    "GENERIC_SQL_EXECUTOR",
]


@dataclass(frozen=True)
class PhysicalPlan:
    strategy: PhysicalStrategy
    logical: LogicalPlan
    cost: float
    reasons: tuple[str, ...] = ()
    covered_ops: tuple[str, ...] = ()
    partial: bool = False


def _collect_ops(node) -> list[str]:
    out = [node.op]
    for child in node.children:
        out.extend(_collect_ops(child))
    return out


def _has_op(ops: list[str], name: str) -> bool:
    return name in ops


def select_physical_plan(logical: LogicalPlan) -> PhysicalPlan:
    """Select an executor strategy from LogicalPlan only.

    Partial coverage is never returned as executable: if a candidate cannot
    cover all ops, fall through to GENERIC_SQL_EXECUTOR or mark unsupported.
    """
    if logical.status != "READY":
        return PhysicalPlan(
            strategy="GENERIC_SQL_EXECUTOR",
            logical=logical,
            cost=10_000,
            reasons=(f"not_ready:{logical.status}", *logical.reason_codes),
            covered_ops=(),
            partial=False,
        )

    ops = _collect_ops(logical.root)
    ir = logical.query_ir
    datasets = {b.dataset for b in logical.bindings}

    # Fast simple count: Scan + optional scope Filter + Aggregate(count) only
    simple_count = (
        ir.task == "count"
        and not ir.spatial
        and ir.temporal is None
        and len([p for p in ir.predicates if p.field and p.field not in {None}]) <= 1
        and not ir.dimensions
        and not any(a.function not in {"count"} for a in ir.aggregations)
    )
    if simple_count and not _has_op(ops, "SpatialFilter") and not _has_op(ops, "TemporalFilter"):
        # threshold vs place-only
        has_threshold = any(
            p.operator in {"gt", "gte", "lt", "lte", "between"} and p.field
            for p in ir.predicates
        )
        if has_threshold and len(ir.predicates) <= 2:
            return PhysicalPlan(
                strategy="FAST_THRESHOLD",
                logical=logical,
                cost=1.0,
                reasons=("simple_threshold_count",),
                covered_ops=tuple(ops),
                partial=False,
            )
        if not has_threshold:
            return PhysicalPlan(
                strategy="FAST_SIMPLE_COUNT",
                logical=logical,
                cost=0.5,
                reasons=("simple_count",),
                covered_ops=tuple(ops),
                partial=False,
            )

    if _has_op(ops, "SpatialFilter") or ir.spatial:
        return PhysicalPlan(
            strategy="SPATIAL_EXECUTOR",
            logical=logical,
            cost=5.0,
            reasons=("spatial_ops_present",),
            covered_ops=tuple(ops),
            partial=False,
        )

    if ir.entity == "basic_zone" or "basic_zone" in datasets:
        return PhysicalPlan(
            strategy="BASIC_ZONE_EXECUTOR",
            logical=logical,
            cost=4.0,
            reasons=("basic_zone_entity",),
            covered_ops=tuple(ops),
            partial=False,
        )

    if "building_attr_d198" in datasets and "building_gis_d010" not in datasets:
        return PhysicalPlan(
            strategy="D198_EXECUTOR",
            logical=logical,
            cost=3.0,
            reasons=("d198_binding",),
            covered_ops=tuple(ops),
            partial=False,
        )

    if "building_gis_d010" in datasets or ir.entity == "building":
        return PhysicalPlan(
            strategy="D010_EXECUTOR",
            logical=logical,
            cost=2.0,
            reasons=("d010_binding_or_building",),
            covered_ops=tuple(ops),
            partial=False,
        )

    return PhysicalPlan(
        strategy="GENERIC_SQL_EXECUTOR",
        logical=logical,
        cost=8.0,
        reasons=("fallback_generic",),
        covered_ops=tuple(ops),
        partial=False,
    )


def reject_partial_execution(plan: PhysicalPlan) -> PhysicalPlan:
    """Hard guard: never execute a partial plan."""
    if plan.partial:
        raise RuntimeError("partial semantic coverage execution is forbidden")
    ops = set(_collect_ops(plan.logical.root))
    covered = set(plan.covered_ops)
    if covered and ops - covered:
        raise RuntimeError(f"partial coverage detected: missing={ops - covered}")
    return plan
