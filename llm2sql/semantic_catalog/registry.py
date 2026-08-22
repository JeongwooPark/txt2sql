"""entity/field/join registry. compiler 분기를 늘리지 않고 binding을 외부화한다."""

from __future__ import annotations

from llm2sql.semantic_catalog.models import JoinEdge, SourceBinding, ValueProfile
from llm2sql.semantic_plan.catalog import (
    ADMIN_TABLE,
    BASIC_ZONE_TABLE,
    BUILDING_TABLE,
    ENTITIES,
    INDUSTRIAL_TABLE,
)

SOURCE_BINDINGS: dict[str, SourceBinding] = {
    "building": SourceBinding("building", BUILDING_TABLE, "20250704"),
    "admin_area": SourceBinding("admin_area", ADMIN_TABLE, "static"),
    "basic_zone": SourceBinding("basic_zone", BASIC_ZONE_TABLE, "202507"),
    "industrial_complex": SourceBinding("industrial_complex", INDUSTRIAL_TABLE, "20250804"),
}

JOIN_EDGES: dict[str, JoinEdge] = {
    "building_in_admin": JoinEdge(
        "building_in_admin", "building", "admin_area", "n:1", spatial=True, cost=1.0
    ),
    "building_in_basic_zone": JoinEdge(
        "building_in_basic_zone", "building", "basic_zone", "n:1", spatial=True, cost=1.2
    ),
    "building_in_industrial": JoinEdge(
        "building_in_industrial", "building", "industrial_complex", "n:1", spatial=True, cost=1.3
    ),
}

VALUE_PROFILES: tuple[ValueProfile, ...] = (
    ValueProfile(BUILDING_TABLE, "A9", "공동주택", ("아파트", "연립주택"), 1, "20250704"),
    ValueProfile(BUILDING_TABLE, "A9", "단독주택", ("주택",), 1, "20250704"),
    ValueProfile(BUILDING_TABLE, "A9", "창고시설", ("창고",), 1, "20250704"),
    ValueProfile(BUILDING_TABLE, "A9", "교육연구시설", ("학교",), 1, "20250704"),
    ValueProfile(BUILDING_TABLE, "A9", "업무시설", ("사무실",), 1, "20250704"),
    ValueProfile(BUILDING_TABLE, "A9", "판매시설", ("상가",), 1, "20250704"),
    ValueProfile(BUILDING_TABLE, "A9", "숙박시설", ("호텔",), 1, "20250704"),
)


def list_entities() -> tuple[str, ...]:
    extra = ("industrial_complex",)
    return tuple(dict.fromkeys([*ENTITIES.keys(), *extra]))


def get_binding(entity: str) -> SourceBinding:
    if entity not in SOURCE_BINDINGS:
        raise KeyError(f"unknown entity binding: {entity}")
    return SOURCE_BINDINGS[entity]


def get_edge(edge_id: str) -> JoinEdge:
    if edge_id not in JOIN_EDGES:
        raise KeyError(f"unknown join edge: {edge_id}")
    return JOIN_EDGES[edge_id]


def allowed_edges() -> frozenset[str]:
    return frozenset(JOIN_EDGES)


def detect_cycles() -> list[str]:
    return []


def duplicate_bindings() -> list[str]:
    tables = [item.table for item in SOURCE_BINDINGS.values()]
    dups = [name for name in tables if tables.count(name) > 1]
    return sorted(set(dups))
