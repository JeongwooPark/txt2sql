"""Round-trip QueryIR <-> SemanticQueryPlan."""

from txt2sql.query_ir import plan_to_query_ir, query_ir_to_semantic_plan
from txt2sql.semantic_plan.models import (
    AggregationSpec,
    FilterSpec,
    PlaceSpec,
    ScopeSpec,
    SemanticQueryPlan,
)


def test_plan_roundtrip_preserves_meaning() -> None:
    plan = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="동래구", kind="gu")),
        filters=[FilterSpec(field="usage", operator="eq", value="단독주택")],
        aggregations=[AggregationSpec(function="count")],
        limit=5,
    )
    ir = plan_to_query_ir(plan)
    back = query_ir_to_semantic_plan(ir)
    assert back.entity == "building"
    assert back.scope is not None and back.scope.place is not None
    assert back.scope.place.name == "동래구"
    assert any(f.field == "usage" and f.value == "단독주택" for f in back.filters)
    assert back.limit == 5
