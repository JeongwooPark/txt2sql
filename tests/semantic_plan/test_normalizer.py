from txt2sql.domain import USAGE_ALIASES
from txt2sql.semantic_plan.models import FilterSpec, SemanticQueryPlan
from txt2sql.semantic_plan.normalizer import normalize_semantic_plan
from txt2sql.units import PYEONG_TO_M2


def test_usage_apartment_to_multiunit() -> None:
    plan = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        filters=[FilterSpec(field="usage", operator="eq", value="아파트")],
    )
    out = normalize_semantic_plan(plan, "아파트 몇 채")
    assert out.filters[0].value == USAGE_ALIASES["아파트"]
    assert out.filters[0].value == "공동주택"


def test_pyeong_to_m2() -> None:
    plan = SemanticQueryPlan(
        query_kind="list",
        entity="building",
        filters=[
            FilterSpec(
                field="gross_floor_area_m2",
                operator="gte",
                value=30,
                unit="평",
            )
        ],
        select=["name"],
    )
    out = normalize_semantic_plan(plan, "30평 이상")
    assert abs(float(out.filters[0].value) - 30 * PYEONG_TO_M2) < 0.01
    assert out.filters[0].unit == "m2"


def test_km_to_m() -> None:
    plan = SemanticQueryPlan(
        query_kind="list",
        entity="building",
        filters=[FilterSpec(field="height_m", operator="gte", value=2, unit="km")],
        select=["name", "height_m"],
    )
    out = normalize_semantic_plan(plan, "높이 2km")
    assert float(out.filters[0].value) == 2000.0
    assert out.filters[0].unit == "m"
