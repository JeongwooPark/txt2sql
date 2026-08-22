"""PostGIS 공간 관계 정책. Plan에는 함수 문자열을 넣지 않고 compiler만 매핑한다."""

from __future__ import annotations

from dataclasses import dataclass

from llm2sql.semantic_plan.models import SemanticCompileError


@dataclass(frozen=True)
class SpatialPolicy:
    name: str
    postgis_fn: str
    kind: str


POLICIES: dict[str, SpatialPolicy] = {
    "covered_by": SpatialPolicy("covered_by", "ST_CoveredBy", "predicate"),
    "within": SpatialPolicy("within", "ST_CoveredBy", "predicate"),
    "intersects": SpatialPolicy("intersects", "ST_Intersects", "predicate"),
    "touches": SpatialPolicy("touches", "ST_Touches", "predicate"),
    "buffer": SpatialPolicy("buffer", "ST_DWithin", "distance"),
    "within_distance": SpatialPolicy("within_distance", "ST_DWithin", "distance"),
    "outside_distance": SpatialPolicy("outside_distance", "ST_DWithin", "distance_outside"),
    "nearest": SpatialPolicy("nearest", "ST_Distance", "nearest"),
    "overlap_ratio": SpatialPolicy("overlap_ratio", "ST_Intersection", "ratio"),
}


def resolve_spatial_policy(name: str) -> SpatialPolicy:
    policy = POLICIES.get(name)
    if policy is None:
        raise SemanticCompileError(f"unsupported spatial relation: {name}")
    return policy
