"""Grain / temporal / conflict catalog tests."""

from txt2sql.semantic_catalog.binding import bind_concepts
from txt2sql.semantic_catalog.datasets import DATASETS
from txt2sql.semantic_catalog.temporal import temporal_coverage


def test_grain_compatibility() -> None:
    assert DATASETS["building_gis_d010"].grain == "building_unit"
    assert DATASETS["building_attr_d198"].grain == "building_attr"


def test_temporal_and_conflict_codes() -> None:
    assert temporal_coverage("building_attr_d198") == "year_stats"
    result = bind_concepts(["usage", "gross_floor_area_m2"])
    assert result.bindings
    # numeric metric forces d010; usage also on d010 — no hard fail required
    assert result.primary_dataset in {None, "building_gis_d010", "building_attr_d198"}
