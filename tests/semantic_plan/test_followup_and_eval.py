from llm2sql.evaluation.taxonomy import classify_root_causes
from llm2sql.semantic_plan.followup import apply_plan_delta, parse_followup_delta
from llm2sql.semantic_plan.models import (
    FilterSpec,
    OperandSpec,
    PlaceSpec,
    PredicateSpec,
    ScopeSpec,
    SemanticQueryPlan,
)
from llm2sql.semantic_plan.predicate_utils import effective_predicate, has_op


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
