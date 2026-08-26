"""Follow-up via QueryIR deltas (preferred over rewriting SQL strings)."""

from __future__ import annotations

import re

from txt2sql.interaction.delta import QueryIRDelta, apply_delta, classify_interaction_intent
from txt2sql.query_ir.models import QueryIR


_LIMIT_RE = re.compile(r"상위\s*(\d+)|(\d+)\s*개만")


def followup_to_delta(question: str, previous: QueryIR) -> QueryIR | None:
    intent = classify_interaction_intent(question, has_session=True)
    if intent != "refine_query":
        return None
    ir = previous
    m = _LIMIT_RE.search(question)
    if m:
        limit = int(m.group(1) or m.group(2))
        ir = apply_delta(ir, QueryIRDelta(op="change_limit", payload={"limit": limit}))
    if any(k in question for k in ("지도", "맵")):
        ir = apply_delta(ir, QueryIRDelta(op="set_presentation", payload={"presentation": "map"}))
    if any(k in question for k in ("차트", "그래프")):
        ir = apply_delta(ir, QueryIRDelta(op="set_presentation", payload={"presentation": "chart"}))
    return ir
