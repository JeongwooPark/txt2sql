"""Dataset capability definitions for semantic binding."""

from __future__ import annotations

from dataclasses import dataclass

from txt2sql.canonical_physical_columns import CONCEPT_PHYSICAL_FIELDS as _CANONICAL_PHYS
from txt2sql.dataset_tables import (
    DEFAULT_BASIC_ZONE_TABLE,
    DEFAULT_BUILDING_TABLE,
)

# Re-export so existing `from ...datasets import CONCEPT_PHYSICAL_FIELDS` keeps working,
# while the only mutable definition lives in canonical_physical_columns.py.
CONCEPT_PHYSICAL_FIELDS = _CANONICAL_PHYS


@dataclass(frozen=True)
class DatasetCapability:
    dataset_id: str  # logical id, not necessarily physical table
    physical_table: str
    entity: str
    grain: str
    priority: int
    concepts: frozenset[str]
    supports_agg: bool = True
    supports_filter: bool = True
    supports_group: bool = True
    supports_sort: bool = True
    supports_spatial: bool = False
    temporal_coverage: str | None = None
    caveats: tuple[str, ...] = ()


# Logical dataset ids isolate physical names from QueryIR.
DATASETS: dict[str, DatasetCapability] = {
    "building_gis_d010": DatasetCapability(
        dataset_id="building_gis_d010",
        physical_table=DEFAULT_BUILDING_TABLE,
        entity="building",
        grain="building_unit",
        priority=10,
        concepts=frozenset(
            {
                "building.height",
                "building.usage",
                "building.structure",
                "building.approval_date",
                "building.floor_area_ratio",
                "building.building_coverage_ratio",
                "building.gross_floor_area",
                "building.ground_floors",
                "building.basement_floors",
                "building.age",
                "admin.sigungu",
                "admin.legal_dong",
            }
        ),
        supports_spatial=True,
        temporal_coverage="approval_date",
        caveats=(
            "primary GIS building inventory; "
            "detail_usage/permit_date are D198-only (not on D010)",
        ),
    ),
    "building_attr_d198": DatasetCapability(
        dataset_id="building_attr_d198",
        physical_table="AL_D198",  # logical family; concrete table resolved later
        entity="building",
        grain="building_attr",
        priority=20,
        concepts=frozenset(
            {
                "building.usage",
                "building.detail_usage",
                "building.structure",
                "building.approval_date",
                "building.permit_date",
                "building.age",
                "admin.sigungu",
                "admin.legal_dong",
            }
        ),
        supports_spatial=False,
        temporal_coverage="year_stats",
        caveats=("attribute/year-grain oriented; column numbers differ from D010",),
    ),
    "admin_boundary": DatasetCapability(
        dataset_id="admin_boundary",
        physical_table="BND_ADM_DONG_PG",
        entity="admin_area",
        grain="admin_polygon",
        priority=30,
        concepts=frozenset({"admin.sigungu", "admin.legal_dong"}),
        supports_agg=False,
        supports_spatial=True,
    ),
    "basic_zone": DatasetCapability(
        dataset_id="basic_zone",
        physical_table=DEFAULT_BASIC_ZONE_TABLE,
        entity="basic_zone",
        grain="bas_polygon",
        priority=40,
        concepts=frozenset(),
        supports_spatial=True,
    ),
}
