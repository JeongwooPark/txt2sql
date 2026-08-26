"""Dataset capability definitions for semantic binding."""

from __future__ import annotations

from dataclasses import dataclass, field


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
        physical_table="AL_D010_26_20250704",
        entity="building",
        grain="building_unit",
        priority=10,
        concepts=frozenset(
            {
                "building.height",
                "building.usage",
                "building.detail_usage",
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
        caveats=("primary GIS building inventory",),
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
                "building.approval_date",
                "building.age",
                "admin.sigungu",
                "admin.legal_dong",
            }
        ),
        supports_spatial=False,
        temporal_coverage="year_stats",
        caveats=("attribute/year-grain oriented; conflicts with d010 on shared concepts",),
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
        physical_table="TL_KODIS_BAS_26_202507",
        entity="basic_zone",
        grain="bas_polygon",
        priority=40,
        concepts=frozenset(),
        supports_spatial=True,
    ),
}


# concept -> preferred physical field on each dataset
CONCEPT_PHYSICAL_FIELDS: dict[str, dict[str, str]] = {
    "building.height": {"building_gis_d010": "A16"},
    "building.usage": {"building_gis_d010": "A9", "building_attr_d198": "usage"},
    "building.detail_usage": {"building_gis_d010": "A10", "building_attr_d198": "detail_usage"},
    "building.approval_date": {"building_gis_d010": "A24", "building_attr_d198": "approval_date"},
    "building.floor_area_ratio": {"building_gis_d010": "A18"},
    "building.building_coverage_ratio": {"building_gis_d010": "A17"},
    "building.gross_floor_area": {"building_gis_d010": "A14"},
    "building.ground_floors": {"building_gis_d010": "A15"},
    "building.basement_floors": {"building_gis_d010": "A19"},
    "building.age": {"building_gis_d010": "A24", "building_attr_d198": "approval_date"},
    "admin.sigungu": {"building_gis_d010": "A3", "admin_boundary": "SIGUNGU_NM"},
    "admin.legal_dong": {"building_gis_d010": "A4", "admin_boundary": "DONG_NM"},
}
