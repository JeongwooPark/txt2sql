"""Plan 노드가 SQL compile_trace에 모두 남았는지 검사한다. 누락이면 실행 금지."""

from __future__ import annotations

from llm2sql.semantic_plan.compiler import CompiledSemanticQuery
from llm2sql.semantic_plan.models import SemanticQueryPlan
from llm2sql.semantic_plan.predicate_utils import (
    effective_predicate,
    has_op,
    predicate_atoms,
)


def verify_plan_to_sql(
    plan: SemanticQueryPlan,
    compiled: CompiledSemanticQuery,
) -> list[str]:
    errors: list[str] = []
    extra = compiled.extra or {}
    trace = extra.get("compile_trace") or {}
    pred = effective_predicate(plan)
    atoms = predicate_atoms(pred)
    compiled_nodes = list(trace.get("predicate_nodes") or [])
    if atoms and len(compiled_nodes) < len(atoms):
        errors.append("PREDICATE_DROPPED")
    sql = compiled.sql.upper()
    if pred and has_op(pred, "or") and " OR " not in sql:
        errors.append("BOOLEAN_OR_DROPPED")
    if pred and has_op(pred, "not") and "NOT " not in sql and "NOT IN" not in sql and "<>" not in sql:
        errors.append("BOOLEAN_NOT_DROPPED")
    wanted_aggs = {item.function.upper() for item in plan.aggregations}
    got_aggs = {str(fn).upper() for fn in (trace.get("aggregations") or [])}
    if wanted_aggs and not wanted_aggs.issubset(got_aggs):
        for fn in wanted_aggs:
            token = "COUNT(" if fn == "COUNT" else f"{fn}("
            if token not in sql:
                errors.append("OUTPUT_SHAPE_MISMATCH")
                break
    if plan.spatial_relations:
        if "ST_" not in sql:
            errors.append("SPATIAL_TARGET_DROPPED")
    return list(dict.fromkeys(errors))
