"""Extract pass/fail maps from gold evaluation JSON documents."""

from __future__ import annotations

from typing import Any, Iterable


def case_rows(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Locate the primary case collection in a gold result document."""
    for key in ("rows", "cases", "results", "items"):
        value = doc.get(key)
        if isinstance(value, list) and value and isinstance(value[0], dict):
            # Prefer collections that look like scored cases
            if any(("id" in c or "qid" in c) and ("pass" in c or "passed" in c or "ok" in c) for c in value[:5]):
                return value
    for key in ("rows", "cases", "results", "items"):
        value = doc.get(key)
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return value
    return []


def case_id(case: dict[str, Any]) -> str:
    return str(case.get("id") or case.get("qid") or case.get("case_id") or "")


def case_passed(case: dict[str, Any]) -> bool | None:
    """Explicit field presence — do not use truthy OR chains across keys."""
    if "pass" in case:
        return bool(case["pass"])
    if "passed" in case:
        return bool(case["passed"])
    if "ok" in case:
        return bool(case["ok"])
    return None


def case_pass_map(doc: dict[str, Any]) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for case in case_rows(doc):
        cid = case_id(case)
        if not cid:
            continue
        passed = case_passed(case)
        if passed is None:
            continue
        out[cid] = passed
    return out


def iter_failed_cases(doc: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for case in case_rows(doc):
        passed = case_passed(case)
        if passed is False:
            yield case
