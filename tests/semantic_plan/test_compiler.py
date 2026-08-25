from llm2sql.semantic_plan.compiler import compile_semantic_plan
from llm2sql.semantic_plan.models import (
    FilterSpec,
    PlaceSpec,
    ScopeSpec,
    SemanticQueryPlan,
)
from llm2sql.semantic_plan.normalizer import normalize_semantic_plan


def _plan_height_list() -> SemanticQueryPlan:
    return SemanticQueryPlan(
        query_kind="list",
        entity="building",
        scope=ScopeSpec(
            place=PlaceSpec(name="해운대구", kind="gu"),
            spatial_mode="auto",
        ),
        filters=[
            FilterSpec(field="usage", operator="eq", value="아파트"),
            FilterSpec(field="height_m", operator="gte", value=100, unit="m"),
        ],
        select=["name", "height_m"],
        limit=100,
    )


def test_compiler_building_height_filter() -> None:
    plan = normalize_semantic_plan(
        _plan_height_list(),
        "해운대구 아파트 중 높이 100m 이상",
    )
    compiled = compile_semantic_plan(plan)
    sql = compiled.sql
    assert "AL_D010_26_20250704" in sql
    assert '"A3"' in sql or '"A4"' in sql
    assert '"A9"' in sql
    assert '"A16"' in sql
    assert "공동주택" in sql
    upper = sql.upper()
    for banned in ("INSERT", "UPDATE", "DELETE", "DROP"):
        assert banned not in upper
    assert "SELECT *" not in upper


def test_compiler_rejects_sql_injection_in_place() -> None:
    plan = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        scope=ScopeSpec(
            place=PlaceSpec(name="해운대구' OR 1=1 --", kind="gu")
        ),
    )
    sql = compile_semantic_plan(plan).sql
    assert "해운대구''" in sql
    assert sql.upper().startswith("SELECT")
    assert sql.count(";") <= 1
    assert "INSERT" not in sql.upper()


def test_compiler_count_and_rank() -> None:
    count_plan = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="금정구", kind="gu")),
        filters=[FilterSpec(field="usage", operator="eq", value="공동주택")],
    )
    count_sql = compile_semantic_plan(count_plan).sql
    assert "COUNT(*)" in count_sql.upper()

    rank_plan = SemanticQueryPlan(
        query_kind="rank",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="동래구", kind="gu")),
        filters=[FilterSpec(field="structure", operator="eq", value="철근콘크리트")],
        select=["name", "height_m"],
        order_by=[],
        limit=10,
    )
    rank_plan = normalize_semantic_plan(rank_plan, "동래구 철근콘크리트 건물 중 높이가 높은 10개")
    rank_sql = compile_semantic_plan(rank_plan).sql
    assert "ORDER BY" in rank_sql.upper()
    assert "LIMIT 10" in rank_sql.upper()
    assert "철근콘크리트" in rank_sql
