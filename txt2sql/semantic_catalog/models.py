"""외부화된 semantic catalog 모델."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SourceBinding:
    entity: str
    table: str
    version: str
    schema: str = "public"


@dataclass(frozen=True)
class ValueProfile:
    table: str
    column: str
    canonical: str
    synonyms: tuple[str, ...] = ()
    frequency: int = 0
    source_version: str = ""


@dataclass(frozen=True)
class JoinEdge:
    edge_id: str
    source_entity: str
    target_entity: str
    cardinality: str
    spatial: bool = False
    cost: float = 1.0
    metadata: dict = field(default_factory=dict)
