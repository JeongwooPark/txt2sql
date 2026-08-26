"""Visualization presentation helpers (do not alter QueryIR meaning)."""

from __future__ import annotations

from txt2sql.interaction.delta import QueryIRDelta, apply_delta, classify_interaction_intent
from txt2sql.query_ir.models import QueryIR


def maybe_set_visualization(question: str, ir: QueryIR) -> QueryIR:
    intent = classify_interaction_intent(question)
    if intent != "visualize":
        return ir
    presentation = "chart" if any(k in question for k in ("차트", "그래프")) else "map"
    return apply_delta(ir, QueryIRDelta(op="set_presentation", payload={"presentation": presentation}))
