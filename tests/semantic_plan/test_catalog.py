from txt2sql.domain import reset_d198_coverage, set_d198_coverage
from txt2sql.semantic_plan.catalog import get_field, is_allowed_physical_identifier
from txt2sql.semantic_plan.compiler import compile_semantic_plan
from txt2sql.semantic_plan.models import (
    FilterSpec,
    PlaceSpec,
    ScopeSpec,
    SemanticQueryPlan,
    UnknownSemanticFieldError,
)


def test_building_name_maps_to_a24() -> None:
    assert get_field("building", "name").column == "A24"


def test_building_height_maps_to_a16() -> None:
    assert get_field("building", "height_m").column == "A16"


def test_gross_floor_area_maps_to_a14() -> None:
    assert get_field("building", "gross_floor_area_m2").column == "A14"


def test_building_area_maps_to_a12() -> None:
    assert get_field("building", "building_area_m2").column == "A12"


def test_unknown_field_raises() -> None:
    try:
        get_field("building", "market_cap")
    except UnknownSemanticFieldError:
        return
    raise AssertionError("unknown field should raise")


def test_runtime_d198_latest_table_is_allowed_and_compiles() -> None:
    latest = "AL_D198_26410_20260715"
    try:
        set_d198_coverage({"금정구": latest})
        assert is_allowed_physical_identifier(latest)
        plan = SemanticQueryPlan(
            query_kind="count",
            entity="building",
            scope=ScopeSpec(place=PlaceSpec(name="금정구", kind="gu")),
            filters=[
                FilterSpec(
                    field="detail_usage",
                    operator="contains",
                    value="오피스텔",
                )
            ],
        )
        sql = compile_semantic_plan(plan).sql
        assert latest in sql
    finally:
        reset_d198_coverage()


def test_unregistered_d198_table_stays_rejected() -> None:
    assert not is_allowed_physical_identifier("AL_D198_26410_20990101")
