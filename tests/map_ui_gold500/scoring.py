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
) -> dict[str, Any]:
    from txt2sql.evaluation.taxonomy import diagnose_eval_failure

    pred_rows = list(rows or [])
    ok, reason = False, error or "no-result"
    if timed_out:
        reason = error or "timeout"
    elif error and not answer:
        reason = error
    else:
        ok, reason = score(case.get("kind") or "fallback", case.get("gold") or "", answer, pred_rows)
        if error and not ok:
            reason = f"engine-fail:{error}"
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
        "error": error,
        "ms": ms,
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
    return rec
