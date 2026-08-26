"""Physical executor capability matrix (LogicalPlan ops)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExecutorCapability:
    strategy: str
    ops: frozenset[str]
    datasets: frozenset[str] = field(default_factory=frozenset)


EXECUTOR_CAPABILITIES: dict[str, ExecutorCapability] = {
    "FAST_SIMPLE_COUNT": ExecutorCapability(
        "FAST_SIMPLE_COUNT",
        frozenset({"Scan", "Filter", "Aggregate", "Project", "Limit"}),
        frozenset({"building_gis_d010"}),
    ),
    "FAST_THRESHOLD": ExecutorCapability(
        "FAST_THRESHOLD",
        frozenset({"Scan", "Filter", "Aggregate", "Project", "Limit", "Sort"}),
        frozenset({"building_gis_d010"}),
    ),
    "D010_EXECUTOR": ExecutorCapability(
        "D010_EXECUTOR",
        frozenset(
            {
                "Scan",
                "Filter",
                "TemporalFilter",
                "Project",
                "Aggregate",
                "Group",
                "Sort",
                "Limit",
                "Compare",
                "Ratio",
                "DerivedMetric",
                "Percentile",
            }
        ),
        frozenset({"building_gis_d010"}),
    ),
    "D198_EXECUTOR": ExecutorCapability(
        "D198_EXECUTOR",
        frozenset({"Scan", "Filter", "TemporalFilter", "Aggregate", "Group", "Sort", "Limit", "Project"}),
        frozenset({"building_attr_d198"}),
    ),
    "BASIC_ZONE_EXECUTOR": ExecutorCapability(
        "BASIC_ZONE_EXECUTOR",
        frozenset({"Scan", "Filter", "SpatialFilter", "Aggregate", "Group", "Project", "Limit"}),
        frozenset({"basic_zone"}),
    ),
    "SPATIAL_EXECUTOR": ExecutorCapability(
        "SPATIAL_EXECUTOR",
        frozenset({"Scan", "Filter", "SpatialFilter", "Aggregate", "Project", "Sort", "Limit", "Group"}),
        frozenset({"building_gis_d010", "admin_boundary", "basic_zone"}),
    ),
    "GENERIC_SQL_EXECUTOR": ExecutorCapability(
        "GENERIC_SQL_EXECUTOR",
        frozenset(
            {
                "Scan",
                "Filter",
                "TemporalFilter",
                "SpatialFilter",
                "Project",
                "Aggregate",
                "Group",
                "Sort",
                "Limit",
                "Compare",
                "Ratio",
                "DerivedMetric",
                "Percentile",
            }
        ),
    ),
}


def supports_all_ops(strategy: str, ops: set[str]) -> bool:
    cap = EXECUTOR_CAPABILITIES.get(strategy)
    if cap is None:
        return False
    return ops.issubset(cap.ops)
