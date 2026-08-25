from txt2sql.config import Settings
from txt2sql.semantic_plan.compiler import compile_semantic_plan
from txt2sql.semantic_plan.generator import generate_semantic_plan
from txt2sql.semantic_plan.models import SemanticQueryPlan


def test_default_mode_is_hybrid() -> None:
    settings = Settings(database_url="postgresql://x:x@localhost/x")
    assert settings.semantic_plan_mode == "hybrid"
    assert settings.semantic_plan_version == "1.1"
    assert settings.semantic_plan_min_contract_coverage == 1.0


def test_shadow_override_does_not_change_default() -> None:
    settings = Settings(
        database_url="postgresql://x:x@localhost/x",
        semantic_plan_mode="shadow",
    )
    assert settings.semantic_plan_mode == "shadow"


def test_complete_or_is_ready() -> None:
    settings = Settings(database_url="postgresql://x:x@localhost/x")
    plan = generate_semantic_plan(
        "연제구 공동주택 또는 단독주택 건물 수",
        settings,
        allow_llm=False,
    )
    assert plan.requires_clarification is False
    assert plan.predicate is not None
    assert plan.predicate.op == "or"


def test_write_sql_still_blocked() -> None:
    plan = SemanticQueryPlan(
        query_kind="list",
        entity="building",
        select=["name"],
        limit=10,
    )
    sql = compile_semantic_plan(plan).sql.upper()
    for word in ("INSERT", "UPDATE", "DELETE", "DROP"):
        assert word not in sql
