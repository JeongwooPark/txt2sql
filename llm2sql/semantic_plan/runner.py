"""generate → normalize → validate → compile → SQL validate → execute."""

from __future__ import annotations

from typing import Any

import psycopg

from llm2sql.config import Settings
from llm2sql.db import assert_readonly_sql, execute_query
from llm2sql.progress import ProgressTracker
from llm2sql.semantic_plan.answer import format_semantic_answer, format_semantic_clarify
from llm2sql.semantic_plan.compiler import compile_semantic_plan
from llm2sql.semantic_plan.generator import generate_semantic_plan
from llm2sql.semantic_plan.models import (
    SemanticCompileError,
    SemanticPlanGenerationError,
    SemanticQueryPlan,
)
from llm2sql.semantic_plan.plan_sql_verifier import verify_plan_to_sql
from llm2sql.semantic_plan.normalizer import normalize_semantic_plan
from llm2sql.semantic_plan.validator import validate_semantic_plan
from llm2sql.session import SessionContext
from llm2sql.sql_validator import validate_sql_preexec


def run_semantic_plan(
    question: str,
    settings: Settings,
    *,
    conn: psycopg.Connection,
    ollama_client: Any | None = None,
    session: SessionContext | None = None,
    progress: ProgressTracker | None = None,
    execute: bool = True,
    allow_llm: bool = True,
    plan: SemanticQueryPlan | None = None,
    contract=None,
) -> dict[str, Any]:
    def emit(stage: str, message: str, **extra: Any) -> None:
        if progress is not None:
            progress.emit(stage, message, **extra)

    try:
        generated = plan or generate_semantic_plan(
            question,
            settings,
            conn=conn,
            ollama_client=ollama_client,
            session=session,
            allow_llm=allow_llm,
            contract=contract,
        )
    except SemanticPlanGenerationError as exc:
        emit("plan_fallback", f"Plan 생성 실패: {exc}")
        return _fallback("generation_failed", str(exc))

    emit(
        "plan",
        "Semantic Query Plan 생성 완료",
        query_kind=generated.query_kind,
        entity=generated.entity,
        plan_version=generated.version,
    )
    normalized = normalize_semantic_plan(generated, question, conn=conn)
    checked = validate_semantic_plan(
        normalized, question, conn=conn, contract=contract
    )
    emit(
        "plan_validate",
        f"Plan 검증 완료 status={checked.status} score={checked.score:.2f}",
        plan_version=checked.plan.version,
        slot_confidence=(
            checked.plan.slot_confidence.overall
            if checked.plan.slot_confidence
            else None
        ),
        verification_errors=list(checked.errors),
    )

    if checked.status == "clarify":
        answer = format_semantic_clarify(checked.plan)
        return {
            "ok": True,
            "needs_clarification": True,
            "route": "semantic_plan_clarify",
            "answer": answer,
            "sql": None,
            "tables": [],
            "rows": [],
            "row_count": 0,
            "semantic_plan": checked.plan.model_dump(),
            "plan_quality": checked.score,
            "fallback": False,
            "fallback_reason": None,
        }

    if checked.status != "ready":
        reason = checked.errors[0] if checked.errors else "validation_failed"
        emit("plan_fallback", f"Plan 검증 fallback: {reason}")
        return _fallback(reason, semantic_plan=checked.plan, quality=checked.score)

    if checked.score < settings.semantic_plan_min_quality:
        emit("plan_fallback", f"Plan 품질 부족 score={checked.score:.2f}")
        return _fallback(
            "low_quality",
            semantic_plan=checked.plan,
            quality=checked.score,
        )

    try:
        compiled = compile_semantic_plan(checked.plan)
    except SemanticCompileError as exc:
        emit("plan_fallback", f"SQL 컴파일 실패: {exc}")
        return _fallback("compile_failed", str(exc), semantic_plan=checked.plan)

    emit("plan_compile", "Semantic Plan → SQL 컴파일 완료", sql=compiled.sql)
    from llm2sql.semantic_plan.sql_equivalence import verify_plan_sql_equivalence
    from llm2sql.semantic_plan.plan_sql_verifier import verify_plan_to_sql

    drop_errors = verify_plan_to_sql(checked.plan, compiled)
    if drop_errors:
        emit("plan_fallback", f"Plan-SQL 노드 누락: {drop_errors}")
        return _fallback(
            "sql_semantic_mismatch",
            ",".join(drop_errors),
            semantic_plan=checked.plan,
            sql=compiled.sql,
        )
    eq_errors = verify_plan_sql_equivalence(checked.plan, compiled.sql)
    if eq_errors:
        emit("plan_fallback", f"Plan-SQL 의미 불일치: {eq_errors}")
        return _fallback(
            "sql_semantic_mismatch",
            ",".join(eq_errors),
            semantic_plan=checked.plan,
            sql=compiled.sql,
        )
    try:
        assert_readonly_sql(compiled.sql)
    except ValueError as exc:
        return _fallback("readonly_failed", str(exc), semantic_plan=checked.plan)

    pre_diag = validate_sql_preexec(
        question,
        compiled.sql,
        conn=conn if settings.use_explain and execute else None,
        default_limit=settings.default_limit,
        use_explain=settings.use_explain and execute,
    )
    if pre_diag:
        emit("plan_fallback", "SQL 사전검증 실패")
        return _fallback(
            "sql_validation_failed",
            pre_diag,
            semantic_plan=checked.plan,
            sql=compiled.sql,
        )

    if not execute:
        return {
            "ok": True,
            "fallback": False,
            "route": compiled.route,
            "sql": compiled.sql,
            "tables": compiled.tables,
            "rows": [],
            "row_count": 0,
            "semantic_plan": compiled.semantic_plan,
            "plan_quality": checked.score,
            "fallback_reason": None,
            "shadow": True,
        }

    try:
        rows = execute_query(
            conn,
            compiled.sql,
            default_limit=settings.default_limit,
            statement_timeout_ms=settings.db_statement_timeout_ms,
        )
    except Exception as exc:
        emit("plan_fallback", f"실행 실패: {type(exc).__name__}")
        return _fallback(
            "execute_failed",
            f"{type(exc).__name__}: {exc}",
            semantic_plan=checked.plan,
            sql=compiled.sql,
        )

    from llm2sql.semantic_plan.result_shape import diagnose_result_shape

    shape_errors = diagnose_result_shape(checked.plan, list(rows or []))
    if shape_errors and rows:
        emit("plan_validate", f"result shape warnings {shape_errors}")

    warnings = checked.warnings
    blocking = [
        item
        for item in warnings
        if item not in {"heuristic_plan", "plan_followup_delta", "plan_followup_event"}
    ]
    if not rows and blocking:
        return _fallback(
            "empty_with_warning",
            "; ".join(blocking),
            semantic_plan=checked.plan,
            sql=compiled.sql,
        )

    answer = format_semantic_answer(
        question, plan=checked.plan, rows=rows, row_count=len(rows)
    )
    return {
        "ok": True,
        "fallback": False,
        "route": compiled.route,
        "sql": compiled.sql,
        "tables": compiled.tables,
        "rows": rows,
        "row_count": len(rows),
        "answer": answer,
        "semantic_plan": compiled.semantic_plan,
        "plan_quality": checked.score,
        "fallback_reason": None,
    }


def _fallback(
    reason: str,
    detail: str | None = None,
    *,
    semantic_plan: SemanticQueryPlan | None = None,
    quality: float | None = None,
    sql: str | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "fallback": True,
        "route": "semantic_plan_fallback",
        "fallback_reason": reason,
        "error": detail,
        "sql": sql,
        "tables": [],
        "rows": [],
        "row_count": 0,
        "semantic_plan": semantic_plan.model_dump() if semantic_plan is not None else None,
        "plan_quality": quality,
    }
