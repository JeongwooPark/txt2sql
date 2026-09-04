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
    hints = ir.provenance.legacy_hints or {}
    source = ir.provenance.source_text or ""

    if ir.entity == "unknown":
        report.entity_binding = "FAIL"
        report.reasons.append("SEMANTIC_UNBOUND_ENTITY")

    # Dataset binding: entity must match declared hints / spatial targets
    if ir.entity == "basic_zone" and ir.task not in {"count", "list", "group", "aggregate", "rank"}:
        report.dataset_binding = "FAIL"
        report.reasons.append("SEMANTIC_DATASET_TASK_MISMATCH")
    if hints.get("basic_zone") and ir.entity not in {"basic_zone", "building", "admin_area"}:
        report.dataset_binding = "FAIL"
        report.reasons.append("SEMANTIC_BASIC_ZONE_ENTITY")
    if ir.spatial and ir.entity == "unknown":
        report.dataset_binding = "FAIL"
        report.reasons.append("SEMANTIC_UNBOUND_DATASET")

    # Scope binding for grouped / ranked queries
    if ir.task in {"group", "distribution", "rank"}:
        if not ir.dimensions and not (ir.scope and ir.scope.place):
            if ir.task != "rank" or not ir.ordering:
                report.scope_binding = "FAIL"
                report.reasons.append("SEMANTIC_INCOMPLETE_SCOPE")
        if ir.task in {"group", "distribution"} and not ir.dimensions:
            report.scope_binding = "FAIL"
            report.reasons.append("SEMANTIC_INCOMPLETE_DIMENSION")

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
            if not (ir.task == "group" and hints.get("wants_count")):
                report.aggregation_binding = "FAIL"
                report.reasons.append("SEMANTIC_INCOMPLETE_AGGREGATION")
        if ir.task in {"group", "distribution"} and not ir.aggregations:
            if hints.get("wants_count") or "몇" in source or "수" in source:
                pass  # adapter may inject count at compile time
            elif not ir.measures:
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

    if ir.task == "rank":
        if not ir.ordering and not ir.limit:
            report.output_binding = "FAIL"
            report.reasons.append("SEMANTIC_INCOMPLETE_OUTPUT")
        elif ir.limit is None and any(k in source for k in ("상위", "top", "가장")):
            report.output_binding = "FAIL"
            report.reasons.append("SEMANTIC_INCOMPLETE_LIMIT")

    if ir.task in {"list", "rank"} and not ir.outputs and not ir.measures:
        # list without projection is still often valid (default columns)
        pass

    for sp in ir.spatial:
        if not sp.relation:
            report.scope_binding = "FAIL"
            report.reasons.append("SEMANTIC_INCOMPLETE_SPATIAL")
            break
        if sp.relation in {"intersects", "within", "overlaps"} and not (
            sp.target_place or sp.target_entity
        ):
            report.scope_binding = "FAIL"
            report.reasons.append("SEMANTIC_UNBOUND_SPATIAL_TARGET")
            break

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
        report.scope_binding,
        report.predicate_binding,
        report.temporal_binding,
        report.aggregation_binding,
        report.output_binding,
        report.dataset_binding,
    ]
    if any(x == "FAIL" for x in node_fails) and report.status == "READY":
        report.status = "REPLAN"

    return report
