"""Adapters between QueryContract / SemanticQueryPlan and canonical QueryIR."""

from __future__ import annotations

from typing import Any

from txt2sql.query_ir.models import (
    AggregationIR,
    ComparisonIR,
    DimensionIR,
    EntityName,
    InteractionIR,
    MeasureIR,
    OrderingIR,
    PredicateIR,
    ProvenanceIR,
    ProvenanceSpan,
    QueryIR,
    ScopeIR,
    SpatialIR,
    TemporalIR,
    UnresolvedIR,
)
from txt2sql.query_ir.normalize import assert_no_physical_names, normalize_query_ir, normalize_task, result_shape_for_task


def _span_prov(span: Any) -> ProvenanceSpan:
    return ProvenanceSpan(
        text=getattr(span, "text", "") or "",
        start=getattr(span, "start", None),
        end=getattr(span, "end", None),
        kind=getattr(span, "kind", None),
        value=getattr(span, "value", None),
    )


def _entity_from_contract(contract: Any) -> EntityName:
    datasets = [str(x).lower() for x in (getattr(contract, "datasets", None) or [])]
    joined = " ".join(datasets)
    # datasets on contract may hold semantic hints historically; strip physical later
    if "basic" in joined or "bas" in joined:
        return "basic_zone"
    if "industrial" in joined:
        return "industrial_complex"
    if "admin" in joined:
        return "admin_area"
    return "building"


