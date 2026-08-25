"""catalog JSON/YAML loader. 운영 DB에 적용하지 않는다."""

from __future__ import annotations

import json
from pathlib import Path

from txt2sql.semantic_catalog.models import SourceBinding
from txt2sql.semantic_catalog.registry import SOURCE_BINDINGS


def load_bindings(path: Path | None = None) -> dict[str, SourceBinding]:
    if path is None:
        return dict(SOURCE_BINDINGS)
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, SourceBinding] = {}
    for key, item in payload.items():
        out[key] = SourceBinding(
            entity=item["entity"],
            table=item["table"],
            version=item["version"],
            schema=item.get("schema", "public"),
        )
    if len(out) != len({b.table for b in out.values()}):
        raise ValueError("duplicate table binding")
    return out
