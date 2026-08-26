"""Execute Logical/Physical plans through deterministic compiler (semantic-v2)."""

from __future__ import annotations

from typing import Any

import psycopg

from txt2sql.compiler.safety import validate_compiled_sql
from txt2sql.db import execute_query
from txt2sql.planner.executor_adapter import ExecutionPlanBundle
from txt2sql.planner.physical import reject_partial_execution
from txt2sql.query_ir.adapters import query_ir_to_semantic_plan
from txt2sql.query_ir.models import PredicateIR, QueryIR, TemporalIR
from txt2sql.semantic_plan.compiler import compile_semantic_plan
from txt2sql.semantic_plan.models import OrderSpec, SemanticQueryPlan


def refine_query_ir_for_compile(ir: QueryIR, *, question: str | None = None) -> QueryIR:
    """Fix common IR slot issues before compile (operator-level, not Q-ID)."""
    data = ir.model_copy(deep=True)
    # Prefer aggregatable numeric measure as AVG/SUM/... field when multiple metrics exist.
    numericish = {
        "height_m",
        "gross_floor_area_m2",
        "building_area_m2",
        "site_area_m2",
        "ground_floors",
        "basement_floors",
        "building_coverage_ratio",
        "floor_area_ratio",
        "building.gross_floor_area",
        "building.height",
        "building.building_coverage_ratio",
        "building.floor_area_ratio",
        "building.ground_floors",
        "building.basement_floors",
    }
    concept_to_field = {
        "building.gross_floor_area": "gross_floor_area_m2",
        "building.height": "height_m",
        "building.building_coverage_ratio": "building_coverage_ratio",
        "building.floor_area_ratio": "floor_area_ratio",
        "building.ground_floors": "ground_floors",
        "building.basement_floors": "basement_floors",
        "building.usage": "usage",
        "building.detail_usage": "detail_usage",
        "building.approval_date": "approval_date",
        "building.permit_date": "permit_date",
    }
    measure_fields: list[str] = []
    for m in data.measures:
        f = concept_to_field.get(m.concept, m.concept)
        measure_fields.append(f)

    categorical = {"usage", "structure", "detail_usage", "violation_status", "special_land"}
    for agg in data.aggregations:
        if agg.function in {"avg", "sum", "min", "max", "median", "stddev", "percentile"}:
            field = agg.field
            if field in categorical or field is None or field not in numericish:
                pick = next((f for f in measure_fields if f in numericish), None)
                if pick:
                    agg.field = pick
            for f in measure_fields:
                if f in categorical and not any(p.field == f for p in data.predicates):
                    for m in data.measures:
                        mapped = concept_to_field.get(m.concept, m.concept)
                        if mapped == f and m.provenance and m.provenance.text:
                            text = m.provenance.text
                            if text not in {"용도", "구조", "높이", "연면적", "건폐율", "용적률"}:
                                data.predicates.append(
                                    PredicateIR(field=f, operator="eq", value=text)
                                )
                            break
    for m in data.measures:
        if m.concept in concept_to_field:
            m.concept = concept_to_field[m.concept]

    # Enrich temporal from NL when contract only flagged wants_temporal.
    if question and (data.temporal is not None or _looks_temporal(question)):
        from txt2sql.query_understanding.temporal import parse_temporal_filters

        tfilters = parse_temporal_filters(question)
        if tfilters and data.temporal is None:
            data.temporal = TemporalIR()
        for tf in tfilters:
            if any(
                p.field == tf.field and p.operator == tf.operator and p.value == tf.value
                for p in data.predicates
            ):
                continue
            data.predicates.append(
                PredicateIR(
                    field=tf.field,
                    operator=tf.operator,
                    value=tf.value,
                    value2=tf.value2,
                    unit=tf.unit,
                )
            )
            if data.temporal is not None and data.temporal.field is None:
                data.temporal.field = tf.field
                data.temporal.operator = tf.operator
                data.temporal.value = tf.value
                data.temporal.value2 = tf.value2

    # Grain: prefer building-level D010 concepts; avoid forcing D198 unless permit/approval needed.
    if data.temporal and data.temporal.field in {None, "approval_date", "permit_date"}:
        pass  # catalog binder decides D198 when date fields bind
    return data


def _looks_temporal(question: str) -> bool:
    q = question or ""
    needles = ("년", "년대", "경과", "사용승인", "허가일", "건축년", "지어진")
    return any(n in q for n in needles)


