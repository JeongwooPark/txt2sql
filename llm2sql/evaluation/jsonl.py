"""jsonl gold fixture IO."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from llm2sql.evaluation.schema import GoldPlanCase


def load_jsonl(path: Path) -> list[GoldPlanCase]:
    cases: list[GoldPlanCase] = []
    text = path.read_text(encoding="utf-8")
    for line_no, line in enumerate(text.splitlines(), 1):
        raw = line.strip()
        if not raw:
            continue
        try:
            cases.append(GoldPlanCase.model_validate_json(raw))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"{path}:{line_no}: invalid gold case: {exc}") from exc
    return cases


def dump_jsonl(path: Path, cases: Iterable[GoldPlanCase]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        case.model_dump_json(exclude_none=True) for case in cases
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
