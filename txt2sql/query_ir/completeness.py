"""QueryIR semantic completeness (node-level, not score threshold)."""

from __future__ import annotations

from dataclasses import dataclass, field

from txt2sql.query_ir.models import QueryIR


@dataclass
class CompletenessReport:
    entity_binding: str = "PASS"
    scope_binding: str = "PASS"
    predicate_binding: str = "PASS"
    temporal_binding: str = "PASS"
    aggregation_binding: str = "PASS"
    output_binding: str = "PASS"
    dataset_binding: str = "PASS"
    status: str = "READY"  # READY | REPLAN | CLARIFY | UNSUPPORTED
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "entity_binding": self.entity_binding,
            "scope_binding": self.scope_binding,
            "predicate_binding": self.predicate_binding,
            "temporal_binding": self.temporal_binding,
            "aggregation_binding": self.aggregation_binding,
            "output_binding": self.output_binding,
            "dataset_binding": self.dataset_binding,
            "status": self.status,
            "reasons": list(self.reasons),
        }


def assess_completeness(ir: QueryIR) -> CompletenessReport:
    report = CompletenessReport()

    if ir.entity == "unknown":
        report.entity_binding = "FAIL"
        report.reasons.append("SEMANTIC_UNBOUND_ENTITY")

    for pred in ir.predicates:
        if pred.children:
            continue
        if pred.field is None and pred.value_field is None:
            report.predicate_binding = "FAIL"
            report.reasons.append("SEMANTIC_UNBOUND_PREDICATE")
            break
        if pred.operator is None and not pred.children:
            report.predicate_binding = "FAIL"
            report.reasons.append("SEMANTIC_UNBOUND_PREDICATE_OP")
            break

    if ir.temporal is not None and ir.temporal.field is None and ir.temporal.age_years is None:
        report.temporal_binding = "FAIL"
        report.reasons.append("SEMANTIC_UNBOUND_TEMPORAL")

    if ir.task in {"aggregate", "group", "distribution", "ratio", "count"}:
        if ir.task != "count" and not ir.aggregations and not ir.measures:
            report.aggregation_binding = "FAIL"
            report.reasons.append("SEMANTIC_INCOMPLETE_AGGREGATION")
        for agg in ir.aggregations:
            if agg.function in {"avg", "sum", "min", "max", "median", "stddev", "percentile"}:
                if agg.field is None and agg.left is None:
                    report.aggregation_binding = "FAIL"
                    report.reasons.append("SEMANTIC_UNBOUND_METRIC")
                    break
            if agg.function == "count" and agg.distinct and agg.grain is None:
                report.aggregation_binding = "FAIL"
                report.reasons.append("SEMANTIC_INCOMPLETE_GRAIN")
                break

    if ir.task in {"list", "rank"} and not ir.outputs and not ir.measures:
        # list without projection is still often valid (default columns)
        pass

    for item in ir.unresolved:
        code = item.code.upper()
        if "CLARIFY" in code or "AMBIG" in code:
            report.status = "CLARIFY"
            report.reasons.append(item.code)
        elif "UNSUPPORTED" in code:
            report.status = "UNSUPPORTED"
            report.reasons.append(item.code)
        else:
            if report.status == "READY":
                report.status = "REPLAN"
            report.reasons.append(item.code)

    node_fails = [
        report.entity_binding,
        report.predicate_binding,
        report.temporal_binding,
        report.aggregation_binding,
        report.output_binding,
        report.dataset_binding,
    ]
    if any(x == "FAIL" for x in node_fails) and report.status == "READY":
        report.status = "REPLAN"

    return report
