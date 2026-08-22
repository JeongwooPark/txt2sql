from llm2sql.semantic_plan.catalog import get_field
from llm2sql.semantic_plan.models import UnknownSemanticFieldError


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