def build_sqp(ir: QueryIR, *, question: str | None = None) -> SemanticQueryPlan:
    refined = refine_query_ir_for_compile(ir, question=question)
    plan = query_ir_to_semantic_plan(refined)
    # Ensure group dimensions present
    if refined.dimensions and not plan.group_by:
        plan.group_by = [d.field for d in refined.dimensions]
    # Stable secondary order for group/rank
    if plan.query_kind in {"distribution", "rank"} and plan.group_by:
        if not plan.order_by:
            plan.order_by = [
                OrderSpec(field="count", direction="desc"),
                OrderSpec(field=plan.group_by[0], direction="asc"),
            ]
        elif len(plan.order_by) == 1 and plan.group_by:
            key = plan.group_by[0]
            if all(o.field != key for o in plan.order_by):
                plan.order_by = list(plan.order_by) + [OrderSpec(field=key, direction="asc")]
    # Rank/list-top: unify Sort+Limit defaults
    if plan.query_kind == "rank":
        if not plan.order_by and plan.aggregations:
            alias = plan.aggregations[0].alias or plan.aggregations[0].field or "count"
            plan.order_by = [OrderSpec(field=alias, direction="desc")]
        if plan.limit is None:
            plan.limit = 10
        if not plan.select and refined.outputs:
            plan.select = list(refined.outputs)
    if plan.query_kind == "list" and plan.limit is None and refined.limit:
        plan.limit = refined.limit
    return plan


def compile_sql_from_bundle(
    bundle: ExecutionPlanBundle, *, question: str | None = None
) -> tuple[str, dict[str, Any]]:
    reject_partial_execution(bundle.physical)
    plan = build_sqp(bundle.query_ir, question=question)
    compiled = compile_semantic_plan(plan)
    sql = compiled.sql if hasattr(compiled, "sql") else str(compiled)
    meta = {
        "tables": getattr(compiled, "tables", []),
        "route": getattr(compiled, "route", "semantic_v2"),
        "semantic_plan": getattr(compiled, "semantic_plan", plan.model_dump()),
    }
    return sql, meta


def execution_trace(
    bundle: ExecutionPlanBundle,
    *,
    execution_source: str,
    compiler_source: str,
    fallback_source: str | None = None,
) -> dict[str, Any]:
    return {
        "query_ir_task": bundle.query_ir.task,
        "logical_status": bundle.logical.status,
        "physical_strategy": bundle.physical.strategy,
        "execution_source": execution_source,
        "compiler_source": compiler_source,
        "fallback_source": fallback_source,
        "reason_codes": list(bundle.logical.reason_codes),
    }


def should_try_semantic_v2(bundle: ExecutionPlanBundle) -> bool:
    if bundle.logical.status != "READY":
        return False
    if bundle.physical.partial:
        return False
    # Keep Fast Path simple count/list on legacy router.
    if bundle.physical.strategy in {"FAST_SIMPLE_COUNT", "FAST_THRESHOLD"}:
        return False
    ir = bundle.query_ir
    # Unstable / high-regression operators stay on legacy/SQP until compilers mature.
    if ir.task in {"meta", "list", "rank", "compare", "unknown"}:
        return False
    # SpatialFilter→PostGIS still available via SQP/legacy; v2 ownership gated carefully.
    if ir.spatial:
        return False

    hints = ir.provenance.legacy_hints or {}
    source = ir.provenance.source_text or ""

    if ir.task == "aggregate":
        # Bare "면적 평균" is often clarify/meta — do not force AVG(gross_floor_area).
        if "면적" in source and not any(
            tok in source for tok in ("연면적", "건축면적", "대지면적", "부지면적")
        ):
            return False
        return bool(ir.aggregations)
    if ir.task in {"group", "distribution"}:
        return bool(ir.dimensions)
    if ir.task == "ratio":
        return True
    if ir.task == "count":
        # Avoid list-shaped questions mis-tagged as count (e.g. "보여줘").
        if not hints.get("wants_count"):
            return False
        if ir.temporal is not None:
            return True
        # Multi-predicate attribute counts (e.g. coverage + FAR thresholds).
        if len(ir.predicates) >= 2:
            return True
        return False
    return False


def try_execute_semantic_v2(
    question: str,
    bundle: ExecutionPlanBundle,
    *,
    conn: psycopg.Connection,
    default_limit: int = 100,
) -> dict[str, Any] | None:
    """Compile+execute via semantic-v2. Return None to fall back to legacy."""
    if not should_try_semantic_v2(bundle):
        return None
    try:
        sql, meta = compile_sql_from_bundle(bundle, question=question)
        validate_compiled_sql(sql, question=question, conn=None)
        rows = execute_query(conn, sql, default_limit=default_limit)
    except Exception:
        return None
    return {
        "ok": True,
        "sql": sql,
        "rows": rows,
        "row_count": len(rows),
        "tables": meta.get("tables"),
        "route": "semantic_v2",
        "answer": None,
        **execution_trace(
            bundle,
            execution_source="semantic_v2",
            compiler_source="deterministic_compiler_v2",
            fallback_source=None,
        ),
    }
