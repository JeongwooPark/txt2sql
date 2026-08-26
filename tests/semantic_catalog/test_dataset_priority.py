"""Dataset priority / conflict tests."""

from txt2sql.semantic_catalog.binding import bind_concepts, rank_datasets_for_concepts
from txt2sql.semantic_catalog.datasets import DATASETS
from txt2sql.semantic_catalog.spatial import datasets_with_spatial, spatial_supported


def test_dataset_priority_ordering() -> None:
    ranked = rank_datasets_for_concepts(["building.height", "building.gross_floor_area"])
    assert ranked[0][0] == "building_gis_d010"


def test_spatial_geometry_datasets() -> None:
    ids = datasets_with_spatial()
    assert "building_gis_d010" in ids
    assert spatial_supported("building_gis_d010")
    assert not spatial_supported("building_attr_d198")


def test_building_age_binds() -> None:
    result = bind_concepts(["building.age"])
    assert result.bindings
    assert result.bindings[0].dataset in DATASETS
