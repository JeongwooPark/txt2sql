"""Result shape inference from LogicalPlan / QueryIR."""

from __future__ import annotations

from txt2sql.planner.logical import LogicalPlan
from txt2sql.query_ir.normalize import result_shape_for_task


def infer_result_shape(plan: LogicalPlan) -> str:
    return result_shape_for_task(plan.query_ir.task)
