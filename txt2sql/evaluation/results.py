"""순서 무관 result-set hash와 shape 비교. SQL 토큰 존재는 정답으로 쓰지 않는다."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

ResultMode = Literal["set", "sequence"]


def _cell(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {str(k): _cell(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_cell(v) for v in value]
    return value


def canonicalize_rows(rows: list[dict[str, Any]] | None, *, mode: ResultMode) -> list[list[Any]]:
    if not rows:
        return []
    tuples: list[list[Any]] = []
    for row in rows:
        items = sorted((_cell(k), _cell(v)) for k, v in row.items())
        tuples.append(items)
    if mode == "set":
        tuples.sort(key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
    return tuples


def result_hash(rows: list[dict[str, Any]] | None, *, mode: ResultMode = "set") -> str:
    canonical = canonicalize_rows(rows, mode=mode)
    payload = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compare_result_sets(
    predicted: list[dict[str, Any]] | None,
    gold: list[dict[str, Any]] | None,
    *,
    mode: ResultMode = "set",
    gold_hash: str | None = None,
) -> dict[str, Any]:
    pred_hash = result_hash(predicted, mode=mode)
    expected = gold_hash or result_hash(gold, mode=mode)
    return {
        "match": pred_hash == expected,
        "predicted_hash": pred_hash,
        "gold_hash": expected,
        "predicted_n": len(predicted or []),
        "gold_n": len(gold or []),
        "mode": mode,
    }
