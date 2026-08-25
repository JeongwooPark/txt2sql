"""generate → normalize → validate → compile → SQL validate → execute."""

from __future__ import annotations

from typing import Any

import psycopg

from txt2sql.config import Settings
from txt2sql.db import assert_readonly_sql, execute_query
from txt2sql.progress import ProgressTracker
from txt2sql.semantic_plan.answer import format_semantic_answer, format_semantic_clarify
from txt2sql.semantic_plan.compiler import compile_semantic_plan
from txt2sql.semantic_plan.generator import generate_semantic_plan
from txt2sql.semantic_plan.models import (
    SemanticCompileError,
    SemanticPlanGenerationError,
    SemanticQueryPlan,
)
from txt2sql.semantic_plan.normalizer import normalize_semantic_plan
from txt2sql.semantic_plan.plan_sql_verifier import verify_plan_to_sql
from txt2sql.semantic_plan.result_shape import diagnose_result_shape, verify_result
from txt2sql.semantic_plan.sql_equivalence import verify_plan_sql_equivalence
from txt2sql.semantic_plan.validator import validate_semantic_plan
from txt2sql.session import SessionContext
from txt2sql.sql_validator import validate_sql_preexec


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
    force_llm: bool = False,
) -> dict[str, Any]:
    """Plan 생성 → 검증 → SQL → 실행. force_llm은 shape 실패 후 1회 재계획."""
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
            force_llm=force_llm,
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
    for label, errors in (
        ("Plan-SQL 노드 누락", verify_plan_to_sql(checked.plan, compiled)),
        ("Plan-SQL 의미 불일치", verify_plan_sql_equivalence(checked.plan, compiled.sql)),
    ):
        if errors:
            emit("plan_fallback", f"{label}: {errors}")
            return _fallback(
                "sql_semantic_mismatch",
                ",".join(errors),
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
        return _sqp_ok(
            route=compiled.route,
            sql=compiled.sql,
            tables=compiled.tables,
            semantic_plan=compiled.semantic_plan,
            plan_quality=checked.score,
            shadow=True,
        )

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

    # 계약 kind가 count로 남아도 Plan shape이 맞으면 결과를 유지한다(other 적재 방지).
    # Plan shape도 틀린 진짜 불일치만 LLM 재계획으로 넘긴다.
    rows = list(rows or [])
    shape_errors = diagnose_result_shape(checked.plan, rows)
    if shape_errors and rows:
        emit("plan_validate", f"result shape warnings {shape_errors}")
    verified = verify_result(contract, rows, plan=checked.plan)
    if not verified.ok and shape_errors:
        emit("plan_validate", f"result shape fail {verified.reasons}")
        return _sqp_ok(
            ok=False,
            route=compiled.route,
            sql=compiled.sql,
            tables=compiled.tables,
            rows=rows,
            semantic_plan=compiled.semantic_plan,
            plan_quality=checked.score,
            shape_failed=True,
            fallback=True,
            fallback_reason="shape_mismatch",
            error=",".join(verified.reasons),
        )
    if not verified.ok:
        emit(
            "plan_validate",
            "contract kind mismatch but executed plan shape ok — keep result "
            f"{verified.reasons}",
        )

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

    return _sqp_ok(
        route=compiled.route,
        sql=compiled.sql,
        tables=compiled.tables,
        rows=rows,
        semantic_plan=compiled.semantic_plan,
        plan_quality=checked.score,
        answer=format_semantic_answer(
            question, plan=checked.plan, rows=rows, row_count=len(rows)
        ),
    )


def _sqp_ok(
    *,
    route: str,
    sql: str | None = None,
    tables: list[str] | None = None,
    rows: list | None = None,
    semantic_plan: Any = None,
    plan_quality: float | None = None,
    ok: bool = True,
    **extra: Any,
) -> dict[str, Any]:
    rows = list(rows or [])
    out: dict[str, Any] = {
        "ok": ok,
        "fallback": False,
        "fallback_reason": None,
        "route": route,
        "sql": sql,
        "tables": list(tables or []),
        "rows": rows,
        "row_count": len(rows),
        "semantic_plan": semantic_plan,
        "plan_quality": plan_quality,
    }
    out.update(extra)
    return out


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
