"""Decompose count-mismatch failures into semantic root causes."""

from __future__ import annotations

from collections import Counter
from typing import Any

from txt2sql.evaluation.case_map import case_rows


COUNT_MISMATCH_CAUSES = (
    "scope",
    "predicate",
    "dataset",
    "grain",
    "join",
    "spatial",
    "temporal",
    "agg",
    "eval",
    "unknown",
)


def classify_count_mismatch(
    *,
    question: str = "",
    sql: str | None = None,
    reason: str = "",
    route: str | None = None,
    root_causes: list[str] | None = None,
) -> str:
    """Map a count-mismatch case to a concrete semantic root cause (not unknown if possible)."""
    q = question or ""
    sql_u = (sql or "").upper()
    reason_l = (reason or "").lower()
    route_s = route or ""
    roots = {str(x) for x in (root_causes or [])}

    if "count-mismatch" not in reason_l and reason_l not in {"", "count_mismatch"}:
        # Still allow explicit caller path
        if "mismatch" not in reason_l:
            return "unknown"

    if any(x in roots for x in {"SPATIAL_TARGET_DROPPED"}) or "ST_" in sql_u or any(
        t in q for t in ("주변", "이내", "반경", "버퍼", "교차", "포함")
    ):
        if "ST_" in sql_u or any(t in q for t in ("주변", "이내", "반경", "버퍼")):
            return "spatial"

    if any(t in q for t in ("년", "년대", "경과", "사용승인", "허가", "건축년")) or "APPROVAL" in sql_u or "A13" in sql_u or "A34" in sql_u:
        if any(t in q for t in ("년", "년대", "경과", "사용승인", "허가", "건축년")):
            return "temporal"

    if "JOIN" in sql_u or "S04" in roots or route_s.startswith("buildings_in"):
        return "join"

    if "D198" in sql_u or "AL_D198" in sql_u:
        if any(t in q for t in ("연면적", "높이", "건폐", "용적", "층")):
            return "grain"
        return "dataset"

    if any(t in q for t in ("평균", "합계", "최대", "최소", "중앙", "비율")) or "AVG(" in sql_u or "SUM(" in sql_u:
        return "agg"

    if any(x in roots for x in {"PREDICATE_DROPPED", "RANGE_BOUND_DROPPED", "BOOLEAN_OR_DROPPED", "BOOLEAN_NOT_DROPPED"}):
        return "predicate"

    if any(t in q for t in ("구", "동", "읍", "면", "리", "부산")) and (
        "WHERE" not in sql_u or ("ADM" not in sql_u and "A3" not in sql_u and "A4" not in sql_u)
    ):
        return "scope"

    if reason_l.startswith("count-mismatch") and sql:
        # Numeric compare failed but SQL looks complete → evaluation/gold shape
        if "COUNT(" in sql_u or "SELECT" in sql_u:
            return "eval"

    if any(t in q for t in ("용도", "구조", "위반", "특수")):
        return "predicate"

    if "구" in q or "동" in q:
        return "scope"

    return "unknown"


def decompose_count_mismatches(payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    rows = case_rows(payload) if isinstance(payload, dict) else list(payload)
    mismatches: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for case in rows:
        reason = str(case.get("reason") or case.get("fail_reason") or "")
        if "count-mismatch" not in reason.lower():
            continue
        cause = classify_count_mismatch(
            question=str(case.get("q") or case.get("question") or ""),
            sql=case.get("sql_full") or case.get("sql"),
            reason=reason,
            route=case.get("route"),
            root_causes=list(case.get("root_causes") or []),
        )
        counts[cause] += 1
        mismatches.append({"id": case.get("id"), "cause": cause, "reason": reason, "route": case.get("route")})
    total = sum(counts.values()) or 1
    concrete = total - counts.get("unknown", 0)
    return {
        "total_count_mismatch": sum(counts.values()),
        "counts": dict(counts),
        "share_pct": {k: round(100.0 * v / total, 2) for k, v in counts.items()},
        "concrete_pct": round(100.0 * concrete / total, 2),
        "cases": mismatches,
    }
