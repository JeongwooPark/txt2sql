"""Binding catalog and SQP compiler catalog must share one physical map."""

from __future__ import annotations

from txt2sql.semantic_catalog.datasets import CONCEPT_PHYSICAL_FIELDS, DATASETS
from txt2sql.canonical_physical_columns import (
    CONCEPT_PHYSICAL_FIELDS as CANONICAL_PHYS,
    CONCEPT_TO_FIELD,
    D010_FIELD_COLUMNS,
    D198_FIELD_COLUMNS,
)
from txt2sql.semantic_plan.catalog import BUILDING_FIELDS
from txt2sql.semantic_plan.compiler import D198_BUILDING_COLUMNS


def test_datasets_reexports_canonical_physical_map() -> None:
    assert CONCEPT_PHYSICAL_FIELDS is CANONICAL_PHYS


def test_sqp_building_fields_match_d010_map() -> None:
    for field_key, column in D010_FIELD_COLUMNS.items():
        if field_key not in BUILDING_FIELDS:
            continue
        assert BUILDING_FIELDS[field_key].column == column, (
            f"BUILDING_FIELDS[{field_key}]={BUILDING_FIELDS[field_key].column} "
            f"!= D010_FIELD_COLUMNS[{field_key}]={column}"
        )


def test_d198_compiler_map_matches_canonical() -> None:
    for key, column in D198_FIELD_COLUMNS.items():
        assert D198_BUILDING_COLUMNS[key] == column


def test_concept_physical_matches_sqp_for_d010() -> None:
    """Every D010 concept binding column must equal the SQP field column."""
    for concept, field_key in CONCEPT_TO_FIELD.items():
        d010_col = CONCEPT_PHYSICAL_FIELDS.get(concept, {}).get("building_gis_d010")
        if not d010_col:
            continue
        assert field_key in BUILDING_FIELDS, f"missing SQP field for {concept}"
        # D198-only slots must not appear under building_gis_d010.
        assert concept not in {
            "building.detail_usage",
            "building.permit_date",
        }
        assert BUILDING_FIELDS[field_key].column == d010_col, (
            f"{concept}: binding={d010_col} sqp={BUILDING_FIELDS[field_key].column}"
        )


def test_concept_physical_matches_d198_for_attr_dataset() -> None:
    for concept, field_key in CONCEPT_TO_FIELD.items():
        d198_col = CONCEPT_PHYSICAL_FIELDS.get(concept, {}).get("building_attr_d198")
        if not d198_col:
            continue
        assert D198_FIELD_COLUMNS[field_key] == d198_col, (
            f"{concept}: binding D198={d198_col} map={D198_FIELD_COLUMNS[field_key]}"
        )


def test_detail_usage_not_on_d010_dataset() -> None:
    assert "building.detail_usage" not in DATASETS["building_gis_d010"].concepts
    assert "building.detail_usage" in DATASETS["building_attr_d198"].concepts
    assert "building_gis_d010" not in CONCEPT_PHYSICAL_FIELDS["building.detail_usage"]
    assert CONCEPT_PHYSICAL_FIELDS["building.detail_usage"]["building_attr_d198"] == "A27"


def test_known_mismatch_examples_are_fixed() -> None:
    """Regression: Binding must not claim the old wrong D010 letters."""
    assert CONCEPT_PHYSICAL_FIELDS["building.ground_floors"]["building_gis_d010"] == "A26"
    assert CONCEPT_PHYSICAL_FIELDS["building.basement_floors"]["building_gis_d010"] == "A27"
    assert CONCEPT_PHYSICAL_FIELDS["building.approval_date"]["building_gis_d010"] == "A13"
    assert BUILDING_FIELDS["ground_floors"].column == "A26"
    assert BUILDING_FIELDS["basement_floors"].column == "A27"
    assert BUILDING_FIELDS["approval_date"].column == "A13"
    assert BUILDING_FIELDS["site_area_m2"].column == "A15"  # not ground floors
    # detail_usage letter equals D198 A27, not a fake D010 A10.
    assert BUILDING_FIELDS["detail_usage"].column == D198_FIELD_COLUMNS["detail_usage"]
