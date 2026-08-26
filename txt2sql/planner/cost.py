"""Physical plan cost model.

Unlike legacy route_cost(semantic_plan=1000), strategies are scored after
LogicalPlan is fixed — they do not compete with understanding.
"""

from __future__ import annotations

from txt2sql.planner.physical import PhysicalStrategy

BASE_COST: dict[PhysicalStrategy, float] = {
    "FAST_SIMPLE_COUNT": 0.5,
    "FAST_THRESHOLD": 1.0,
    "D010_EXECUTOR": 2.0,
    "D198_EXECUTOR": 3.0,
    "BASIC_ZONE_EXECUTOR": 4.0,
    "SPATIAL_EXECUTOR": 5.0,
    "GENERIC_SQL_EXECUTOR": 8.0,
}


def strategy_cost(strategy: PhysicalStrategy, *, op_count: int = 0) -> float:
    return BASE_COST[strategy] + 0.05 * max(0, op_count - 3)
