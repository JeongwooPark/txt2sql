"""Physical-name isolation and QueryIR normalization helpers."""

from __future__ import annotations

import re
from typing import Any, Iterable

from txt2sql.query_ir.models import QueryIR, QueryIRError, TaskName

_PHYSICAL_TABLE = re.compile(
    r"\b(?:AL_D\d+|BND_ADM\w*|TL_KODIS\w*)\b",
    re.IGNORECASE,
)
_PHYSICAL_COL = re.compile(r"\bA\d{1,2}\b")
_POSTGIS = re.compile(r"\bST_[A-Za-z0-9_]+\b")
_SQL_KW = re.compile(
    r"\b(?:SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|FROM|WHERE|JOIN|UNION|WITH)\b",
    re.IGNORECASE,
)

_TASK_ALIASES: dict[str, TaskName] = {
    "count": "count",
    "list": "list",
    "rank": "rank",
    "aggregate": "aggregate",
    "distribution": "distribution",
    "group": "group",
    "scalar": "aggregate",
    "ratio": "ratio",
    "compare": "compare",
    "meta": "meta",
}


def contains_physical_token(text: str | None) -> bool:
    if not text:
        return False
    return bool(
        _PHYSICAL_TABLE.search(text)
        or _PHYSICAL_COL.search(text)
        or _POSTGIS.search(text)
        or _SQL_KW.search(text)
    )


def assert_no_physical_names(value: Any, *, path: str = "root") -> None:
    if value is None:
        return
    if isinstance(value, str):
        if contains_physical_token(value):
            raise QueryIRError(f"physical/SQL token in QueryIR at {path}: {value!r}")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            assert_no_physical_names(item, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple, set)):
        for idx, item in enumerate(value):
            assert_no_physical_names(item, path=f"{path}[{idx}]")
        return
    if hasattr(value, "model_dump"):
        assert_no_physical_names(value.model_dump(), path=path)


def normalize_task(kind: str | None) -> TaskName:
    if not kind:
        return "unknown"
    return _TASK_ALIASES.get(kind.lower(), "unknown")


def result_shape_for_task(task: TaskName) -> str:
    if task in {"count", "aggregate", "ratio"}:
        return "scalar"
    if task in {"list", "rank"}:
        return "list"
    if task in {"group", "distribution", "compare"}:
        return "table"
    if task == "meta":
        return "text"
    return "unknown"


def normalize_query_ir(ir: QueryIR) -> QueryIR:
    data = ir.model_dump()
    assert_no_physical_names(data)
    task = normalize_task(ir.task)
    shape = ir.result_shape if ir.result_shape != "unknown" else result_shape_for_task(task)
    return ir.model_copy(update={"task": task, "result_shape": shape})


def collect_strings(obj: Any) -> Iterable[str]:
    if obj is None:
        return
    if isinstance(obj, str):
        yield obj
        return
    if isinstance(obj, dict):
        for v in obj.values():
            yield from collect_strings(v)
        return
    if isinstance(obj, (list, tuple, set)):
        for v in obj:
            yield from collect_strings(v)
        return
    if hasattr(obj, "model_dump"):
        yield from collect_strings(obj.model_dump())
