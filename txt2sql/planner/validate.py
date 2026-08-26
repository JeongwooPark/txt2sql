"""Logical plan validation helpers."""

from __future__ import annotations

from txt2sql.planner.logical import LogicalPlan, PlanStatus


def validate_logical_plan(plan: LogicalPlan) -> PlanStatus:
    if plan.completeness and plan.completeness.status != "READY":
        return plan.completeness.status  # type: ignore[return-value]
    if plan.query_ir.unresolved:
        if any("CLARIFY" in u.code.upper() or "AMBIG" in u.code.upper() for u in plan.query_ir.unresolved):
            return "CLARIFY"
        if any("UNSUPPORTED" in u.code.upper() for u in plan.query_ir.unresolved):
            return "UNSUPPORTED"
        return "REPLAN"
    return plan.status
