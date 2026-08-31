"""QueryIR v2 semantic completeness — AggregationIR grain contract."""

from txt2sql.query_ir import QueryIR, assess_completeness
from txt2sql.query_ir.models import AggregationIR, GrainIR, ScopeIR


def test_aggregation_ir_grain_fields() -> None:
    agg = AggregationIR(
        function="count",
        distinct=True,
        grain=GrainIR(entity="admin_dong", distinct_key="admin_dong_id"),
        null_policy="EXCLUDE_NULL",
        unit="count",
        rounding=0,
    )
    assert agg.grain is not None
    assert agg.grain.entity == "admin_dong"
    assert agg.distinct is True


def test_count_distinct_requires_grain() -> None:
    ir = QueryIR(
        task="count",
        entity="building",
        scope=ScopeIR(place="금정구"),
        aggregations=[AggregationIR(function="count", distinct=True)],
    )
    report = assess_completeness(ir)
    assert report.aggregation_binding == "FAIL"
    assert "SEMANTIC_INCOMPLETE_GRAIN" in report.reasons


def test_simple_count_without_distinct_ok() -> None:
    ir = QueryIR(
        task="count",
        entity="building",
        scope=ScopeIR(place="금정구"),
        aggregations=[AggregationIR(function="count")],
    )
    report = assess_completeness(ir)
    assert report.status == "READY"


def test_query_ir_no_duplicate_top_level_metric() -> None:
    """Phase 5: no top-level metric/grain/group_by — use aggregations + dimensions."""
    ir = QueryIR()
    assert not hasattr(ir, "metric") or "metric" not in ir.model_fields
    assert "group_by" not in ir.model_fields
