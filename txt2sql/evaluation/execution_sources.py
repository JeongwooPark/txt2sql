"""Aggregate execution_source / compiler_source shares from gold result JSON."""

from __future__ import annotations

from collections import Counter
from typing import Any

from txt2sql.evaluation.case_map import case_rows


def _infer_source(case: dict[str, Any]) -> str:
    for key in ("execution_source",):
        val = case.get(key)
        if val:
            return str(val)
    # Prefer progress/detail emitted during ask
    for step in case.get("process") or []:
        if not isinstance(step, dict):
            continue
        detail = step.get("detail") or {}
        if isinstance(detail, dict) and detail.get("execution_source"):
            return str(detail["execution_source"])
        msg = str(step.get("message") or "")
        if "semantic-v2 적중" in msg or "execution_source=semantic_v2" in msg:
            return "semantic_v2"
        if "Semantic Plan" in msg or "semantic_plan" in msg.lower():
            return "semantic_plan"
        if "RAG" in msg:
            return "rag_sql"
    route = str(case.get("route") or "")
    if route == "semantic_v2":
        return "semantic_v2"
    if route.startswith("semantic_plan"):
        return "semantic_plan"
    if route in {"", "None", "null"} and case.get("sql"):
        return "rag_sql"
    if route:
        return "legacy_router"
    return "untracked"


def share_execution_sources(payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    rows = case_rows(payload) if isinstance(payload, dict) else list(payload)
    counts: Counter[str] = Counter()
    compiler: Counter[str] = Counter()
    fallback: Counter[str] = Counter()
    for case in rows:
        src = _infer_source(case)
        counts[src] += 1
        cs = case.get("compiler_source")
        if cs:
            compiler[str(cs)] += 1
        fb = case.get("fallback_source")
        if fb:
            fallback[str(fb)] += 1
    total = sum(counts.values()) or 1
    return {
        "total": total,
        "counts": dict(counts),
        "share_pct": {k: round(100.0 * v / total, 2) for k, v in counts.items()},
        "compiler_counts": dict(compiler),
        "fallback_counts": dict(fallback),
        "untracked": counts.get("untracked", 0),
    }
