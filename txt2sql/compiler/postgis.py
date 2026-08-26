"""PostGIS function names — compiler-only (never QueryIR)."""

from __future__ import annotations

RELATION_TO_POSTGIS = {
    "within": "ST_Within",
    "intersects": "ST_Intersects",
    "within_distance": "ST_DWithin",
    "touches": "ST_Touches",
}


def postgis_fn(relation: str) -> str:
    return RELATION_TO_POSTGIS.get(relation, "ST_Intersects")
