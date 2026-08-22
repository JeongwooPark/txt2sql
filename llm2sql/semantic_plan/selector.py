"""Hard query에만 후보 2~3개를 만들고 결정적으로 고른다."""

from __future__ import annotations

from llm2sql.query_understanding.complexity import is_hard_query
from llm2sql.query_understanding.contract import extract_contract
from llm2sql.semantic_plan.compiler import compile_semantic_plan
from llm2sql.semantic_plan.models import SemanticQueryPlan
from llm2sql.semantic_plan.sql_equivalence import verify_plan_sql_equivalence


def should_enumerate_candidates(question: str) -> bool:
    contract = extract_contract(question)
    return is_hard_query(contract.complexity)


def select_candidate(plans: list[SemanticQueryPlan], question: str) -> SemanticQueryPlan:
    contract = extract_contract(question)
    wanted_agg = [span.value for span in contract.aggregations]
    scored: list[tuple[int, SemanticQueryPlan]] = []
    for plan in plans:
        compiled = compile_semantic_plan(plan)
        errors = verify_plan_sql_equivalence(plan, compiled.sql)
        score = 100 - 10 * len(errors)
        if plan.predicate is not None:
            score += 5
        if wanted_agg and plan.aggregations and plan.aggregations[0].function == wanted_agg[0]:
            score += 20
        scored.append((score, plan))
    scored.sort(key=lambda item: (-item[0], item[1].model_dump_json()))
    return scored[0][1]
