"""Deterministic SQL compiler facade.

Delegates to existing semantic_plan compiler while enforcing that inputs are
PhysicalPlan + bindings — not free-form NL interpretation.
"""

from __future__ import annotations

from typing import Any

from txt2sql.planner.physical import PhysicalPlan
from txt2sql.query_ir.adapters import query_ir_to_semantic_plan
from txt2sql.query_ir.normalize import assert_no_physical_names


def compile_physical_plan(physical: PhysicalPlan, *, settings: Any | None = None) -> str:
    """Compile Logical/Physical plan to SQL via shared deterministic compiler."""
    assert_no_physical_names(physical.logical.query_ir.model_dump())
    plan = query_ir_to_semantic_plan(physical.logical.query_ir)
    from txt2sql.semantic_plan.compiler import compile_semantic_plan

    return compile_semantic_plan(plan)


def compile_plan_safe(physical: PhysicalPlan) -> tuple[str | None, str | None]:
    try:
        sql = compile_physical_plan(physical)
        return sql, None
    except Exception as exc:  # noqa: BLE001 — surface compile errors to caller
        return None, str(exc)
