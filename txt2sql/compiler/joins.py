"""Join planning helpers (logical edge ids only)."""

from __future__ import annotations

from txt2sql.semantic_catalog.registry import get_edge


def resolve_join_edge(edge_id: str) -> dict[str, object]:
    edge = get_edge(edge_id)
    return {
        "edge_id": edge.edge_id,
        "source_entity": edge.source_entity,
        "target_entity": edge.target_entity,
        "spatial": edge.spatial,
        "cost": edge.cost,
    }
