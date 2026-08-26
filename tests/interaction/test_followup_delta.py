"""Interaction delta tests."""

from txt2sql.interaction import QueryIRDelta, apply_delta, classify_interaction_intent, followup_to_delta
from txt2sql.query_ir.models import AggregationIR, QueryIR, ScopeIR


def test_classify_visualize_vs_data() -> None:
    assert classify_interaction_intent("차트로 그려줘") == "visualize"
    assert classify_interaction_intent("동래구 건물 수는?") == "new_query"


def test_followup_limit_map_delta() -> None:
    prev = QueryIR(
        task="list",
        scope=ScopeIR(place="해운대구"),
        aggregations=[AggregationIR(function="count")],
    )
    refined = followup_to_delta("그중 상위 10개만 지도에서 보여줘", prev)
    assert refined is not None
    assert refined.limit == 10
    assert refined.interaction.presentation == "map"


def test_no_data_intent_hijack_for_chart_help() -> None:
    # chart help should be visualize/help, not treated as refine of prior SQL meaning
    assert classify_interaction_intent("차트 기능 어떻게 쓰나요?") in {"help", "visualize"}


def test_apply_filter_delta() -> None:
    ir = QueryIR(task="count")
    out = apply_delta(
        ir,
        QueryIRDelta(op="add_filter", payload={"field": "usage", "operator": "eq", "value": "공동주택"}),
    )
    assert out.predicates and out.predicates[0].field == "usage"
