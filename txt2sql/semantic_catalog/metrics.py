"""Metric / aggregation support metadata."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricSupport:
    concept: str
    aggregations: frozenset[str]
    preferred_dataset: str


METRICS: dict[str, MetricSupport] = {
    "building.height": MetricSupport(
        "building.height",
        frozenset({"avg", "min", "max", "median", "stddev", "percentile", "count"}),
        "building_gis_d010",
    ),
    "building.gross_floor_area": MetricSupport(
        "building.gross_floor_area",
        frozenset({"avg", "sum", "min", "max", "median", "stddev", "percentile", "count"}),
        "building_gis_d010",
    ),
    "building.building_coverage_ratio": MetricSupport(
        "building.building_coverage_ratio",
        frozenset({"avg", "min", "max", "median", "count"}),
        "building_gis_d010",
    ),
    "building.floor_area_ratio": MetricSupport(
        "building.floor_area_ratio",
        frozenset({"avg", "min", "max", "median", "count"}),
        "building_gis_d010",
    ),
    "building.ground_floors": MetricSupport(
        "building.ground_floors",
        frozenset({"avg", "min", "max", "median", "count"}),
        "building_gis_d010",
    ),
    "building.basement_floors": MetricSupport(
        "building.basement_floors",
        frozenset({"avg", "min", "max", "count"}),
        "building_gis_d010",
    ),
}
