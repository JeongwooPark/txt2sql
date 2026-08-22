"""SemanticQueryPlan 의미 검증. 실행 여부는 score가 아니라 status가 결정한다."""

from __future__ import annotations

import re

import psycopg

from llm2sql.domain import AGE_HINTS, looks_like_age_question
from llm2sql.gazetteer import find_places, load_gazetteer
from llm2sql.semantic_plan.catalog import get_entity, get_field
from llm2sql.semantic_plan.models import (
    PlanValidationResult,
    SemanticQueryPlan,
    UnknownSemanticFieldError,
)

_MAX_FILTERS = 6
_MAX_SPATIAL = 2
_MAX_GROUP = 2
_MAX_AGG = 4
_MAX_ORDER = 3
_MAX_LIMIT = 1000
_V1_ENTITIES = frozenset({"building"})
_V1_SPATIAL = frozenset({"within", "intersects", "within_distance", "outside_distance"})


def validate_semantic_plan(
    plan: SemanticQueryPlan,
    question: str,
    *,
    conn: psycopg.Connection | None = None,
) -> PlanValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    score = 1.0
    status = "ready"

    if plan.unsupported_reason:
        return PlanValidationResult(
            status="fallback",
            score=0.0,
            errors=[plan.unsupported_reason],
            warnings=warnings,
            plan=plan,
        )
    if plan.requires_clarification:
        return PlanValidationResult(
            status="clarify",
            score=max(0.0, score - 0.3),
            errors=list(plan.ambiguities) or ["clarification required"],
            warnings=warnings,
            plan=plan,
        )

    if plan.entity not in _V1_ENTITIES:
        return _fallback(plan, f"unsupported entity: {plan.entity}", score - 0.4)

    try:
        get_entity(plan.entity)
    except UnknownSemanticFieldError as exc:
        return _fallback(plan, str(exc), score - 0.4)

    if looks_like_age_question(question) or any(h in question for h in AGE_HINTS):
        return _fallback(plan, "unsupported_coverage: building age / 사용승인", score - 0.5)

    if "면적" in question and not any(
        k in question for k in ("연면적", "건축면적", "건물면적", "대지면적")
    ):
        area_fields = [f.field for f in plan.filters if "area" in f.field]
        if not area_fields and not any("area" in s for s in plan.select):
            clarified = plan.model_copy(
                update={
                    "requires_clarification": True,
                    "ambiguities": list(plan.ambiguities)
                    + ["면적이 건축면적·연면적·대지면적 중 어떤 것인지 필요합니다"],
                }
            )
            return PlanValidationResult(
                status="clarify",
                score=score - 0.3,
                errors=list(clarified.ambiguities),
                warnings=warnings,
                plan=clarified,
            )

    used_fields = list(plan.select) + list(plan.group_by)
    used_fields.extend(item.field for item in plan.filters)
    used_fields.extend(item.field for item in plan.order_by)
    used_fields.extend(item.field for item in plan.aggregations if item.field)

    for key in used_fields:
        if not key:
            continue
        try:
            field = get_field(plan.entity, key)
        except UnknownSemanticFieldError:
            return _fallback(plan, f"unknown field: {key}", score - 0.4)

        if field.data_type == "geometry":
            return _fallback(plan, f"geometry field cannot be selected: {key}", score - 0.4)

    for spec in plan.filters:
        try:
            field = get_field(plan.entity, spec.field)
        except UnknownSemanticFieldError:
            return _fallback(plan, f"unknown field: {spec.field}", score - 0.4)
        if spec.operator not in field.allowed_ops:
            return _fallback(
                plan,
                f"unsupported operation: {spec.field} {spec.operator}",
                score - 0.4,
            )
        if spec.operator in {"gt", "gte", "lt", "lte", "between"} and field.data_type != "number":
            return _fallback(
                plan, f"numeric operator on text field: {spec.field}", score - 0.4
            )
        if spec.operator == "contains" and field.data_type != "text":
            return _fallback(
                plan, f"contains on non-text field: {spec.field}", score - 0.4
            )
        if spec.operator == "between" and spec.value2 is None:
            errors.append("between requires value2")
            status = "fallback"
            score -= 0.4

    if plan.scope and plan.scope.place and plan.scope.place.name.strip():
        place_status, place_error = _validate_place(plan.scope.place.name)
        if place_status == "clarify":
            clarified = plan.model_copy(
                update={
                    "requires_clarification": True,
                    "ambiguities": list(plan.ambiguities) + [place_error],
                }
            )
            return PlanValidationResult(
                status="clarify",
                score=score - 0.3,
                errors=[place_error],
                warnings=warnings,
                plan=clarified,
            )
        if place_status == "fallback":
            return _fallback(plan, place_error, score - 0.35)

    for rel in plan.spatial_relations:
        if rel.relation not in _V1_SPATIAL:
            return _fallback(plan, f"unsupported spatial relation: {rel.relation}", 0.4)
        if rel.relation in {"within_distance", "outside_distance"}:
            if rel.distance_m is None or rel.distance_m <= 0:
                return _fallback(plan, "distance_m must be > 0", score - 0.4)
        target = rel.target
        if target.longitude is not None or target.latitude is not None:
            lon = target.longitude
            lat = target.latitude
            if lon is None or lat is None:
                return _fallback(plan, "longitude/latitude both required", score - 0.4)
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                return _fallback(plan, "invalid lon/lat range", score - 0.4)
        elif rel.relation in {"within", "intersects", "within_distance", "outside_distance"}:
            if target.place is None or not (target.place.name or "").strip():
                return _fallback(plan, "spatial relation needs a place or lon/lat", score - 0.4)

    if len(plan.filters) > _MAX_FILTERS:
        return _fallback(plan, "too many filters", score - 0.2)
    if len(plan.spatial_relations) > _MAX_SPATIAL:
        return _fallback(plan, "too many spatial relations", score - 0.2)
    if len(plan.group_by) > _MAX_GROUP:
        return _fallback(plan, "too many group_by", score - 0.2)
    if len(plan.aggregations) > _MAX_AGG:
        return _fallback(plan, "too many aggregations", score - 0.2)
    if len(plan.order_by) > _MAX_ORDER:
        return _fallback(plan, "too many order_by", score - 0.2)
    if plan.limit is not None and plan.limit > _MAX_LIMIT:
        return _fallback(plan, "limit exceeds 1000", score - 0.2)

    tracked = [
        item
        for item in plan.assumptions
        if item not in {"heuristic_plan", "plan_followup_delta"}
    ]
    if tracked:
        score -= 0.1 * min(len(tracked), 3)
        warnings.extend(tracked)
    if plan.assumptions:
        warnings.extend(
            item for item in plan.assumptions if item not in tracked
        )
    if plan.ambiguities:
        score -= 0.3
        status = "clarify"

    if errors:
        status = "fallback"
    return PlanValidationResult(
        status=status,
        score=max(0.0, min(1.0, score)),
        errors=errors,
        warnings=warnings,
        plan=plan,
    )


def _fallback(plan: SemanticQueryPlan, reason: str, score: float) -> PlanValidationResult:
    return PlanValidationResult(
        status="fallback",
        score=max(0.0, score),
        errors=[reason],
        warnings=[],
        plan=plan,
    )


def _validate_place(name: str) -> tuple[str, str]:
    text = name.strip()
    if not text or re.search(r"[;\\]|--", text):
        return "fallback", f"unresolved place: {text}"
    gaz = load_gazetteer()
    if not (gaz.legal_dong or gaz.admin_dong or gaz.sigungu):
        return "ready", ""
    hits = find_places(text)
    if not hits:
        # 구 단위 등 질문 조각만 온 경우는 허용하고 compiler가 A4 LIKE로 처리
        if text.endswith(("구", "군")):
            return "ready", ""
        return "fallback", f"unresolved place: {text}"
    dongs = [h for h in hits if not h.is_sigungu]
    names = {h.name for h in dongs}
    if len(names) > 1:
        return "clarify", f"ambiguous place: {', '.join(sorted(names))}"
    return "ready", ""
