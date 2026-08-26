"""SemanticQueryPlan -> QueryIR adapter tests."""

from txt2sql.query_ir import plan_to_query_ir
from txt2sql.semantic_plan.models import (
    AggregationSpec,
    FilterSpec,
    OrderSpec,
    PlaceSpec,
    ScopeSpec,
    SemanticQueryPlan,
)


def _sample_plan() -> SemanticQueryPlan:
    return SemanticQueryPlan(
        query_kind="aggregate",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="해운대구", kind="gu")),
        filters=[
            FilterSpec(field="usage", operator="eq", value="공동주택"),
            FilterSpec(field="gross_floor_area_m2", operator="gte", value=1000),
        ],
        aggregations=[AggregationSpec(function="avg", field="gross_floor_area_m2", alias="avg_gfa")],
        group_by=["usage"],
        order_by=[OrderSpec(field="avg_gfa", direction="desc")],
        limit=10,
    )


def test_plan_adapter_preserves_core_slots() -> None:
    plan = _sample_plan()
    ir = plan_to_query_ir(plan)
    assert ir.task == "aggregate"
    assert ir.entity == "building"
    assert ir.scope is not None and ir.scope.place == "해운대구"
    assert any(p.field == "usage" for p in ir.predicates)
    assert any(a.function == "avg" and a.field == "gross_floor_area_m2" for a in ir.aggregations)
    assert any(d.field == "usage" for d in ir.dimensions)
    assert ir.limit == 10
    assert ir.ordering


def test_plan_adapter_group_and_percentile() -> None:
    plan = SemanticQueryPlan(
        query_kind="distribution",
        entity="building",
        aggregations=[AggregationSpec(function="percentile", field="height_m", percentile=0.9)],
        group_by=["legal_dong"],
    )
    ir = plan_to_query_ir(plan)
    assert ir.task == "distribution"
    assert any(a.function == "percentile" and a.percentile == 0.9 for a in ir.aggregations)
    assert any(d.field == "legal_dong" for d in ir.dimensions)
