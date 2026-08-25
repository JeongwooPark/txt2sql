"""masked question + Plan signature example retrieval."""

from __future__ import annotations

import re
from dataclasses import dataclass

from txt2sql.example_store import EXAMPLE_BANK
from txt2sql.semantic_plan.models import SemanticQueryPlan


def plan_signature(plan: SemanticQueryPlan) -> str:
    fields = sorted({item.field for item in plan.filters})
    aggs = sorted(item.function for item in plan.aggregations)
    pred = plan.predicate.op if plan.predicate else "and"
    return f"{plan.query_kind}|{plan.entity}|{pred}|{','.join(fields)}|{','.join(aggs)}"


def mask_question(question: str) -> str:
    text = re.sub(r"\d+(?:\.\d+)?", "<NUM>", question)
    text = re.sub(r"[가-힣]+(?:구|군|동)", "<PLACE>", text)
    return text


@dataclass(frozen=True)
class ExampleHit:
    question: str
    sql: str
    score: float
    verified: bool


def retrieve_plan_examples(question: str, plan: SemanticQueryPlan | None, *, top_k: int = 3) -> list[ExampleHit]:
    masked = mask_question(question)
    sig = plan_signature(plan) if plan else ""
    hits: list[ExampleHit] = []
    for item in EXAMPLE_BANK:
        q = item.question
        sql = item.sql
        score = 0.0
        if mask_question(q) == masked:
            score += 0.5
        if sig and sig.split("|")[0] in q:
            score += 0.2
        if score:
            hits.append(ExampleHit(q, sql, score, verified=False))
    hits.sort(key=lambda item: item.score, reverse=True)
    return hits[:top_k]
