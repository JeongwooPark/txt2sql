"""Join / relationship helpers (logical)."""

from __future__ import annotations

from txt2sql.semantic_catalog.registry import JOIN_EDGES, get_edge, list_entities


def related_entities(entity: str) -> tuple[str, ...]:
    found: list[str] = []
    for edge in JOIN_EDGES.values():
        if edge.source_entity == entity:
            found.append(edge.target_entity)
        elif edge.target_entity == entity:
            found.append(edge.source_entity)
    return tuple(dict.fromkeys(found))


__all__ = ["get_edge", "list_entities", "related_entities"]