def contract_to_query_ir(contract: Any) -> QueryIR:
    places = list(getattr(contract, "places", None) or [])
    scope = None
    if places:
        p0 = places[0]
        scope = ScopeIR(
            place=str(getattr(p0, "value", None) or getattr(p0, "text", "") or None),
            place_kind=None,
            spatial_mode="auto",
        )

    predicates: list[PredicateIR] = []
    for span in getattr(contract, "ranges", None) or []:
        meta = getattr(span, "meta", None) or {}
        predicates.append(
            PredicateIR(
                field=meta.get("field") or getattr(span, "value", None),
                operator=meta.get("operator") or "between",
                value=meta.get("low", getattr(span, "value", None)),
                value2=meta.get("high"),
                unit=meta.get("unit"),
                provenance=_span_prov(span),
            )
        )
    for span in getattr(contract, "comparisons", None) or []:
        meta = getattr(span, "meta", None) or {}
        predicates.append(
            PredicateIR(
                field=meta.get("field") or meta.get("left"),
                operator=meta.get("operator") or "eq",
                value=meta.get("value"),
                value_field=meta.get("right_field") or meta.get("value_field"),
                provenance=_span_prov(span),
            )
        )
    for span in getattr(contract, "numbers", None) or []:
        meta = getattr(span, "meta", None) or {}
        if meta.get("field") or meta.get("operator"):
            predicates.append(
                PredicateIR(
                    field=meta.get("field"),
                    operator=meta.get("operator") or "gte",
                    value=getattr(span, "value", None),
                    unit=meta.get("unit"),
                    provenance=_span_prov(span),
                )
            )

    measures: list[MeasureIR] = []
    for span in getattr(contract, "metrics", None) or []:
        concept = str(getattr(span, "value", None) or getattr(span, "text", "") or "")
        if concept:
            measures.append(MeasureIR(concept=concept, provenance=_span_prov(span)))

    aggregations: list[AggregationIR] = []
    for req in getattr(contract, "aggregation_requests", None) or []:
        aggregations.append(
            AggregationIR(
                function=getattr(req, "function", "count"),
                field=getattr(req, "field", None),
                percentile=getattr(req, "percentile", None),
            )
        )
    for req in getattr(contract, "percentile_requests", None) or []:
        aggregations.append(
            AggregationIR(
                function="percentile",
                field=getattr(req, "field", None),
                percentile=getattr(req, "percentile", None),
            )
        )
    for req in getattr(contract, "ratios", None) or []:
        aggregations.append(
            AggregationIR(function="ratio", has_denominator=bool(getattr(req, "has_denominator", False)))
        )
    for req in getattr(contract, "derived_metrics", None) or []:
        aggregations.append(
            AggregationIR(
                function="derived",
                derived_kind=getattr(req, "kind", "divide"),
                left=getattr(req, "left", None),
                right=getattr(req, "right", None),
            )
        )

    dimensions = [
        DimensionIR(field=str(f), bins=bool(getattr(contract, "fixed_bins", False)))
        for f in (getattr(contract, "group_fields", None) or [])
        if f
    ]
    ordering = [
        OrderingIR(field=getattr(o, "field", None), direction=getattr(o, "direction", "desc") or "desc")
        for o in (getattr(contract, "order_requests", None) or [])
    ]
    unresolved = [
        UnresolvedIR(code="UNRESOLVED_SPAN", message=getattr(s, "text", ""), span=_span_prov(s))
        for s in (getattr(contract, "unresolved_spans", None) or [])
    ]

    temporal = TemporalIR() if getattr(contract, "wants_temporal", False) else None
    spatial: list[SpatialIR] = []
    if getattr(contract, "wants_spatial", False):
        spatial.append(SpatialIR(relation="within"))

    # Strip physical dataset names from contract.datasets — keep only as unresolved/provenance note
    legacy_datasets = list(getattr(contract, "datasets", None) or [])
    safe_hints: dict[str, Any] = {
        "wants_basement": bool(getattr(contract, "wants_basement", False)),
        "wants_count": bool(getattr(contract, "wants_count", False)),
        "coverage_ratio": getattr(contract, "coverage_ratio", None),
        "complexity": getattr(contract, "complexity", None),
        "operation": getattr(contract, "operation", None),
    }
    # Do not copy physical table names into IR; record count only
    if legacy_datasets:
        safe_hints["legacy_dataset_hint_count"] = len(legacy_datasets)

    task = normalize_task(getattr(contract, "query_kind", None) or getattr(contract, "operation", None))
    ir = QueryIR(
        task=task,
        entity=_entity_from_contract(contract),
        scope=scope,
        predicates=predicates,
        temporal=temporal,
        spatial=spatial,
        measures=measures,
        aggregations=aggregations,
        dimensions=dimensions,
        comparisons=[],
        ordering=ordering,
        limit=getattr(contract, "limit", None),
        outputs=list(getattr(contract, "output_fields", None) or []),
        result_shape=result_shape_for_task(task),  # type: ignore[arg-type]
        interaction=InteractionIR(),
        unresolved=unresolved,
        provenance=ProvenanceIR(
            source_text=getattr(contract, "question", "") or "",
            source="contract",
            legacy_hints=safe_hints,
        ),
    )
    return normalize_query_ir(ir)


def _predicate_from_filter(filt: Any) -> PredicateIR:
    return PredicateIR(
        field=getattr(filt, "field", None),
        operator=getattr(filt, "operator", None),
        value=getattr(filt, "value", None),
        value2=getattr(filt, "value2", None),
        unit=getattr(filt, "unit", None),
        value_field=getattr(filt, "value_field", None),
    )


def _predicate_from_spec(pred: Any) -> PredicateIR | None:
    if pred is None:
        return None
    op = getattr(pred, "op", None)
    if op in {"and", "or"}:
        children = [_predicate_from_spec(c) for c in (getattr(pred, "args", None) or [])]
        return PredicateIR(
            logical_group=op,
            children=[c for c in children if c is not None],
        )
    if op == "not":
        args = getattr(pred, "args", None) or []
        child = _predicate_from_spec(args[0]) if args else None
        if child is None:
            return PredicateIR(negated=True)
        child.negated = True
        return child
    left = getattr(pred, "left", None)
    right = getattr(pred, "right", None)
    return PredicateIR(
        field=getattr(left, "field", None) if left is not None else None,
        operator=getattr(pred, "operator", None),
        value=getattr(right, "value", None) if right is not None else None,
        value_field=getattr(right, "field", None) if right is not None else None,
        unit=getattr(right, "unit", None) if right is not None else None,
    )


