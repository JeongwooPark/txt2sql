from txt2sql.semantic_plan.compiler import CompiledSemanticQuery, compile_semantic_plan
from txt2sql.semantic_plan.models import (
    AggregationSpec,
    OperandSpec,
    OrderSpec,
    PredicateSpec,
    SemanticQueryPlan,
)
from txt2sql.semantic_plan.result_shape import diagnose_result_shape
from txt2sql.semantic_plan.plan_sql_verifier import verify_plan_to_sql
from txt2sql.semantic_plan.selector import select_candidate, should_enumerate_candidates
from txt2sql.semantic_plan.sql_equivalence import verify_plan_sql_equivalence


def test_detects_or_missing_and_agg_change() -> None:
    pred = PredicateSpec(
        op="or",
        args=[
            PredicateSpec(
                op="cmp",
                operator="eq",
                left=OperandSpec(kind="field", field="usage"),
                right=OperandSpec(kind="literal", value="공동주택"),
            ),
            PredicateSpec(
                op="cmp",
                operator="eq",
                left=OperandSpec(kind="field", field="usage"),
                right=OperandSpec(kind="literal", value="단독주택"),
            ),
        ],
    )
    plan = SemanticQueryPlan(query_kind="count", entity="building", predicate=pred)
    bad_sql = 'SELECT COUNT(*) AS "count" FROM "AL_D010_26_20250704" b WHERE b."A9" = \'공동주택\';'
    errors = verify_plan_sql_equivalence(plan, bad_sql)
    assert "P04" in errors
    good = compile_semantic_plan(plan).sql
    assert verify_plan_sql_equivalence(plan, good) == []


def test_result_shape_and_zero_rows_ok() -> None:
    plan = SemanticQueryPlan(query_kind="count", entity="building")
    assert diagnose_result_shape(plan, []) == ["Q03"]
    assert diagnose_result_shape(plan, [{"count": 0}]) == []
    listed = SemanticQueryPlan(query_kind="list", entity="building", limit=10)
    assert diagnose_result_shape(listed, []) == []


def test_selector_is_deterministic() -> None:
    a = SemanticQueryPlan(
        query_kind="aggregate",
        entity="building",
        aggregations=[AggregationSpec(function="sum", field="height_m", alias="sum_height_m")],
    )
    b = SemanticQueryPlan(
        query_kind="aggregate",
        entity="building",
        aggregations=[AggregationSpec(function="avg", field="height_m", alias="avg_height_m")],
    )
    first = select_candidate([a, b], "해운대구 높이 합계")
    second = select_candidate([b, a], "해운대구 높이 합계")
    assert first.aggregations[0].function == second.aggregations[0].function == "sum"
    assert should_enumerate_candidates("연제구 공동주택 또는 단독주택 평균 높이") is True


def test_detects_not_missing_and_order_limit() -> None:
    pred = PredicateSpec(
        op="not",
        args=[
            PredicateSpec(
                op="cmp",
                operator="eq",
                left=OperandSpec(kind="field", field="usage"),
                right=OperandSpec(kind="literal", value="공동주택"),
            )
        ],
    )
    plan = SemanticQueryPlan(query_kind="count", entity="building", predicate=pred)
    and_sql = 'SELECT COUNT(*) AS "count" FROM "AL_D010_26_20250704" b WHERE b."A9" = \'공동주택\';'
    assert "P04" in verify_plan_sql_equivalence(plan, and_sql)

    ranked = SemanticQueryPlan(
        query_kind="rank",
        entity="building",
        order_by=[OrderSpec(field="height_m", direction="asc")],
        limit=10,
    )
    desc_sql = (
        'SELECT b."A8" FROM "AL_D010_26_20250704" b '
        'ORDER BY b."A16" DESC NULLS LAST LIMIT 5;'
    )
    errors = verify_plan_sql_equivalence(ranked, desc_sql)
    assert "P06" in errors

    sum_plan = SemanticQueryPlan(
        query_kind="aggregate",
        entity="building",
        aggregations=[AggregationSpec(function="sum", field="height_m", alias="sum_height_m")],
    )
    avg_sql = 'SELECT AVG(b."A16") AS "avg_height_m" FROM "AL_D010_26_20250704" b;'
    assert "P05" in verify_plan_sql_equivalence(sum_plan, avg_sql)


def test_detects_group_by_dropped_after_plan() -> None:
    plan = SemanticQueryPlan(
        query_kind="aggregate",
        entity="building",
        group_by=["usage"],
        aggregations=[AggregationSpec(function="count", alias="n")],
    )
    bad_sql = 'SELECT COUNT(*) AS "n" FROM "AL_D010_26_20250704" b;'
    compiled = CompiledSemanticQuery(
        sql=bad_sql,
        tables=["AL_D010_26_20250704"],
        route="semantic_plan_aggregate",
        semantic_plan=plan.model_dump(),
        extra={
            "compile_trace": {
                "predicate_nodes": [],
                "aggregations": ["count"],
                "group_fields": [],
            }
        },
    )
    assert "GROUP_BY_DROPPED" in verify_plan_to_sql(plan, compiled)
    assert "P05" in verify_plan_sql_equivalence(plan, bad_sql)
