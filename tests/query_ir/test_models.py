"""QueryIR model smoke tests."""

from txt2sql.query_ir import QueryIR, assess_completeness
from txt2sql.query_ir.models import AggregationIR, MeasureIR, PredicateIR, ScopeIR


def test_query_ir_defaults() -> None:
    ir = QueryIR()
    assert ir.task == "unknown"
    assert ir.entity == "building"
    assert ir.predicates == []


def test_completeness_ready_for_count() -> None:
    ir = QueryIR(
        task="count",
        entity="building",
        scope=ScopeIR(place="동래구"),
        aggregations=[AggregationIR(function="count")],
    )
    report = assess_completeness(ir)
    assert report.status == "READY"
    assert report.entity_binding == "PASS"


def test_completeness_fails_unbound_avg() -> None:
    ir = QueryIR(
        task="aggregate",
        aggregations=[AggregationIR(function="avg", field=None)],
        measures=[],
    )
    report = assess_completeness(ir)
    assert report.aggregation_binding == "FAIL"
    assert "SEMANTIC_UNBOUND_METRIC" in report.reasons


def test_predicate_tree() -> None:
    ir = QueryIR(
        task="count",
        predicates=[
            PredicateIR(
                logical_group="and",
                children=[
                    PredicateIR(field="usage", operator="eq", value="공동주택"),
                    PredicateIR(field="height_m", operator="gte", value=50),
                ],
            )
        ],
        measures=[MeasureIR(concept="height_m")],
    )
    assert len(ir.predicates[0].children) == 2
