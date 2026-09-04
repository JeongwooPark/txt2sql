"""ExecutionTrace — unified observability across all execution paths.

Phase 2: every path (semantic_v2, legacy_router, semantic_plan, rag_sql)
must emit a comparable trace before FAIL180 taxonomy can diagnose by stage.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ExecutionSource = Literal[
    "semantic_v2",
    "legacy_router",
    "semantic_plan",
    "rag_sql",
    "ir_fast_path",
    "untracked",
    "unknown",
]

TRACE_FIELDS = (
    "query_understanding",
    "query_ir",
    "scope_binding",
    "dataset_binding",
    "field_binding",
    "logical_plan",
    "generated_sql",
)


class ExecutionResultTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_count: int = 0
    result_shape: str | None = None
    tables: list[str] = Field(default_factory=list)


class EvaluationTrace(BaseModel):
    model_config = ConfigDict(extra="allow")

    expected: Any | None = None
    actual: Any | None = None
    match: bool | None = None
    reason: str | None = None
    error_stage: str | None = None


class TraceCompleteness(BaseModel):
    """Which trace slots were populated for this execution path."""

    model_config = ConfigDict(extra="forbid")

    query_understanding: bool = False
    query_ir: bool = False
    scope_binding: bool = False
    dataset_binding: bool = False
    field_binding: bool = False
    logical_plan: bool = False
    generated_sql: bool = False
    complete: bool = False


class ExecutionTrace(BaseModel):
    model_config = ConfigDict(extra="allow")

    question_id: str | None = None
    execution_source: str = "unknown"
    compiler_source: str | None = None
    fallback_source: str | None = None

    normalized_question: str = ""

    query_understanding: dict[str, Any] = Field(default_factory=dict)
    query_ir: dict[str, Any] | None = None
    scope_binding: dict[str, Any] | None = None
    dataset_binding: dict[str, Any] | None = None
    field_binding: dict[str, Any] | None = None
    logical_plan: dict[str, Any] | None = None
    semantic_plan: dict[str, Any] | None = None

    generated_sql: str | None = None
    expected_sql: str | None = None

    execution: ExecutionResultTrace = Field(default_factory=ExecutionResultTrace)
    evaluation: EvaluationTrace | None = None

    trace_completeness: TraceCompleteness = Field(default_factory=TraceCompleteness)
    completeness_report: dict[str, Any] | None = None


def _infer_execution_source(payload: dict[str, Any]) -> str:
    for key in ("execution_source",):
        val = payload.get(key)
        if val:
            return str(val)
    route = str(payload.get("route") or "")
    if route == "semantic_v2":
        return "semantic_v2"
    if route.startswith("semantic_plan"):
        return "semantic_plan"
    if route and route not in {"None", "null"}:
        return "legacy_router"
    if payload.get("sql"):
        return "rag_sql"
    return "untracked"


def _build_scope_binding(query_ir: dict[str, Any] | None) -> dict[str, Any] | None:
    if not query_ir:
        return None
    scope = query_ir.get("scope")
    if not scope:
        return None
    place = scope.get("place") if isinstance(scope, dict) else getattr(scope, "place", None)
    if not place:
        return None
    try:
        from txt2sql.semantic_catalog.place_scope import PlaceScopeContext, resolve_place_scope

        ctx = PlaceScopeContext(question=query_ir.get("provenance", {}).get("source_text", ""))
        if scope.get("place_kind") == "admin_dong" if isinstance(scope, dict) else False:
            ctx.prefer_admin = True
        binding = resolve_place_scope(place, context=ctx)
        return binding.model_dump()
    except Exception:
        return {"place": place, "place_kind": scope.get("place_kind") if isinstance(scope, dict) else None}


def _build_dataset_binding(plan_bundle: Any | None, payload: dict[str, Any]) -> dict[str, Any] | None:
    snap = payload.get("binding_snapshot")
    if isinstance(snap, dict) and snap:
        return snap
    if plan_bundle is None:
        return None
    logical = getattr(plan_bundle, "logical", None)
    if logical is None:
        return None
    bindings = getattr(logical, "bindings", None) or []
    if not bindings:
        return None
    return {
        "datasets": [getattr(b, "dataset", None) for b in bindings],
        "concepts": [getattr(b, "concept", None) for b in bindings],
        "physical_fields": [getattr(b, "physical_field", None) for b in bindings],
    }


def _build_field_binding(plan_bundle: Any | None, query_ir: dict[str, Any] | None) -> dict[str, Any] | None:
    if query_ir is None:
        return None
    fields: list[str] = []
    for pred in query_ir.get("predicates") or []:
        if isinstance(pred, dict) and pred.get("field"):
            fields.append(str(pred["field"]))
    for agg in query_ir.get("aggregations") or []:
        if isinstance(agg, dict) and agg.get("field"):
            fields.append(str(agg["field"]))
    for dim in query_ir.get("dimensions") or []:
        if isinstance(dim, dict) and dim.get("field"):
            fields.append(str(dim["field"]))
    ds = _build_dataset_binding(plan_bundle, {})
    if not fields and not ds:
        return None
    return {"fields": sorted(set(fields)), "dataset_binding": ds}


def _build_logical_plan(plan_bundle: Any | None, payload: dict[str, Any]) -> dict[str, Any] | None:
    snap = payload.get("logical_plan_snapshot")
    if isinstance(snap, dict) and snap:
        return snap
    if plan_bundle is None:
        return None
    logical = getattr(plan_bundle, "logical", None)
    if logical is None:
        return None
    return {
        "status": getattr(logical, "status", None),
        "reason_codes": list(getattr(logical, "reason_codes", []) or []),
        "root_op": getattr(getattr(logical, "root", None), "op", None),
    }


def _result_shape(payload: dict[str, Any]) -> str | None:
    task = payload.get("query_ir_task")
    if task:
        return str(task)
    rows = payload.get("rows") or []
    if len(rows) <= 1:
        return "scalar"
    return "table"


def _extract_completeness_report(plan_bundle: Any | None, payload: dict[str, Any]) -> dict[str, Any] | None:
    if plan_bundle is not None:
        logical = getattr(plan_bundle, "logical", None)
        if logical is not None:
            comp = getattr(logical, "completeness", None)
            if comp is not None:
                return comp.as_dict() if hasattr(comp, "as_dict") else dict(comp)
    raw = payload.get("completeness_report")
    return raw if isinstance(raw, dict) else None


def build_execution_trace(
    payload: dict[str, Any],
    *,
    question: str,
    question_id: str | None = None,
    contract: Any | None = None,
    plan_bundle: Any | None = None,
    expected_sql: str | None = None,
    gold: Any | None = None,
    eval_match: bool | None = None,
    eval_reason: str | None = None,
) -> ExecutionTrace:
    """Build unified execution trace from pipeline payload + plan context."""
    source = _infer_execution_source(payload)

    # Query understanding (contract)
    qu: dict[str, Any] = {}
    if contract is not None:
        try:
            qu = contract.model_dump()
        except Exception:
            qu = dict(contract) if isinstance(contract, dict) else {}

    # QueryIR
    query_ir: dict[str, Any] | None = None
    if payload.get("query_ir_snapshot"):
        query_ir = dict(payload["query_ir_snapshot"])
    elif plan_bundle is not None:
        ir = getattr(plan_bundle, "query_ir", None)
        if ir is not None:
            try:
                query_ir = ir.model_dump()
            except Exception:
                query_ir = dict(ir) if isinstance(ir, dict) else None

    scope_binding = _build_scope_binding(query_ir)
    dataset_binding = _build_dataset_binding(plan_bundle, payload)
    field_binding = _build_field_binding(plan_bundle, query_ir)
    logical_plan = _build_logical_plan(plan_bundle, payload)

    semantic_plan = payload.get("semantic_plan")
    if isinstance(semantic_plan, dict):
        sp = semantic_plan
    else:
        sp = None

    sql = payload.get("sql") or payload.get("compiled_sql")
    rows = list(payload.get("rows") or [])

    completeness = TraceCompleteness(
        query_understanding=bool(qu),
        query_ir=query_ir is not None,
        scope_binding=scope_binding is not None,
        dataset_binding=dataset_binding is not None,
        field_binding=field_binding is not None,
        logical_plan=logical_plan is not None,
        generated_sql=bool(sql),
    )
    completeness.complete = all(
        getattr(completeness, f) for f in TRACE_FIELDS if f != "field_binding"
    ) or source in {"legacy_router", "rag_sql"}

    error_stage = _infer_error_stage(payload, completeness, eval_match)

    evaluation = None
    if gold is not None or eval_match is not None:
        evaluation = EvaluationTrace(
            expected=gold,
            actual=payload.get("answer"),
            match=eval_match,
            reason=eval_reason,
            error_stage=error_stage,
        )

    return ExecutionTrace(
        question_id=question_id,
        execution_source=source,
        compiler_source=payload.get("compiler_source"),
        fallback_source=payload.get("fallback_source"),
        normalized_question=question,
        query_understanding=qu,
        query_ir=query_ir,
        scope_binding=scope_binding,
        dataset_binding=dataset_binding,
        field_binding=field_binding,
        logical_plan=logical_plan,
        semantic_plan=sp,
        generated_sql=sql,
        expected_sql=expected_sql,
        execution=ExecutionResultTrace(
            row_count=len(rows),
            result_shape=_result_shape(payload),
            tables=list(payload.get("tables") or []),
        ),
        evaluation=evaluation,
        trace_completeness=completeness,
        completeness_report=_extract_completeness_report(plan_bundle, payload),
    )


def _infer_error_stage(
    payload: dict[str, Any],
    completeness: TraceCompleteness,
    eval_match: bool | None,
) -> str | None:
    if eval_match is True:
        return None
    if payload.get("error") or not payload.get("ok", True):
        if not completeness.generated_sql:
            return "compilation"
        return "execution"
    if eval_match is False:
        if not completeness.query_ir:
            return "understanding"
        if not completeness.logical_plan:
            return "binding"
        return "evaluator"
    return None


def attach_execution_trace(
    payload: dict[str, Any],
    *,
    question: str,
    question_id: str | None = None,
    contract: Any | None = None,
    plan_bundle: Any | None = None,
    **eval_kwargs: Any,
) -> dict[str, Any]:
    """Attach execution_trace to pipeline result dict."""
    trace = build_execution_trace(
        payload,
        question=question,
        question_id=question_id,
        contract=contract,
        plan_bundle=plan_bundle,
        **eval_kwargs,
    )
    out = dict(payload)
    out["execution_trace"] = trace.model_dump()
    return out


def diagnose_from_trace(trace: dict[str, Any] | ExecutionTrace) -> tuple[str, str, float]:
    """Stage-based diagnosis from execution trace (Phase 5 prerequisite)."""
    if isinstance(trace, ExecutionTrace):
        data = trace.model_dump()
    else:
        data = trace

    completeness = data.get("trace_completeness") or {}
    evaluation = data.get("evaluation") or {}
    error_stage = evaluation.get("error_stage") or ""

    if error_stage == "understanding":
        return "BINDING", "IR_MISSING", 0.9
    if error_stage == "binding":
        return "BINDING", "DATASET_BINDING", 0.85
    if error_stage == "compilation":
        return "COMPILER", "SQL_GENERATION", 0.85
    if error_stage == "execution":
        return "EXECUTION", "SQL_EXECUTION", 0.9
    if error_stage == "evaluator":
        return "EVALUATOR", "RESULT_MISMATCH", 0.8

    if not completeness.get("query_ir"):
        return "BINDING", "IR_MISSING", 0.75
    if not completeness.get("logical_plan"):
        return "BINDING", "PLAN_MISSING", 0.7
    if not completeness.get("generated_sql"):
        return "COMPILER", "SQL_MISSING", 0.75

    source = data.get("execution_source", "unknown")
    if source == "rag_sql":
        return "BINDING", "RAG_FALLBACK", 0.65

    return "UNKNOWN", "", 0.3
