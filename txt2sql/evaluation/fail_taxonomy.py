"""MAIN FAIL semantic error taxonomy (Phase 4)."""

from __future__ import annotations

import re
from typing import Any, Literal

ErrorClass = Literal[
    "SCOPE",
    "ENTITY",
    "DATASET",
    "FIELD",
    "PREDICATE",
    "OPERATOR",
    "AGGREGATION",
    "GRAIN",
    "GROUP",
    "TEMPORAL",
    "SPATIAL",
    "JOIN",
    "RANK",
    "CONTEXT",
    "BINDING",
    "COMPILER",
    "EXECUTION",
    "EVALUATOR",
    "GOLD",
    "DATA_QUALITY",
    "UNKNOWN",
]

EvalStatus = Literal[
    "ENGINE_ERROR",
    "GOLD_ERROR",
    "DATA_ERROR",
    "EVALUATOR_ERROR",
    "POLICY_GOLD_MISMATCH",
    "DATA_QUALITY",
    "PASS",
]


def classify_error_class(case: dict[str, Any]) -> tuple[str, str, float]:
    """Classify a FAIL case into error_class, error_subtype, confidence."""
    if case.get("pass"):
        return "PASS", "", 1.0

    from txt2sql.evaluation.case_map import case_execution_trace

    # Phase 2: prefer pipeline stage diagnosis from execution_trace
    trace = case_execution_trace(case)
    if trace:
        from txt2sql.evaluation.execution_trace import diagnose_from_trace

        ec, sub, conf = diagnose_from_trace(trace)
        if ec != "UNKNOWN":
            return ec, sub, conf

    reason = str(case.get("reason") or "").lower()
    kind = str(case.get("kind") or "")
    q = str(case.get("q") or "")
    sql = str(case.get("sql") or "")
    upper = sql.upper()
    exec_src = str(case.get("execution_source") or case.get("route") or "")
    root_causes = case.get("root_causes") or []

    # Heuristic classification
    if "timeout" in reason or "EXECUTION_TIMEOUT" in root_causes:
        return "EXECUTION", "TIMEOUT", 0.9

    if "scalar-mismatch" in reason or kind == "scalar":
        if any(k in q for k in ("비율", "평균", "avg", "%")):
            return "AGGREGATION", "AVG" if "평균" in q else "RATIO", 0.85
        return "AGGREGATION", "SCALAR_NUMERIC", 0.8

    if "count-mismatch" in reason or kind == "count":
        if any(k in q for k in ("행정동", "법정동", "동별")):
            return "GRAIN", "ADMIN_DONG" if "행정동" in q else "BUILDING", 0.8
        return "AGGREGATION", "COUNT", 0.85

    if "group-mismatch" in reason or kind == "group":
        if any(k in q for k in ("연도", "년")):
            return "GROUP", "YEAR", 0.85
        if any(k in q for k in ("용도", "구조")):
            return "GROUP", "USAGE", 0.8
        return "GROUP", "DIMENSION", 0.75

    if "list-top-missing" in reason or kind == "list":
        if "ENTITY_SELECTION_ERROR" in root_causes:
            return "ENTITY", "WRONG_ENTITY", 0.8
        return "FIELD", "OUTPUT_FIELD", 0.7

    if "compare" in kind:
        return "RANK", "COMPARISON", 0.75

    if any(k in q for k in ("m 이내", "m 밖", "반경", "거리", "경계")):
        if "ST_" not in upper and sql:
            return "SPATIAL", "OPERATOR_MISSING", 0.85
        if "밖" in q and "NOT ST_DWITHIN" not in upper:
            return "SPATIAL", "OUTSIDE_DISTANCE", 0.9
        return "SPATIAL", "DWITHIN", 0.8

    if any(k in q for k in ("행정동", "법정동")) and "SCOPE" not in str(root_causes):
        if "행정동" in q and "BND" not in upper and "ADM_NM" not in upper:
            return "SCOPE", "ADMIN_VS_LEGAL", 0.85
        if "법정동" in q and "A4" not in upper:
            return "SCOPE", "LEGAL_DONG", 0.8

    if "semantic_plan_clarify" in exec_src or "clarify" in reason:
        return "BINDING", "IR_INCOMPLETE", 0.75

    if "engine-fail" in reason or not sql:
        return "EXECUTION", "NO_SQL", 0.8

    if "PREDICATE_DROPPED" in root_causes:
        return "PREDICATE", "DROPPED", 0.8

    if "ENTITY_SELECTION_ERROR" in root_causes:
        return "ENTITY", "SELECTION", 0.75

    if "FOLLOWUP_CONTEXT_LOST" in root_causes:
        return "CONTEXT", "FOLLOWUP", 0.85

    if "RANGE_BOUND_DROPPED" in root_causes:
        return "PREDICATE", "RANGE_BOUND", 0.8

    if "SPATIAL_TARGET_DROPPED" in root_causes:
        return "SPATIAL", "TARGET_DROPPED", 0.8

    if exec_src in {"rag_sql"}:
        return "BINDING", "RAG_FALLBACK", 0.6

    return "UNKNOWN", "", 0.3


