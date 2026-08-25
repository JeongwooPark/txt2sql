from txt2sql.evaluation.taxonomy import classify_root_causes
from txt2sql.semantic_plan.followup import apply_plan_delta, parse_followup_delta
from txt2sql.semantic_plan.models import (
    FilterSpec,
    OperandSpec,
    PlaceSpec,
    PredicateSpec,
    ScopeSpec,
    SemanticQueryPlan,
)
from txt2sql.semantic_plan.predicate_utils import effective_predicate, has_op


def test_followup_ands_into_canonical_predicate() -> None:
    base = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="해운대구", kind="gu")),
        predicate=PredicateSpec(
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
        ),
        filters=[FilterSpec(field="usage", operator="eq", value="공동주택")],
    )
    delta = parse_followup_delta("그중 높이 40m 이상만")
    assert delta is not None
    merged = apply_plan_delta(base, delta)
    pred = effective_predicate(merged)
    assert has_op(pred, "or")
    assert any(item.field == "height_m" for item in merged.filters)


def test_root_cause_timeout_and_or() -> None:
    causes = classify_root_causes(["P04", "Q02"], timed_out=True)
    assert "EXECUTION_TIMEOUT" in causes
    assert "BOOLEAN_OR_DROPPED" in causes


def test_followup_uses_contract_range() -> None:
    delta = parse_followup_delta("그중 연면적 500㎡ 이상 3000㎡ 이하만")
    assert delta is not None
    fields = {item.field for item in delta.add_filters}
    assert "gross_floor_area_m2" in fields


def test_diagnose_eval_failure_or_drop() -> None:
    from txt2sql.evaluation.taxonomy import diagnose_eval_failure

    causes = diagnose_eval_failure(
        question="수영구 숙박시설 또는 위락시설 채수",
        sql='SELECT COUNT(*) FROM t WHERE "A4" LIKE \'%수영구%\'',
        answer="12채",
        reason="count-mismatch",
        timed_out=False,
    )
    assert "BOOLEAN_OR_DROPPED" in causes


def test_followup_keeps_count_and_and_filter() -> None:
    base = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="수영구", kind="gu")),
        filters=[FilterSpec(field="usage", operator="eq", value="숙박시설")],
    )
    delta = parse_followup_delta("그중 연면적 8000㎡ 이상만")
    assert delta is not None
    merged = apply_plan_delta(base, delta)
    assert merged.query_kind == "count"
    pred = effective_predicate(merged)
    assert any(item.field == "gross_floor_area_m2" for item in merged.filters)
    assert pred is not None


def test_followup_avg_keeps_where() -> None:
    base = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="수영구", kind="gu")),
        filters=[
            FilterSpec(field="usage", operator="eq", value="숙박시설"),
            FilterSpec(field="gross_floor_area_m2", operator="gte", value=8000),
        ],
    )
    delta = parse_followup_delta("평균 높이")
    assert delta is not None
    merged = apply_plan_delta(base, delta)
    assert merged.query_kind == "aggregate"
    fields = {item.field for item in merged.filters}
    assert "usage" in fields
    assert "gross_floor_area_m2" in fields


def test_followup_dual_avg() -> None:
    delta = parse_followup_delta("평균 높이와 연면적")
    assert delta is not None
    assert delta.change_aggregations is not None
    agg_fields = {item.field for item in delta.change_aggregations}
    assert "height_m" in agg_fields
    assert "gross_floor_area_m2" in agg_fields


def test_followup_industrial_spatial() -> None:
    delta = parse_followup_delta("그중 산업단지 안만")
    assert delta is not None
    assert delta.add_spatial
    assert delta.add_spatial[0].target.entity == "industrial_complex"


def test_followup_spatial_event_survives_next_aggregate() -> None:
    from txt2sql.semantic_plan.followup import apply_followup_history, parse_followup_events

    base = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="강서구", kind="gu")),
        filters=[FilterSpec(field="usage", operator="eq", value="공장")],
    )
    events = parse_followup_events("그중 산업단지 안에 있는 것만")
    assert any(ev.op == "add_spatial" for ev in events)
    plan, combined = apply_followup_history(
        "그 공장들 평균 연면적",
        base,
        events,
    )
    assert plan is not None
    assert plan.spatial_relations
    assert any(ev.op == "add_spatial" for ev in combined)


def test_followup_filter_only_from_list_becomes_count() -> None:
    from txt2sql.semantic_plan.followup import apply_count_display_followup
    from txt2sql.session import SessionContext

    plan = {"query_kind": "list", "limit": 100, "select": ["name"]}
    SessionContext._coerce_count_display_plan(
        plan,
        "SELECT a, COUNT(*) OVER() AS total_n FROM t",
        "모두 675동입니다.",
    )
    assert plan["query_kind"] == "count"
    assert plan["limit"] is None

    base = SemanticQueryPlan(
        query_kind="list",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="해운대구", kind="gu")),
        filters=[FilterSpec(field="usage", operator="eq", value="공동주택")],
        limit=100,
        select=["name"],
    )
    delta = parse_followup_delta("그중 연면적 8000㎡ 이상만")
    assert delta is not None
    merged = apply_plan_delta(base, delta)
    session = SessionContext()
    session.last_sql = 'SELECT "A24", COUNT(*) OVER() AS total_n FROM "AL_D010_26_20250704"'
    session.last_answer = "해운대구 공동주택 높이 50m 이상은 모두 675동입니다."
    session.last_semantic_plan = {"query_kind": "list", "limit": 100}
    forced = apply_count_display_followup("그중 연면적 8000㎡ 이상만", merged, session)
    assert forced.query_kind == "count"
    assert forced.limit is None


def test_followup_sum_keeps_count() -> None:
    base = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="해운대구", kind="gu")),
        filters=[FilterSpec(field="usage", operator="eq", value="공동주택")],
    )
    delta = parse_followup_delta("합계")
    assert delta is not None
    merged = apply_plan_delta(base, delta)
    assert merged.query_kind == "aggregate"
    fns = {item.function for item in merged.aggregations}
    assert "count" in fns
    assert "sum" in fns


def test_expand_skips_semantic_plan_followup() -> None:
    from txt2sql.pipeline import _expand_followup_question
    from txt2sql.session import SessionContext

    session = SessionContext()
    session.last_semantic_plan = {"query_kind": "list", "entity": "building"}
    session.last_semantic_plan_route = "semantic_plan_list"
    session.last_sql = 'SELECT "A24", COUNT(*) OVER() FROM "AL_D010_26_20250704"'
    session.last_full_question = "해운대구 공동주택 중 높이 50m 이상인 건물 이름과 높이"
    expanded = _expand_followup_question("그중 연면적 8000㎡ 이상만", session)
    assert expanded == "그중 연면적 8000㎡ 이상만"
