"""Temporal coverage helpers."""

from __future__ import annotations

from txt2sql.semantic_catalog.datasets import DATASETS


def temporal_coverage(dataset_id: str) -> str | None:
    ds = DATASETS.get(dataset_id)
    return ds.temporal_coverage if ds else None


def datasets_for_temporal(concept: str = "building.approval_date") -> tuple[str, ...]:
    out: list[str] = []
    for ds in DATASETS.values():
        if concept in ds.concepts and ds.temporal_coverage:
            out.append(ds.dataset_id)
    return tuple(out)
