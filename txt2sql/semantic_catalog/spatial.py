"""Spatial capability helpers."""

from __future__ import annotations

from txt2sql.semantic_catalog.datasets import DATASETS


def datasets_with_spatial() -> tuple[str, ...]:
    return tuple(d.dataset_id for d in DATASETS.values() if d.supports_spatial)


def spatial_supported(dataset_id: str) -> bool:
    ds = DATASETS.get(dataset_id)
    return bool(ds and ds.supports_spatial)