def classify_eval_status(
    case: dict[str, Any],
    *,
    policy_mismatch_ids: set[str] | None = None,
    data_quality_ids: set[str] | None = None,
) -> EvalStatus:
    """Classify evaluation status including Gold/Policy separation."""
    qid = str(case.get("id") or "")
    if case.get("pass"):
        return "PASS"
    if data_quality_ids and qid in data_quality_ids:
        return "DATA_QUALITY"
    if policy_mismatch_ids and qid in policy_mismatch_ids:
        return "POLICY_GOLD_MISMATCH"
    if "gold" in str(case.get("reason") or "").lower():
        return "GOLD_ERROR"
    if "timeout" in str(case.get("reason") or "").lower():
        return "ENGINE_ERROR"
    return "ENGINE_ERROR"


def build_fail_record(case: dict[str, Any], *, policy_mismatch_ids: set[str] | None = None) -> dict[str, Any]:
    """Build full FAIL record — requires execution_trace from Phase 2."""
    from txt2sql.evaluation.case_map import case_execution_trace

    error_class, error_subtype, confidence = classify_error_class(case)
    trace = case_execution_trace(case)
    return {
        "question_id": case.get("id"),
        "question": case.get("q"),
        "kind": case.get("kind"),
        "category": case.get("cat"),
        "expected": {"gold": case.get("gold")},
        "actual": {
            "answer": case.get("answer"),
            "rows_n": len(case.get("rows") or []),
        },
        "execution_source": case.get("execution_source") or case.get("route"),
        "execution_trace": trace,
        "contract": trace.get("query_understanding") or case.get("contract") or {},
        "query_ir": trace.get("query_ir") or case.get("query_ir") or {},
        "logical_plan": trace.get("logical_plan") or case.get("logical_plan") or {},
        "place_scope": trace.get("scope_binding") or case.get("place_scope") or {},
        "dataset_binding": trace.get("dataset_binding") or case.get("dataset_binding") or {},
        "field_binding": trace.get("field_binding") or case.get("field_binding") or {},
        "generated_sql": trace.get("generated_sql") or case.get("sql") or "",
        "expected_sql": trace.get("expected_sql") or case.get("expected_sql") or "",
        "error_stage": (trace.get("evaluation") or {}).get("error_stage")
        or ("evaluator" if case.get("sql") else "execution"),
        "error_class": error_class,
        "error_subtype": error_subtype,
        "eval_status": classify_eval_status(case, policy_mismatch_ids=policy_mismatch_ids),
        "confidence": confidence,
        "trace_completeness": trace.get("trace_completeness"),
        "notes": case.get("reason") or "",
        "root_causes": case.get("root_causes") or [],
    }


