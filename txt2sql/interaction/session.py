"""Session helpers for interaction layer."""

from __future__ import annotations

from typing import Any

from txt2sql.query_ir.models import QueryIR


def previous_query_ir(session: dict[str, Any] | None) -> QueryIR | None:
    if not session:
        return None
    raw = session.get("query_ir") or session.get("last_query_ir")
    if isinstance(raw, QueryIR):
        return raw
    if isinstance(raw, dict):
        return QueryIR.model_validate(raw)
    return None


def store_query_ir(session: dict[str, Any], ir: QueryIR) -> dict[str, Any]:
    out = dict(session or {})
    out["query_ir"] = ir.model_dump()
    out["last_query_ir"] = out["query_ir"]
    return out
