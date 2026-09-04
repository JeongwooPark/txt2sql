"""맵 UI 답변을 골드 수치 기준으로 채점한다."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _load_gold_eval():
    spec = importlib.util.spec_from_file_location(
        "eval_q500_gold", ROOT / "scripts" / "eval_q500_gold.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError("scripts/eval_q500_gold.py 를 불러올 수 없습니다")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_GOLD = _load_gold_eval()
score = _GOLD.score
summarize = _GOLD.summarize
clip = _GOLD._clip


def _infer_llm_from_process(process: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    calls: list[str] = []
    for step in process or []:
        if not isinstance(step, dict):
            continue
        stage = str(step.get("stage") or "")
        msg = str(step.get("message") or "")
        if stage == "llm" or "LLM 호출:" in msg:
            purpose = msg.split("LLM 호출:", 1)[-1].strip() or "chat"
            calls.append(purpose)
            continue
        if "RAG+LLM" in msg:
            calls.append("rag_sql")
        elif "의도 분류" in msg and "(llm)" in msg:
            calls.append("intent_classify")
        elif "의도=" in msg and "(llm)" in msg:
            calls.append("intent_classify")
        elif "미지용어 대응 (llm)" in msg:
            calls.append("synonym_map")
    return bool(calls), calls


def score_case(
    case: dict[str, Any],
    *,
    answer: str,
    rows: list[dict[str, Any]] | None,
    sql: str | None,
    route: str | None,
    error: str | None,
    timed_out: bool,
    ms: int,
    ui: dict[str, Any],
    process: list[dict[str, Any]],
    execution_source: str | None = None,
    compiler_source: str | None = None,
    fallback_source: str | None = None,
    query_ir_task: str | None = None,
    logical_status: str | None = None,
    physical_strategy: str | None = None,
    execution_trace: dict[str, Any] | None = None,
    llm_used: bool | None = None,
    llm_calls: list[str] | None = None,
    stage_latency_ms: dict[str, int] | None = None,
) -> dict[str, Any]:
    from txt2sql.evaluation.taxonomy import diagnose_eval_failure

    pred_rows = list(rows or [])
    ok, reason = False, error or "no-result"
    if timed_out:
        reason = error or "timeout"
    elif error and not answer:
        reason = error
    else:
        ok, reason = score(
            case.get("kind") or "fallback",
            case.get("gold") or "",
            answer,
            pred_rows,
            question=case.get("q") or "",
            sql=sql,
        )
        if error and not ok:
            reason = f"engine-fail:{error}"
    resolved_llm_used = bool(llm_used) if llm_used is not None else False
    resolved_llm_calls = list(llm_calls or [])
    if not resolved_llm_calls and llm_used is None:
        resolved_llm_used, resolved_llm_calls = _infer_llm_from_process(process)
    rec = {
        "id": case["id"],
        "cat": case.get("cat"),
        "kind": case.get("kind"),
        "source": case.get("source"),
        "session": case.get("session"),
        "parent": case.get("parent"),
        "q": case["q"],
        "gold": case.get("gold"),
        "pass": ok,
        "reason": reason,
        "route": route,
        "execution_source": execution_source,
        "compiler_source": compiler_source,
        "fallback_source": fallback_source,
        "query_ir_task": query_ir_task,
        "logical_status": logical_status,
        "physical_strategy": physical_strategy,
        "error": error,
        "ms": ms,
        "latency_ms": ms,
        "llm_used": resolved_llm_used,
        "llm_calls": resolved_llm_calls,
        "llm_call_count": len(resolved_llm_calls),
        "stage_latency_ms": dict(stage_latency_ms or {}),
        "answer": clip(answer),
        "answer_full": answer,
        "sql": clip(str(sql or ""), 800 if not ok else 220),
        "sql_full": sql,
        "row_count": len(pred_rows),
        "rows": pred_rows[:20],
        "timed_out": timed_out,
        "root_causes": []
        if ok
        else diagnose_eval_failure(
            question=case["q"],
            sql=sql,
            answer=answer,
            reason=reason,
            timed_out=timed_out,
            route=route,
        ),
        "ui": ui,
        "process": process,
    }
    # Phase 2: preserve execution_trace from API if present
    if execution_trace:
        rec["execution_trace"] = execution_trace
    for step in process or []:
        if isinstance(step, dict):
            detail = step.get("detail") or {}
            if isinstance(detail, dict) and detail.get("execution_trace"):
                rec["execution_trace"] = detail["execution_trace"]
                break
    if ui.get("execution_trace"):
        rec["execution_trace"] = ui["execution_trace"]
    return rec
