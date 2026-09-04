"""Bridge legacy router into LogicalPlan/PhysicalPlan executors.

Public entry still accepts a question string (adapter), but meaning is taken
from QueryIR / LogicalPlan — executors must not invent new semantics from NL.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg

from txt2sql.planner.logical import LogicalPlan, build_logical_plan
from txt2sql.planner.physical import PhysicalPlan, reject_partial_execution, select_physical_plan
from txt2sql.query_ir.adapters import contract_to_query_ir
from txt2sql.query_ir.models import QueryIR
from txt2sql.query_understanding.contract import extract_contract


@dataclass
class ExecutionPlanBundle:
    query_ir: QueryIR
    logical: LogicalPlan
    physical: PhysicalPlan


def build_execution_plan(question: str, *, contract: Any | None = None) -> ExecutionPlanBundle:
    c = contract if contract is not None else extract_contract(question)
    ir = contract_to_query_ir(c)
    # Enrich temporal/group slots from NL before completeness + binding.
    from txt2sql.planner.semantic_executor import refine_query_ir_for_compile

    ir = refine_query_ir_for_compile(ir, question=question)
    logical = build_logical_plan(ir)
    physical = select_physical_plan(logical, question=question)
    reject_partial_execution(physical)
    return ExecutionPlanBundle(query_ir=ir, logical=logical, physical=physical)


def route_allowed_by_plan(bundle: ExecutionPlanBundle) -> bool:
    """Block legacy route execution when LogicalPlan is incomplete."""
    if bundle.logical.status != "READY":
        return False
    if bundle.physical.partial:
        return False
    return True


def try_route_via_plan(
    question: str,
    conn: psycopg.Connection | None = None,
    *,
    contract: Any | None = None,
) -> Any | None:
    """Adapter: question -> QueryIR -> Logical/Physical -> legacy executor compile.

    If the plan is not READY, return None so the pipeline can use SQP/RAG.
    Legacy `try_route` still produces SQL, but only after plan gate passes for
    complex queries; simple fast-path strategies always consult legacy router.
    """
    from txt2sql.intent_router import try_route

    bundle = build_execution_plan(question, contract=contract)
    strategy = bundle.physical.strategy

    # Incomplete semantics: do not allow partial legacy route hit.
    if bundle.logical.status in {"CLARIFY", "UNSUPPORTED"}:
        return None
    if bundle.logical.status == "REPLAN" and strategy not in {
        "FAST_SIMPLE_COUNT",
        "FAST_THRESHOLD",
    }:
        return None

    routed = try_route(question, conn=conn)
    if routed is None:
        return None

    # Annotate route meta for observability without changing SQL.
    meta = getattr(routed, "meta", None)
    if isinstance(meta, dict):
        meta = {
            **meta,
            "query_ir_task": bundle.query_ir.task,
            "logical_status": bundle.logical.status,
            "physical_strategy": strategy,
        }
        try:
            routed.meta = meta  # type: ignore[misc]
        except Exception:
            pass
    return routed