def plan_to_query_ir(plan: Any) -> QueryIR:
    scope = None
    plan_scope = getattr(plan, "scope", None)
    if plan_scope is not None:
        place = getattr(plan_scope, "place", None)
        scope = ScopeIR(
            place=getattr(place, "name", None) if place is not None else None,
            place_kind=getattr(place, "kind", None) if place is not None else None,
            spatial_mode=getattr(plan_scope, "spatial_mode", "auto") or "auto",
        )

    predicates = [_predicate_from_filter(f) for f in (getattr(plan, "filters", None) or [])]
    root_pred = _predicate_from_spec(getattr(plan, "predicate", None))
    if root_pred is not None:
        predicates.append(root_pred)

    aggregations = [
        AggregationIR(
            function=getattr(a, "function", "count"),
            field=getattr(a, "field", None),
            alias=getattr(a, "alias", None),
            percentile=getattr(a, "percentile", None),
        )
        for a in (getattr(plan, "aggregations", None) or [])
    ]
    for ratio in getattr(plan, "ratios", None) or []:
        aggregations.append(
            AggregationIR(
                function="ratio",
                alias=getattr(ratio, "alias", "ratio_pct"),
                has_denominator=getattr(ratio, "denominator_predicate", None) is not None,
            )
        )

    measures = [
        MeasureIR(concept=str(p.field), alias=getattr(p, "alias", None))
        for p in (getattr(plan, "projections", None) or [])
        if getattr(p, "field", None)
    ]
    for field in getattr(plan, "select", None) or []:
        if field and all(m.concept != field for m in measures):
            measures.append(MeasureIR(concept=str(field)))

    dimensions = [DimensionIR(field=str(g)) for g in (getattr(plan, "group_by", None) or [])]
    ordering = [
        OrderingIR(field=getattr(o, "field", None), direction=getattr(o, "direction", "asc") or "asc")
        for o in (getattr(plan, "order_by", None) or [])
    ]
    spatial = [
        SpatialIR(
            relation=getattr(s, "relation", None),
            target_place=getattr(getattr(getattr(s, "target", None), "place", None), "name", None),
            target_entity=getattr(getattr(s, "target", None), "entity", None),
            distance_m=getattr(s, "distance_m", None),
            min_ratio=getattr(s, "min_ratio", None),
            longitude=getattr(getattr(s, "target", None), "longitude", None),
            latitude=getattr(getattr(s, "target", None), "latitude", None),
        )
        for s in (getattr(plan, "spatial_relations", None) or [])
    ]

    unresolved: list[UnresolvedIR] = []
    if getattr(plan, "requires_clarification", False):
        unresolved.append(UnresolvedIR(code="CLARIFY_REQUIRED", message="requires_clarification"))
    for amb in getattr(plan, "ambiguities", None) or []:
        unresolved.append(UnresolvedIR(code="AMBIGUITY", message=str(amb)))
    if getattr(plan, "unsupported_reason", None):
        unresolved.append(
            UnresolvedIR(code="UNSUPPORTED", message=str(getattr(plan, "unsupported_reason")))
        )

    entity = getattr(plan, "entity", "building") or "building"
    if entity not in {"building", "admin_area", "basic_zone", "industrial_complex"}:
        entity = "unknown"
    task = normalize_task(getattr(plan, "query_kind", None))
    ir = QueryIR(
        task=task,
        entity=entity,  # type: ignore[arg-type]
        scope=scope,
        predicates=predicates,
        temporal=None,
        spatial=spatial,
        measures=measures,
        aggregations=aggregations,
        dimensions=dimensions,
        comparisons=[],
        ordering=ordering,
        limit=getattr(plan, "limit", None),
        outputs=list(getattr(plan, "select", None) or []),
        result_shape=result_shape_for_task(task),  # type: ignore[arg-type]
        interaction=InteractionIR(),
        unresolved=unresolved,
        provenance=ProvenanceIR(
            source="semantic_plan",
            confidence=getattr(plan, "model_confidence", None),
            notes=list(getattr(plan, "assumptions", None) or []),
        ),
    )
    return normalize_query_ir(ir)


