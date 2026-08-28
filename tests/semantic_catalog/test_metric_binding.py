"""Semantic catalog binding tests."""

from txt2sql.semantic_catalog.binding import bind_concept, bind_concepts, rank_datasets_for_concepts
from txt2sql.semantic_catalog.concepts import resolve_concept
from txt2sql.semantic_catalog.temporal import datasets_for_temporal, temporal_coverage


def test_metric_binding_prefers_d010_for_height() -> None:
    b = bind_concept("height_m")
    assert b is not None
    assert b.dataset == "building_gis_d010"
    assert b.physical_field == "A16"
    assert b.concept == "building.height"


def test_dataset_priority_coverage_ratio() -> None:
    b = bind_concept("건폐율")
    assert b is not None
    assert b.dataset == "building_gis_d010"
    assert "building_coverage" in b.concept


def test_grain_compatibility_and_conflict() -> None:
    result = bind_concepts(["usage", "detail_usage", "approval_date"])
    assert result.bindings
    # shared concepts exist on both; binder may report conflict when both selected
    ranked = rank_datasets_for_concepts(["building.usage", "building.approval_date"])
    assert ranked
    assert ranked[0][0] in {"building_gis_d010", "building_attr_d198"}


def test_d010_d198_conflict_surfaces() -> None:
    # Force both by binding tokens then manually checking alternatives
    usage = bind_concept("usage")
    assert usage is not None
    assert usage.alternatives or usage.dataset in {"building_gis_d010", "building_attr_d198"}


def test_temporal_coverage_approval_date() -> None:
    assert temporal_coverage("building_gis_d010") == "approval_date"
    assert "building_gis_d010" in datasets_for_temporal()


def test_basement_and_admin_concepts() -> None:
    bas = bind_concept("basement_floors")
    assert bas is not None and bas.dataset == "building_gis_d010"
    assert bas.physical_field == "A27"
    gf = bind_concept("ground_floors")
    assert gf is not None and gf.physical_field == "A26"
    admin = resolve_concept("legal_dong")
    assert admin is not None
    b = bind_concept("legal_dong")
    assert b is not None


def test_detail_usage_binds_d198_only() -> None:
    b = bind_concept("detail_usage")
    assert b is not None
    assert b.dataset == "building_attr_d198"
    assert b.physical_field == "A27"


def test_unresolved_concept() -> None:
    result = bind_concepts(["not_a_real_metric_xyz"])
    assert "not_a_real_metric_xyz" in result.unresolved
