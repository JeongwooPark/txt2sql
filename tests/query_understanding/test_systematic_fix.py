from llm2sql.query_understanding.contract import extract_contract
from llm2sql.query_understanding.gate import accept_heuristic_plan
from llm2sql.semantic_plan.catalog import get_field
from llm2sql.semantic_plan.generator import try_heuristic_plan
from llm2sql.semantic_plan.models import (
    AggregationSpec,
    OperandSpec,
    PredicateSpec,
    PlaceSpec,
    ScopeSpec,
    SemanticQueryPlan,
)
from llm2sql.semantic_plan.contract_verifier import verify_contract
from llm2sql.route_capability import SIMPLE_COUNT, missing_slots


def test_outputs_are_actually_bound() -> None:
    c = extract_contract("해운대구 건물 이름과 높이를 보여줘")
    assert c.outputs
    assert c.all_requested_outputs_bound is True
    assert {item.value for item in c.outputs} >= {"name", "height_m"}


def test_or_operands_are_recorded() -> None:
    c = extract_contract("수영구 숙박시설 또는 위락시설 중 연면적 1000㎡ 이상")
    ors = [item for item in c.boolean_ops if item.kind == "or"]
    assert ors
    assert ors[0].meta.get("left")
    assert ors[0].meta.get("right")


def test_greedy_numeric_binding_does_not_reuse_metric() -> None:
    c = extract_contract("높이 40m 이상 층수 12층 이상 연면적 4000㎡ 이상")
    fields = [item.meta.get("field") for item in c.numbers]
    assert "height_m" in fields
    assert "ground_floors" in fields
    assert "gross_floor_area_m2" in fields


def test_nested_or_passes_gate_and_verifier() -> None:
    q = "연제구 공동주택 또는 단독주택이면서 높이 30m 이상"
    pred = PredicateSpec(
        op="and",
        args=[
            PredicateSpec(
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
            PredicateSpec(
                op="cmp",
                operator="gte",
                left=OperandSpec(kind="field", field="height_m"),
                right=OperandSpec(kind="literal", value=30),
            ),
        ],
    )
    plan = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="연제구", kind="gu")),
        predicate=pred,
    )
    contract = extract_contract(q)
    assert accept_heuristic_plan(contract, plan) is True
    result = verify_contract(q, plan)
    assert result.ok is True


def test_multi_aggregate_set_is_checked() -> None:
    q = "해운대구 건물 높이 합계와 평균"
    plan = SemanticQueryPlan(
        query_kind="aggregate",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="해운대구", kind="gu")),
        aggregations=[
            AggregationSpec(function="sum", field="height_m", alias="sum_height_m"),
            AggregationSpec(function="avg", field="height_m", alias="avg_height_m"),
        ],
    )
    assert accept_heuristic_plan(extract_contract(q), plan) is True
    assert verify_contract(q, plan).ok is True


def test_catalog_coverage_and_industrial() -> None:
    assert get_field("building", "building_coverage_ratio").column == "A17"
    assert get_field("building", "floor_area_ratio").column == "A18"
    assert get_field("building", "violation_status").column == "A20"
    assert get_field("industrial_complex", "name").column == "A8"


def test_legacy_route_blocked_when_or_present() -> None:
    c = extract_contract("수영구 숙박시설 또는 위락시설 채수")
    assert "or" in missing_slots(SIMPLE_COUNT, c)


def test_heuristic_does_not_drop_or_when_compare_present() -> None:
    q = "남구 공동주택 또는 단독주택 중 건축면적이 연면적보다 큰 건물"
    plan = try_heuristic_plan(q)
    assert plan is not None
    assert plan.predicate is not None
    assert plan.predicate.op == "or"
    assert any(item.value_field for item in plan.filters)