def query_ir_to_semantic_plan(ir: QueryIR) -> Any:
    """Best-effort reverse adapter to legacy SemanticQueryPlan."""
    from txt2sql.semantic_plan.models import (
        AggregationSpec,
        FilterSpec,
        OrderSpec,
        PlaceSpec,
        ProjectionSpec,
        ScopeSpec,
        SemanticQueryPlan,
        SpatialRelationSpec,
        SpatialTargetSpec,
    )

    assert_no_physical_names(ir.model_dump())

    kind_map = {
        "count": "count",
        "list": "list",
        "rank": "rank",
        "aggregate": "aggregate",
        "group": "distribution",
        "distribution": "distribution",
        "ratio": "aggregate",
        "compare": "aggregate",
        "meta": "count",
        "unknown": "count",
    }
    query_kind = kind_map.get(ir.task, "count")
    entity = ir.entity if ir.entity != "unknown" else "building"

    scope = None
    if ir.scope and ir.scope.place:
        scope = ScopeSpec(
            place=PlaceSpec(name=ir.scope.place, kind=(ir.scope.place_kind or "unknown")),  # type: ignore[arg-type]
            spatial_mode=ir.scope.spatial_mode,
        )

    filters: list[FilterSpec] = []
    for pred in ir.predicates:
        if pred.children or pred.logical_group:
            continue
        if not pred.field or not pred.operator:
            continue
        filters.append(
            FilterSpec(
                field=pred.field,
                operator=pred.operator,  # type: ignore[arg-type]
                value=pred.value,
                value2=pred.value2,
                unit=pred.unit,
                value_field=pred.value_field,
            )
        )

    aggregations = [
        AggregationSpec(
            function=a.function if a.function not in {"ratio", "derived"} else "count",  # type: ignore[arg-type]
            field=a.field,
            alias=a.alias,
            percentile=a.percentile,
        )
        for a in ir.aggregations
        if a.function not in {"ratio", "derived"}
    ]
    projections = [ProjectionSpec(field=m.concept, alias=m.alias) for m in ir.measures]
    order_by = [
        OrderSpec(field=o.field or "count", direction=o.direction) for o in ir.ordering if o.field or True
    ]
    spatial_relations = [
        SpatialRelationSpec(
            relation=s.relation or "within",  # type: ignore[arg-type]
            target=SpatialTargetSpec(
                entity=s.target_entity if s.target_entity in {"building", "admin_area", "basic_zone", "industrial_complex"} else None,  # type: ignore[arg-type]
                place=PlaceSpec(name=s.target_place) if s.target_place else None,
                longitude=s.longitude,
                latitude=s.latitude,
            ),
            distance_m=s.distance_m,
            min_ratio=s.min_ratio,
        )
        for s in ir.spatial
        if s.relation
    ]

    return SemanticQueryPlan(
        query_kind=query_kind,  # type: ignore[arg-type]
        entity=entity,  # type: ignore[arg-type]
        scope=scope,
        filters=filters,
        select=list(ir.outputs) or [m.concept for m in ir.measures],
        projections=projections,
        aggregations=aggregations,
        group_by=[d.field for d in ir.dimensions],
        order_by=[o for o in order_by if o.field],
        limit=ir.limit,
        spatial_relations=spatial_relations,
        requires_clarification=any(u.code.startswith("CLARIFY") for u in ir.unresolved),
        ambiguities=[u.message for u in ir.unresolved if u.code == "AMBIGUITY"],
        unsupported_reason=next((u.message for u in ir.unresolved if u.code == "UNSUPPORTED"), None),
        model_confidence=ir.provenance.confidence or 0.5,
        assumptions=list(ir.provenance.notes),
    )