def summarize_failures(fail_records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate error_summary for fail taxonomy analysis."""
    from collections import Counter

    class_counts: Counter[str] = Counter()
    exec_counts: Counter[str] = Counter()
    eval_status_counts: Counter[str] = Counter()
    stage_counts: Counter[str] = Counter()
    diagnosis_source_counts: Counter[str] = Counter()
    by_class_ids: dict[str, list[str]] = {}

    trace_present = 0
    trace_diagnosed = 0

    for rec in fail_records:
        ec = rec.get("error_class") or "UNKNOWN"
        class_counts[ec] += 1
        exec_src = rec.get("execution_source") or "unknown"
        exec_counts[exec_src] += 1
        eval_status_counts[str(rec.get("eval_status") or "ENGINE_ERROR")] += 1
        stage_counts[str(rec.get("error_stage") or "unknown")] += 1
        by_class_ids.setdefault(ec, []).append(str(rec.get("question_id") or ""))

        trace = rec.get("execution_trace") or {}
        if trace:
            trace_present += 1
            tc = trace.get("trace_completeness") or {}
            if tc.get("query_ir") or tc.get("generated_sql") or (trace.get("evaluation") or {}).get("error_stage"):
                trace_diagnosed += 1
                diagnosis_source_counts["trace"] += 1
            else:
                diagnosis_source_counts["heuristic"] += 1
        else:
            diagnosis_source_counts["heuristic"] += 1

    total = len(fail_records) or 1
    summary_rows = []
    for ec, count in class_counts.most_common():
        summary_rows.append({
            "error_class": ec,
            "count": count,
            "share": round(100.0 * count / total, 1),
            "representative_ids": by_class_ids.get(ec, [])[:8],
            "execution_source_distribution": dict(exec_counts),
            "estimated_fix_leverage": "high" if count >= 15 else ("medium" if count >= 5 else "low"),
        })

    return {
        "total_failures": len(fail_records),
        "by_error_class": summary_rows,
        "by_eval_status": [
            {"eval_status": k, "count": v, "share": round(100.0 * v / total, 1)}
            for k, v in eval_status_counts.most_common()
        ],
        "by_error_stage": [
            {"error_stage": k, "count": v, "share": round(100.0 * v / total, 1)}
            for k, v in stage_counts.most_common()
        ],
        "trace_coverage": {
            "with_trace": trace_present,
            "trace_diagnosed": trace_diagnosed,
            "trace_rate": round(trace_present / total, 4),
            "diagnosis_source": dict(diagnosis_source_counts),
        },
        "execution_source_distribution": dict(exec_counts),
    }


def render_error_summary_md(summary: dict[str, Any]) -> str:
    lines = [
        "# MAIN FAIL Error Summary",
        "",
        f"Total failures: {summary.get('total_failures', 0)}",
        "",
    ]
    tc = summary.get("trace_coverage") or {}
    if tc:
        lines.extend([
            f"Trace coverage: {tc.get('with_trace', 0)}/{summary.get('total_failures', 0)} "
            f"({100 * float(tc.get('trace_rate', 0)):.1f}%), "
            f"trace-diagnosed={tc.get('trace_diagnosed', 0)}",
            "",
        ])
    lines.extend([
        "## By error_class",
        "",
        "| error_class | count | share | representative_ids | fix_leverage |",
        "|-------------|------:|------:|--------------------|--------------|",
    ])
    for row in summary.get("by_error_class") or []:
        ids = ", ".join(row.get("representative_ids") or [])[:60]
        lines.append(
            f"| {row['error_class']} | {row['count']} | {row['share']}% | {ids} | {row['estimated_fix_leverage']} |"
        )
    if summary.get("by_eval_status"):
        lines.extend([
            "",
            "## By eval_status (Phase 4)",
            "",
            "| eval_status | count | share |",
            "|-------------|------:|------:|",
        ])
        for row in summary["by_eval_status"]:
            lines.append(f"| {row['eval_status']} | {row['count']} | {row['share']}% |")
    if summary.get("by_error_stage"):
        lines.extend([
            "",
            "## By error_stage (trace)",
            "",
            "| error_stage | count | share |",
            "|-------------|------:|------:|",
        ])
        for row in summary["by_error_stage"]:
            lines.append(f"| {row['error_stage']} | {row['count']} | {row['share']}% |")
    lines.append("")
    return "\n".join(lines)
