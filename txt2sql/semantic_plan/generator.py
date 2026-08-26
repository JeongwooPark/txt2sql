"""자연어 → SemanticQueryPlan.

LLM structured JSON을 우선 사용하고, 실패 시 단순 건물 질의는
기존 domain/units 힌트로 heuristic plan을 만든다.
"""

from __future__ import annotations

import json
import re
from typing import Any

import psycopg

from txt2sql.config import Settings
from txt2sql.domain import (
    LENGTH_DIST_PATTERN,
    d198_gu_for_dong,
    d198_table_for_gu,
    extract_gu,
    extract_industrial_name,
    extract_industrial_names,
    extract_place,
    extract_special_land,
    extract_structure,
    extract_structures,
    extract_usage,
    extract_usages,
    extract_detail_usages,
    extract_usage_classes,
    is_busan_wide,
    is_vague_age_threshold,
    looks_like_age_question,
)
from txt2sql.llm import chat
from txt2sql.query_understanding.contract import extract_contract
from txt2sql.query_understanding.gate import accept_heuristic_plan
from txt2sql.query_understanding.operators import AGG_MAP
from txt2sql.query_understanding.temporal import parse_temporal_filters
from txt2sql.semantic_plan.migrate import filter_to_predicate, migrate_plan_v11
from txt2sql.semantic_plan.predicate_utils import effective_predicate, has_op
from txt2sql.semantic_plan.models import (
    AggregationSpec,
    ExpressionSpec,
    FilterSpec,
    OperandSpec,
    OrderSpec,
    PlaceSpec,
    PredicateSpec,
    RatioSpec,
    ScopeSpec,
    SemanticPlanGenerationError,
    SemanticQueryPlan,
    SpatialRelationSpec,
    SpatialTargetSpec,
)
from txt2sql.semantic_plan.prompts import build_messages
from txt2sql.session import SessionContext
from txt2sql.units import UNIT_TOKEN, convert_for_schema

_PHYSICAL_LEAK = re.compile(
    r"\b(AL_D\d+|BND_ADM|TL_KODIS|ST_[A-Za-z]+|SELECT|INSERT|UPDATE|DELETE|DROP)\b"
    r'|(?<![A-Za-z])A\d{1,2}(?![A-Za-z0-9])',
    re.I,
)
_REL = {
    "이상": "gte",
    "이하": "lte",
    "초과": "gt",
    "미만": "lt",
    "넘는": "gt",
}
_UNSUPPORTED_HINTS = (
    "시가총액",
    "시세",
    "매매가",
    "공시지가",
    "인구",
    "세대수",
    "지하철",
    "버스",
    "주차",
    "좋은",
    "멋진",
    "예쁜",
    "살기",
)


def extract_plan_hints(question: str) -> dict[str, Any]:
    """LLM 이전 deterministic hint. Plan을 강제 덮어쓰지 않는다."""
    q = question.strip()
    gu = extract_gu(q)
    place = extract_place(q)
    usage = extract_usage(q)
    if "세부용도" in q:
        usage = None
    structure = extract_structure(q)
    numerics: list[dict[str, Any]] = []
    for field, schema_unit, pattern in (
        ("height_m", "m", rf"높이[가이]?\s*(\d+(?:\.\d+)?)\s*{UNIT_TOKEN}\s*[을를]?\s*(이상|이하|초과|미만|넘는)"),
        (
            "gross_floor_area_m2",
            "㎡",
            rf"연면적[이가]?\s*(\d+(?:\.\d+)?)\s*{UNIT_TOKEN}\s*[을를]?\s*(이상|이하|초과|미만|넘는)",
        ),
        (
            "building_area_m2",
            "㎡",
            rf"(?:건축면적|건물면적)[이가]?\s*(\d+(?:\.\d+)?)\s*{UNIT_TOKEN}\s*[을를]?\s*(이상|이하|초과|미만|넘는)",
        ),
        (
            "site_area_m2",
            "㎡",
            rf"대지면적[이가]?\s*(\d+(?:\.\d+)?)\s*{UNIT_TOKEN}\s*[을를]?\s*(이상|이하|초과|미만|넘는)",
        ),
        (
            "ground_floors",
            "층",
            r"(?:지상\s*층?|층수|지상층)[이가]?\s*(\d+)\s*층?\s*[을를]?\s*(이상|이하|초과|미만|넘는)",
        ),
        (
            "basement_floors",
            "층",
            r"지하\s*(?:층수?)?[이가]?\s*(\d+)\s*층?\s*[을를]?\s*(이상|이하|초과|미만|넘는)",
        ),
        (
            "building_coverage_ratio",
            "%",
            rf"건폐율[이가]?\s*(\d+(?:\.\d+)?)\s*%?\s*[을를]?\s*(이상|이하|초과|미만|넘는)",
        ),
        (
            "floor_area_ratio",
            "%",
            rf"용적[률율][이가]?\s*(\d+(?:\.\d+)?)\s*%?\s*[을를]?\s*(이상|이하|초과|미만|넘는)",
        ),
    ):
        match = re.search(pattern, q)
        if not match:
            continue
        unit = match.group(2) if match.lastindex and match.lastindex >= 2 else None
        if field == "ground_floors" or field == "basement_floors":
            unit = "층"
            rel = match.group(2)
        elif field in {"building_coverage_ratio", "floor_area_ratio"}:
            rel = match.group(2)
            numerics.append(
                {
                    "field": field,
                    "operator": _REL.get(rel, "gte"),
                    "value": float(match.group(1)),
                    "unit": "percent",
                }
            )
            continue
        else:
            rel = match.group(3)
        converted = convert_for_schema(match.group(1), unit, schema_unit)
        if converted is None:
            continue
        numerics.append(
            {
                "field": field,
                "operator": _REL.get(rel, "gte"),
                "value": converted.canonical,
                "unit": "m2" if schema_unit in {"㎡", "m2"} else ("m" if schema_unit == "m" else "floor"),
            }
            )
    range_nums = _extract_range_numerics(q)
    if range_nums:
        ranged_fields = {item["field"] for item in range_nums}
        numerics = [item for item in numerics if item["field"] not in ranged_fields]
        numerics.extend(range_nums)
    if not any(item["field"] == "ground_floors" for item in numerics):
        floor_m = re.search(r"(\d+)\s*층\s*[을를]?\s*(이상|이하|초과|미만|넘는)", q)
        if floor_m and "지하" not in q[max(0, floor_m.start() - 4) : floor_m.start()]:
            numerics.append(
                {
                    "field": "ground_floors",
                    "operator": _REL.get(floor_m.group(2), "gte"),
                    "value": int(floor_m.group(1)),
                    "unit": "floor",
                }
            )
    if not numerics:
        bare = re.search(
            rf"(\d+(?:\.\d+)?)\s*(킬로미터|㎞|km|미터|m)\s*[을를]?\s*(이상|이하|초과|미만|넘는)",
            q,
        )
        if bare:
            converted = convert_for_schema(bare.group(1), bare.group(2), "m")
            if converted is not None:
                numerics.append(
                    {
                        "field": "height_m",
                        "operator": _REL.get(bare.group(3), "gte"),
                        "value": converted.canonical,
                        "unit": "m",
                    }
                )
    if re.search(r"용적[률율][이가]?\s*0보다 크", q):
        numerics.append(
            {
                "field": "floor_area_ratio",
                "operator": "gt",
                "value": 0.0,
                "unit": "percent",
            }
        )
    if "기초구역" in q:
        bas = re.search(
            r"(?:면적|BAS_AR)\s*(?:\(BAS_AR\))?\s*(\d+(?:\.\d+)?)\s*(?:㎡|m2|㎢)?"
            r"\s*(이상|이하|초과|미만)",
            q,
            re.I,
        )
        if bas:
            numerics.append(
                {
                    "field": "area_m2",
                    "operator": _REL.get(bas.group(2), "gte"),
                    "value": float(bas.group(1)),
                }
            )
    far_lt = re.search(
        r"(\d+(?:\.\d+)?)\s*%\s*(미만|이하)",
        q,
    )
    if (
        far_lt
        and "용적" in q
        and not any(
            item["field"] == "floor_area_ratio" and item["operator"] in {"lt", "lte"}
            for item in numerics
        )
    ):
        numerics.append(
            {
                "field": "floor_area_ratio",
                "operator": _REL.get(far_lt.group(2), "lt"),
                "value": float(far_lt.group(1)),
                "unit": "percent",
            }
        )
    kind = "unknown"
    if is_busan_wide(q) and not gu and not (place and place.endswith(("구", "군", "동"))):
        place = place or "부산광역시"
        kind = "sido"
    elif gu and (place == gu or not place):
        kind = "gu"
    elif place:
        kind = "legal_dong" if place.endswith("동") else "unknown"
    industrial_names = extract_industrial_names(q)
    industrial_name = industrial_names[0] if industrial_names else extract_industrial_name(q)
    structures = extract_structures(q)
    land = extract_special_land(q)
    extra_filters: list[dict[str, Any]] = []
    if any(k in q for k in ("위반건축", "위반 건축", "위반건물")) or (
        "위반" in q and "건축" in q
    ):
        violate_op = "neq" if _term_is_negated(q, "위반건축물") or _term_is_negated(
            q, "위반건축"
        ) else "eq"
        extra_filters.append(
            {"field": "violation_status", "operator": violate_op, "value": "Y"}
        )
    if land:
        land_label, land_value = land[0], "산" if land[0] == "산지" else (
            "일반" if land[0] == "일반지번" else None
        )
        if land_value:
            land_op = "neq" if _term_is_negated(q, land_label) else "eq"
            extra_filters.append(
                {"field": "special_land", "operator": land_op, "value": land_value}
            )
    dong_quoted = re.search(
        r"건물동명[이은는가에을를]?\s*[''\"]([^'\"]+)[''\"]",
        q,
    )
    if dong_quoted:
        extra_filters.append(
            {
                "field": "building_dong_name",
                "operator": "contains",
                "value": dong_quoted.group(1).strip(),
            }
        )
    elif "건물동명" in q:
        extra_filters.append(
            {"field": "building_dong_name", "operator": "is_not_null", "value": None}
        )
    if re.search(r"지하층이\s*있", q) or (
        "지하층" in q and "있고" in q and "합계" not in q
    ):
        extra_filters.append(
            {"field": "basement_floors", "operator": "gt", "value": 0}
        )
    if "일반건축물대장" in q:
        extra_filters.append(
            {"field": "ledger_kind", "operator": "eq", "value": "일반건축물대장"}
        )
    if any(k in q for k in ("기록된", "모두 있는")):
        if "건폐율" in q:
            extra_filters.append(
                {"field": "building_coverage_ratio", "operator": "gt", "value": 0}
            )
        if "용적" in q:
            extra_filters.append(
                {"field": "floor_area_ratio", "operator": "gt", "value": 0}
            )
    return {
        "place": place or gu,
        "place_kind": kind if (place or gu) else None,
        "usage": usage,
        "usages": [] if "세부용도" in q else extract_usages(q),
        "detail_usages": extract_detail_usages(q),
        "usage_classes": extract_usage_classes(q),
        "structure": structure[0] if structure else None,
        "structures": [item[0] for item in structures],
        "numeric_expressions": numerics,
        "age_question": looks_like_age_question(q),
        "distance_m": _extract_distance_m(q),
        "distance_outside": any(k in q for k in ("경계 밖", "바깥", "외부")),
        "boundary": any(k in q for k in ("안에", "내부", "경계 안", "경계안", "안쪽")),
        "industrial_name": industrial_name,
        "industrial_names": industrial_names,
        "extra_filters": extra_filters,
        "ratio": any(k in q for k in ("비율", "퍼센트", "몇%", "%씩", "몇 프로")),
        "basic_zone": "기초구역" in q,
    }


def parse_plan_json(text: str) -> SemanticQueryPlan:
    payload = _extract_json_object(text)
    if _PHYSICAL_LEAK.search(payload):
        raise SemanticPlanGenerationError("physical identifier or SQL leaked into plan")
    try:
        plan = SemanticQueryPlan.model_validate_json(payload)
    except Exception as exc:
        raise SemanticPlanGenerationError(f"invalid plan json: {exc}") from exc
    return migrate_plan_v11(plan)


def _catalog_owns_d060_only(question: str) -> bool:
    """산업단지 전용 속성(시군구코드 등)은 D060 카탈로그에 맡긴다."""
    if any(k in question for k in ("건물", "공장", "창고", "채수", "교차")):
        return False
    from txt2sql.catalog_attrs import match_catalog

    parsed = match_catalog(question)
    return bool(
        parsed is not None
        and parsed.dataset.key == "d060"
        and (parsed.filters or parsed.rank)
    )


def try_heuristic_plan(
    question: str,
    hints: dict[str, Any] | None = None,
    *,
    reference_date: str | None = None,
    contract=None,
) -> SemanticQueryPlan | None:
    """Router가 놓친 단순 건물 질의를 LLM 없이 Plan으로 옮긴다."""
    bound_contract = contract
    q = question.strip()
    if not q:
        return None
    if any(k in q for k in _UNSUPPORTED_HINTS):
        return None
    hints = hints or extract_plan_hints(q)
    temporal_filters = parse_temporal_filters(q, reference_date=reference_date)
    if is_vague_age_threshold(q) and not temporal_filters:
        scope = None
        place_name = hints.get("place")
        if place_name:
            kind = hints.get("place_kind") or "unknown"
            if kind not in {"sido", "gu", "legal_dong", "admin_dong", "basic_zone", "unknown"}:
                kind = "unknown"
            scope = ScopeSpec(place=PlaceSpec(name=place_name, kind=kind), spatial_mode="auto")
        return SemanticQueryPlan(
            query_kind="count",
            entity="building",
            scope=scope,
            requires_clarification=True,
            ambiguities=["오래된/신규의 기준 연수가 필요합니다"],
        )
    if re.search(r"[가-힣]{1,12}역", q) and _extract_distance_m(q) is not None:
        return SemanticQueryPlan(
            query_kind="list",
            entity="building",
            requires_clarification=True,
            ambiguities=[
                "역·POI 좌표는 지원하지 않습니다. 동·구 경계 기준으로 거리를 물어 주세요."
            ],
        )
    if (
        "면적" in q
        and "기초구역" not in q
        and not any(k in q for k in ("연면적", "건축면적", "건물면적", "대지면적"))
        and not any(
            item.get("field") in {
                "gross_floor_area_m2",
                "building_area_m2",
                "site_area_m2",
            }
            for item in (hints.get("numeric_expressions") or [])
        )
    ):
        return SemanticQueryPlan(
            query_kind="list",
            entity="building",
            requires_clarification=True,
            ambiguities=["면적이 건축면적·연면적·대지면적 중 어떤 것인지 필요합니다"],
        )
    if ("허가일" in q or "허가일자" in q) and "사용승인" not in q:
        gu_name = hints.get("place") if hints.get("place_kind") == "gu" else extract_gu(q)
        if gu_name and d198_table_for_gu(gu_name) is None and not is_busan_wide(q):
            return SemanticQueryPlan(
                query_kind="count",
                entity="building",
                unsupported_reason="허가일은 동래·금정 용도별건물(D198)에서만 조회할 수 있습니다",
            )
    hints = hints or extract_plan_hints(q)
    bound = bound_contract if bound_contract is not None else extract_contract(q)
    if (
        not hints.get("place")
        and not hints.get("usage")
        and not hints.get("detail_usages")
        and not hints.get("usage_classes")
        and not hints.get("numeric_expressions")
        and not temporal_filters
        and not hints.get("industrial_name")
        and not hints.get("industrial_names")
        and not hints.get("basic_zone")
        and "산업단지" not in q
        and "사업지구" not in q
        and not hints.get("ratio")
        and not hints.get("extra_filters")
        and not bound.percentile_requests
        and not bound.derived_metrics
        and not bound.ratios
        and not bound.group_fields
    ):
        return None
    if _catalog_owns_d060_only(q):
        return None
    if not any(
        k in q
        for k in (
            "건물",
            "아파트",
            "주택",
            "건축물",
            "공동주택",
            "창고",
            "학교",
            "공장",
            "용도별",
            "높이",
            "연면적",
            "건축면적",
            "사용승인",
            "년대",
            "허가",
            "산업단지",
            "기초구역",
            "사업지구",
            "채수",
            "비율",
            "산지",
            "구조별",
            "법정동별",
        )
    ):
        if (
            not hints.get("numeric_expressions")
            and not hints.get("usage")
            and not hints.get("detail_usages")
            and not hints.get("usage_classes")
            and not hints.get("distance_m")
            and not hints.get("ratio")
            and not hints.get("extra_filters")
            and not temporal_filters
        ):
            return None

    query_kind = _guess_kind(q)
    filters: list[FilterSpec] = []
    predicate: PredicateSpec | None = None
    or_tokens = ("또는", "혹은", "이거나", "둘 중 하나")
    not_tokens = ("제외", "아닌", "빼고", "뺀", "이외")
    usages = list(hints.get("usages") or [])
    structures = list(hints.get("structures") or [])
    detail_usages = list(hints.get("detail_usages") or [])
    usage_classes = list(hints.get("usage_classes") or [])
    # D198 커버 구/동이면 세부용도(아파트 등)를 우선하고 주요용도 오맵을 제거
    _gu_for_detail = extract_gu(q)
    if _gu_for_detail is None and hints.get("place_kind") == "legal_dong":
        _gu_for_detail = d198_gu_for_dong(str(hints.get("place") or ""))
    if (
        detail_usages
        and _gu_for_detail
        and d198_table_for_gu(str(_gu_for_detail)) is not None
    ):
        usages = []
        if hints.get("usage") and hints["usage"] not in detail_usages:
            hints = {**hints, "usage": None}
    elif detail_usages and not (
        _gu_for_detail and d198_table_for_gu(str(_gu_for_detail)) is not None
    ):
        # 비커버 지역: D010 주요용도만 사용 (아파트→공동주택)
        detail_usages = []
    dual_subset_usage = _dual_count_subset_usage(q, usages)
    if dual_subset_usage:
        usages = []
    neg_usages = [u for u in usages if _term_is_negated(q, u)]
    pos_usages = [u for u in usages if u not in neg_usages]
    middot_usage_or = bool(
        re.search(r"(공장|창고시설|창고)[·･、,/]", q)
    ) and len(pos_usages) >= 2
    if any(k in q for k in or_tokens) and len(usages) >= 2 and not neg_usages:
        predicate = PredicateSpec(
            op="or",
            args=[_usage_eq(value) for value in usages],
        )
    elif middot_usage_or and not any(k in q for k in not_tokens):
        predicate = PredicateSpec(
            op="or",
            args=[_usage_eq(value) for value in pos_usages],
        )
    elif any(k in q for k in or_tokens) and len(detail_usages) >= 2:
        predicate = PredicateSpec(
            op="or",
            args=[_field_eq("detail_usage", value) for value in detail_usages],
        )
    elif any(k in q for k in or_tokens) and len(usage_classes) >= 2:
        predicate = PredicateSpec(
            op="or",
            args=[_field_eq("usage_class", value) for value in usage_classes],
        )
    elif any(k in q for k in or_tokens) and len(structures) >= 2:
        predicate = PredicateSpec(
            op="or",
            args=[_structure_contains(value) for value in structures],
        )
    elif any(k in q for k in not_tokens) and len(neg_usages) >= 2:
        predicate = PredicateSpec(
            op="not",
            args=[
                PredicateSpec(
                    op="or",
                    args=[_usage_eq(value) for value in neg_usages],
                )
            ],
        )
    elif any(k in q for k in not_tokens) and len(usages) >= 2 and not pos_usages:
        predicate = PredicateSpec(
            op="not",
            args=[
                PredicateSpec(
                    op="or",
                    args=[_usage_eq(value) for value in usages],
                )
            ],
        )
    elif (
        any(k in q for k in ("제외", "빼고", "뺀", "이외"))
        and len(usages) >= 2
        and not any(k in q for k in or_tokens)
        and not neg_usages
    ):
        predicate = PredicateSpec(
            op="not",
            args=[
                PredicateSpec(
                    op="or",
                    args=[_usage_eq(value) for value in usages],
                )
            ],
        )
    elif neg_usages:
        usage_not = neg_usages[0]
        filters.append(FilterSpec(field="usage", operator="neq", value=usage_not))
        predicate = PredicateSpec(op="not", args=[_usage_eq(usage_not)])
        if pos_usages:
            predicate = _and_pred(
                PredicateSpec(
                    op="or",
                    args=[_usage_eq(v) for v in pos_usages],
                )
                if len(pos_usages) >= 2
                else _usage_eq(pos_usages[0]),
                predicate,
            )
            if len(pos_usages) == 1:
                filters.append(
                    FilterSpec(field="usage", operator="eq", value=pos_usages[0])
                )
    elif hints.get("usage") and not dual_subset_usage:
        filters.append(FilterSpec(field="usage", operator="eq", value=hints["usage"]))
    if (
        predicate is None
        and not any(k in q for k in or_tokens)
        and len(detail_usages) == 1
    ):
        filters.append(
            FilterSpec(field="detail_usage", operator="eq", value=detail_usages[0])
        )
    if (
        predicate is None
        and not any(k in q for k in or_tokens)
        and len(usage_classes) == 1
    ):
        filters.append(
            FilterSpec(field="usage_class", operator="eq", value=usage_classes[0])
        )
    compare = _extract_field_compare(q)
    if compare is not None:
        filters.append(compare)
    neg_structures = [s for s in structures if _term_is_negated(q, s)]
    if hints.get("structure") and not (
        predicate is not None and predicate.op == "or" and len(structures) >= 2
        and not neg_structures
    ):
        if len(neg_structures) >= 2:
            predicate = _and_pred(
                predicate,
                PredicateSpec(
                    op="not",
                    args=[
                        PredicateSpec(
                            op="or",
                            args=[_structure_contains(s) for s in neg_structures],
                        )
                    ],
                ),
            )
        elif neg_structures or _term_is_negated(q, str(hints.get("structure") or "")):
            neg_val = (neg_structures[0] if neg_structures else hints["structure"])
            filters.append(
                FilterSpec(field="structure", operator="neq", value=neg_val)
            )
            predicate = _and_pred(
                predicate,
                PredicateSpec(op="not", args=[_structure_contains(neg_val)]),
            )
        else:
            filters.append(
                FilterSpec(field="structure", operator="contains", value=hints["structure"])
            )
    for item in hints.get("numeric_expressions") or []:
        filters.append(
            FilterSpec(
                field=item["field"],
                operator=item["operator"],
                value=item["value"],
                value2=item.get("value2"),
                unit=item.get("unit"),
            )
        )
    filters.extend(temporal_filters)
    for item in hints.get("extra_filters") or []:
        filters.append(
            FilterSpec(
                field=item["field"],
                operator=item["operator"],
                value=item.get("value"),
            )
        )

    place_name = hints.get("place")
    scope = None
    spatial_relations: list[SpatialRelationSpec] = []
    distance_m = hints.get("distance_m")
    if place_name:
        kind = hints.get("place_kind") or "unknown"
        if kind not in {"sido", "gu", "legal_dong", "admin_dong", "basic_zone", "unknown"}:
            kind = "unknown"
        if isinstance(distance_m, (int, float)) and distance_m > 0:
            relation = "outside_distance" if hints.get("distance_outside") else "within_distance"
            spatial_relations.append(
                SpatialRelationSpec(
                    relation=relation,
                    target=SpatialTargetSpec(
                        place=PlaceSpec(name=place_name, kind=kind)
                    ),
                    distance_m=float(distance_m),
                )
            )
            scope = ScopeSpec(
                place=PlaceSpec(name=place_name, kind=kind),
                spatial_mode="auto",
            )
        else:
            mode = "boundary" if hints.get("boundary") else "auto"
            scope = ScopeSpec(place=PlaceSpec(name=place_name, kind=kind), spatial_mode=mode)

    industrial_names = list(hints.get("industrial_names") or [])
    industrial_name = hints.get("industrial_name")
    if len(industrial_names) >= 2:
        joined = "·".join(industrial_names[:4])
        spatial_relations.append(
            SpatialRelationSpec(
                relation="intersects",
                target=SpatialTargetSpec(
                    entity="industrial_complex",
                    place=PlaceSpec(name=joined, kind="unknown"),
                ),
            )
        )
    elif industrial_name:
        spatial_relations.append(
            SpatialRelationSpec(
                relation="intersects",
                target=SpatialTargetSpec(
                    entity="industrial_complex",
                    place=PlaceSpec(name=str(industrial_name), kind="unknown"),
                ),
            )
        )
    elif "산업단지" in q and any(
        k in q for k in ("안", "내", "교차", "속한", "겹치")
    ):
        spatial_relations.append(
            SpatialRelationSpec(
                relation="intersects",
                target=SpatialTargetSpec(entity="industrial_complex"),
            )
        )
    else:
        district = re.search(r"([가-힣0-9]{2,30}사업지구)", q)
        if district and any(k in q for k in ("안", "내", "교차", "속한", "겹치")):
            spatial_relations.append(
                SpatialRelationSpec(
                    relation="intersects",
                    target=SpatialTargetSpec(
                        entity="industrial_complex",
                        place=PlaceSpec(name=district.group(1), kind="unknown"),
                    ),
                )
            )

    select: list[str] = []
    order_by: list[OrderSpec] = []
    aggregations: list[AggregationSpec] = []
    group_by: list[str] = []
    limit = _extract_limit(q)
    decade_group = False

    if query_kind == "rank":
        metric = _rank_metric(q)
        direction = (
            "asc"
            if any(k in q for k in ("낮은", "작은", "오래된", "오래"))
            and not any(k in q for k in ("최근", "신규"))
            else "desc"
        )
        order_by = [OrderSpec(field=metric, direction=direction, nulls="last")]
        select = ["name", "legal_dong", "lot_address", metric]
        if limit is None:
            limit = 10
        if metric == "ground_floors" and any(k in q for k in ("많은", "많 ")) and not any(
            item.field == "ground_floors" for item in filters
        ):
            filters.append(FilterSpec(field="ground_floors", operator="gt", value=0))
        if metric in {
            "gross_floor_area_m2",
            "building_area_m2",
            "height_m",
        } and any(k in q for k in ("많은", "큰", "상위")) and not any(
            item.field == metric for item in filters
        ):
            filters.append(FilterSpec(field=metric, operator="gt", value=0))
    elif query_kind == "list":
        select = _list_select(q)
        if compare is not None and compare.field not in select:
            select.append(compare.field)
        if compare is not None and compare.value_field and compare.value_field not in select:
            select.append(compare.value_field)
        if (
            any(item.field == "usage" for item in filters)
            or (predicate is not None and predicate.op in {"or", "not"})
        ) and "usage" not in select:
            select.append("usage")
        # 「많은/큰」인데 rank로 안 잡힌 경우 → 메트릭 정렬 list
        if any(k in q for k in ("많은", "많 ", "큰 ", "큰순", "많은 순")) and not order_by:
            metric = _rank_metric(q)
            if metric not in select:
                select.append(metric)
            order_by = [OrderSpec(field=metric, direction="desc", nulls="last")]
            if metric == "ground_floors" and not any(
                item.field == "ground_floors" for item in filters
            ):
                filters.append(
                    FilterSpec(field="ground_floors", operator="gt", value=0)
                )
            if limit is None:
                limit = 10
        elif not order_by:
            # 골드 list는 A0 DESC 또는 수치 조건 필드 DESC
            metric_fields = (
                "height_m",
                "ground_floors",
                "gross_floor_area_m2",
                "building_area_m2",
                "site_area_m2",
                "building_coverage_ratio",
                "floor_area_ratio",
                "basement_floors",
            )
            order_field = None
            for item in filters:
                if item.field in metric_fields:
                    order_field = item.field
                    break
            if order_field is None:
                for field in metric_fields:
                    if field in select:
                        order_field = field
                        break
            if order_field is not None:
                order_by = [
                    OrderSpec(field=order_field, direction="desc", nulls="last")
                ]
            else:
                order_by = [OrderSpec(field="id", direction="desc", nulls="last")]
    elif query_kind == "aggregate":
        functions = _aggregate_functions(q)
        metrics = _agg_metrics(q)
        aggregations = []
        for fn in functions:
            if fn == "count":
                aggregations.append(
                    AggregationSpec(function="count", field=None, alias="n")
                )
                continue
            for metric in metrics:
                aggregations.append(
                    AggregationSpec(
                        function=fn,
                        field=metric,
                        alias=f"{fn}_{metric}",
                    )
                )
        if any(k in q for k in ("용도별", "구조별", "법정동별", "구별")):
            query_kind = "aggregate"
            if "구조별" in q:
                group_by = ["structure"]
            elif "법정동별" in q:
                group_by = ["legal_dong"]
            elif "구별" in q:
                group_by = ["sigungu_name"]
            else:
                group_by = ["usage"]
    elif query_kind == "distribution":
        if any(k in q for k in ("평균", "합계", "총합", "최대", "최소")):
            metric = _rank_metric(q)
            function = _aggregate_function(q)
            group_field = "usage"
            if any(k in q for k in ("층수별", "층별")):
                group_field = "ground_floors"
            query_kind = "aggregate"
            group_by = [group_field]
            aggregations = [
                AggregationSpec(function=function, field=metric, alias=f"{function}_{metric}")
            ]
        else:
            group_field = "usage"
            if any(k in q for k in ("층수별", "층별")):
                group_field = "ground_floors"
            if any(k in q for k in ("구간별", "년대별", "연도별")) and any(
                k in q for k in ("사용승인", "연도", "년대")
            ):
                group_field = "approval_date"
                decade_group = True
            group_by = [group_field]
            aggregations = [AggregationSpec(function="count", field=None, alias="n")]
            if limit is None:
                limit = 100

    entity: str = "building"
    assumptions = ["heuristic_plan"]
    if any(k in q for k in ("중심에서", "중심으로부터", "중심 기준")):
        assumptions.append("distance_from_centroid")
    gap = re.search(r"연도 차이가\s*(\d+)\s*년", q)
    if gap and "허가" in q and "사용승인" in q:
        assumptions.append(f"permit_year_gap:{int(gap.group(1))}")
    if decade_group:
        assumptions.append("approval_decade")
        query_kind = "aggregate"
        order_by = [OrderSpec(field="approval_date", direction="asc", nulls="last")]
        limit = None
    if bound.fixed_bins and not decade_group:
        bin_field = None
        bin_width = None
        for span in bound.numbers:
            field = span.meta.get("field")
            if field and span.value:
                bin_field = str(field)
                bin_width = float(span.value)
                break
        if bin_field and bin_width and bin_width > 0:
            group_by = [bin_field]
            assumptions.append(f"width_bucket:{bin_field}:{bin_width:g}")
            aggregations = [AggregationSpec(function="count", field=None, alias="n")]
            query_kind = "aggregate"
            order_by = [OrderSpec(field=bin_field, direction="asc", nulls="last")]
            limit = None
    if hints.get("basic_zone"):
        entity = "basic_zone"
        filters = [
            item.model_copy(update={"field": "area_m2"})
            if item.field in {"gross_floor_area_m2", "building_area_m2", "site_area_m2"}
            else item
            for item in filters
        ]
        if "이동사유별" in q or ("이동사유" in q and "별" in q):
            query_kind = "aggregate"
            group_by = ["move_reason"]
            aggregations = [
                AggregationSpec(function="count", field=None, alias="n")
            ]
            select = []
            order_by = []
            limit = None
        elif query_kind == "count" or any(
            k in q for k in ("몇 개", "몇개", "개수", "몇 곳")
        ):
            query_kind = "count"
            aggregations = [
                AggregationSpec(function="count", field=None, alias="n")
            ]
            select = []
            order_by = []
            limit = None
        else:
            query_kind = "rank"
            order_by = [OrderSpec(field="area_m2", direction="desc", nulls="last")]
            select = ["id", "gu_name", "area_m2"]
            aggregations = []
            if limit is None:
                limit = 1
    if "구별" in q and entity == "building":
        query_kind = "aggregate"
        group_by = ["sigungu_name"]
        aggregations = [
            AggregationSpec(function="count", field=None, alias="n")
        ]
        select = []
        if any(k in q for k in ("상위", "순위")):
            order_by = [OrderSpec(field="n", direction="desc", nulls="last")]
            extracted = _extract_limit(q)
            if extracted:
                limit = extracted
        else:
            order_by = []
            limit = None
    ratios: list[RatioSpec] = []
    if hints.get("ratio"):
        query_kind = "aggregate"
        ratios = _build_ratio_specs(q, filters)
        if ratios:
            ratio_fields: set[str] = set()
            for item in ratios:
                ratio_fields.update(_pred_field_names(item.numerator_predicate))
                ratio_fields.update(_pred_field_names(item.denominator_predicate))
            filters = [item for item in filters if item.field not in ratio_fields]
            if predicate is not None:
                pred_fields = set(_pred_field_names(predicate))
                if pred_fields and pred_fields <= ratio_fields:
                    predicate = None
        if not any(text in q for text in AGG_MAP) and not any(
            k in q for k in ("건수", "채수", "몇 채", "몇채")
        ):
            aggregations = []
    contract_extra = bound_contract if bound_contract is not None else extract_contract(q)
    seen_percentiles: set[tuple[str | None, float]] = set()
    for req in contract_extra.percentile_requests:
        key = (req.field, round(float(req.percentile), 6))
        if key in seen_percentiles:
            continue
        seen_percentiles.add(key)
        query_kind = "aggregate"
        aggregations.append(
            AggregationSpec(
                function="percentile",
                field=req.field or _rank_metric(q),
                percentile=req.percentile,
                alias="pctl" if len(seen_percentiles) == 1 else f"pctl_{len(seen_percentiles)}",
            )
        )
        select = []
        if not contract_extra.limit:
            limit = None
            order_by = []
    for req in contract_extra.derived_metrics:
        query_kind = "aggregate"
        aggregations.append(
            AggregationSpec(
                function="avg",
                expression=ExpressionSpec(
                    kind="divide",
                    left=ExpressionSpec(kind="field", field=req.left),
                    right=ExpressionSpec(kind="field", field=req.right),
                ),
                alias="avg_ratio",
            )
        )
        select = []
    if "지하층" in q and "합계" in q:
        query_kind = "aggregate"
        basement_pred = PredicateSpec(
            op="cmp",
            operator="gte",
            left=OperandSpec(kind="field", field="basement_floors"),
            right=OperandSpec(kind="literal", value=1),
        )
        aggregations = [
            AggregationSpec(function="sum", field="basement_floors", alias="sum_basement"),
            AggregationSpec(function="count", alias="n", predicate=basement_pred),
        ]
    if group_by and aggregations and not order_by and (
        limit or any(k in q for k in ("상위", "순위"))
    ):
        alias = aggregations[0].alias or aggregations[0].function
        for item in aggregations:
            if item.function == "count" and item.alias:
                alias = item.alias
                break
        order_by = [OrderSpec(field=alias, direction="desc", nulls="last")]
        if limit is None:
            limit = _extract_limit(q)
    if dual_subset_usage:
        query_kind = "aggregate"
        aggregations = [
            AggregationSpec(function="count", field=None, alias="total_n"),
            AggregationSpec(
                function="count",
                field=None,
                alias="subset_n",
                filter_field="usage",
                filter_operator="eq",
                filter_value=dual_subset_usage,
            ),
        ]
        select = []
        limit = None
    d198_needed = any(
        item.field in {"detail_usage", "usage_class", "ledger_kind", "permit_date"} for item in filters
    ) or (
        predicate is not None
        and _predicate_has_field(predicate, {"detail_usage", "usage_class"})
    ) or any(
        k in q
        for k in (
            "주요용도",
            "세부용도",
            "용도분류",
            "허가일",
            "허가일자",
            "문교사회용",
            "표제부",
            "집합건축물",
            "일반건축물대장",
            "용도별건물",
        )
    )
    # cat4 용도×장소 평균·건수: D198 커버 구/동이면 ledger 강제
    usage_or_detail = any(
        item.field in {"usage", "detail_usage"} for item in filters
    ) or (
        predicate is not None
        and _predicate_has_field(predicate, {"usage", "detail_usage"})
    )
    if not d198_needed and usage_or_detail:
        gu_hint = extract_gu(q)
        dong_hint = hints.get("place") if hints.get("place_kind") == "legal_dong" else None
        if gu_hint is None and dong_hint:
            gu_hint = d198_gu_for_dong(str(dong_hint))
        if gu_hint and d198_table_for_gu(str(gu_hint)) is not None:
            if query_kind in {"aggregate", "count"} or any(
                k in q for k in ("평균", "합계", "몇 채", "몇채", "건수", "채수")
            ):
                d198_needed = True
    if d198_needed:
        assumptions.append("d198_ledger")
    clarify = False
    ambiguities: list[str] = []
    if d198_needed:
        gu_name = extract_gu(q)
        dong_name = None
        if hints.get("place_kind") == "legal_dong":
            dong_name = hints.get("place")
            if gu_name is None and dong_name:
                gu_name = d198_gu_for_dong(str(dong_name))
        if gu_name is None or d198_table_for_gu(str(gu_name)) is None:
            clarify = True
            ambiguities.append(
                "세부용도·용도분류는 동래·금정 용도별건물(D198)에서만 조회할 수 있습니다"
            )
        else:
            scope = ScopeSpec(
                place=PlaceSpec(name=str(gu_name), kind="gu"),
                spatial_mode="auto",
            )
            if dong_name:
                filters.append(
                    FilterSpec(
                        field="legal_dong", operator="contains", value=dong_name
                    )
                )

    plan = SemanticQueryPlan(
        query_kind=query_kind,
        entity=entity,  # type: ignore[arg-type]
        scope=scope,
        filters=filters,
        predicate=predicate,
        select=select,
        aggregations=aggregations,
        ratios=ratios,
        group_by=group_by,
        order_by=order_by,
        limit=limit,
        spatial_relations=spatial_relations,
        requires_clarification=clarify,
        ambiguities=ambiguities,
        model_confidence=0.7,
        assumptions=assumptions,
    )
    return _ensure_contract_operators(plan, bound)


def _boolean_complete(contract, plan: SemanticQueryPlan) -> bool:
    """질문에 있는 OR/NOT이 Plan predicate에 모두 있으면 LLM 없이 채택."""
    if plan is None or plan.requires_clarification or plan.unsupported_reason:
        return False
    pred = effective_predicate(plan)
    wants_or = any(span.kind == "or" for span in contract.boolean_ops)
    wants_not = any(span.kind == "not" for span in contract.boolean_ops)
    if wants_or and not has_op(pred, "or"):
        return False
    if wants_not and not (
        has_op(pred, "not") or any(item.operator == "neq" for item in plan.filters)
    ):
        return False
    return wants_or or wants_not


def _defer_uses_heuristic(question: str, plan: SemanticQueryPlan) -> bool:
    """복합 yield 문항은 LLM 대신 완성 heuristic을 실행한다."""
    try:
        from txt2sql.intent_router import should_defer_compound_to_plan
    except Exception:
        return False
    if not should_defer_compound_to_plan(question):
        return False
    if plan.scope is None or plan.scope.place is None:
        if not plan.spatial_relations:
            return False
    if not (plan.filters or plan.predicate or plan.spatial_relations):
        return False
    pred = effective_predicate(plan)
    contract = extract_contract(question)
    if any(span.kind == "or" for span in contract.boolean_ops) and not has_op(pred, "or"):
        return False
    if any(span.kind == "not" for span in contract.boolean_ops) and not (
        has_op(pred, "not") or any(item.operator == "neq" for item in plan.filters)
    ):
        return False
    return True


def generate_semantic_plan(
    question: str,
    settings: Settings,
    *,
    conn: psycopg.Connection | None = None,
    ollama_client: Any | None = None,
    session: SessionContext | None = None,
    allow_llm: bool = True,
    contract=None,
    force_llm: bool = False,
) -> SemanticQueryPlan:
    hints = extract_plan_hints(question)
    contract = contract if contract is not None else extract_contract(question)
    heuristic = try_heuristic_plan(
        question,
        hints,
        reference_date=settings.reference_date,
        contract=contract,
    )
    if heuristic is not None:
        heuristic = _ensure_contract_operators(heuristic, contract)
    if heuristic is not None and heuristic.requires_clarification:
        if contract.ratios or contract.percentile_requests or contract.derived_metrics:
            heuristic = heuristic.model_copy(
                update={"requires_clarification": False, "ambiguities": []}
            )
        elif not force_llm:
            return heuristic
    if heuristic is not None and accept_heuristic_plan(contract, heuristic):
        return heuristic
    if heuristic is not None and _boolean_complete(contract, heuristic):
        return heuristic
    if (
        heuristic is not None
        and not heuristic.requires_clarification
        and heuristic.unsupported_reason is None
        and _defer_uses_heuristic(question, heuristic)
    ):
        return heuristic
    if (
        heuristic is not None
        and not heuristic.requires_clarification
        and heuristic.unsupported_reason is None
        and (heuristic.aggregations or heuristic.spatial_relations or heuristic.ratios)
    ):
        return heuristic
    last_error: Exception | None = None
    need_llm = force_llm or bool(getattr(contract, "unresolved_spans", None))
    if allow_llm and need_llm:
        try:
            from txt2sql.semantic_plan.examples import examples_for_contract

            return _generate_with_llm(
                question,
                settings,
                hints=hints,
                ollama_client=ollama_client,
                extra_examples=examples_for_contract(contract),
            )
        except SemanticPlanGenerationError as exc:
            last_error = exc
    if heuristic is not None and heuristic.requires_clarification:
        return heuristic
    if heuristic is not None and _boolean_complete(contract, heuristic):
        return heuristic
    if any(span.kind == "or" for span in contract.boolean_ops):
        pred = effective_predicate(heuristic) if heuristic is not None else None
        if pred is None or not has_op(pred, "or"):
            return SemanticQueryPlan(
                query_kind="list",
                entity="building",
                requires_clarification=True,
                ambiguities=["논리합(OR) 조건을 완전히 해석하지 못해 확인이 필요합니다"],
                assumptions=["or_incomplete"],
            )
    if heuristic is not None:
        return heuristic
    if not allow_llm or last_error is not None:
        return SemanticQueryPlan(
            query_kind="list",
            entity="building",
            requires_clarification=True,
            ambiguities=["질문을 완전히 해석하지 못해 확인이 필요합니다"],
            assumptions=["heuristic_incomplete"],
        )
    if last_error is not None:
        raise last_error
    raise SemanticPlanGenerationError("plan generation failed")


def _ensure_contract_operators(plan: SemanticQueryPlan, contract) -> SemanticQueryPlan:
    if plan is None or contract is None:
        return plan
    aggregations = list(plan.aggregations)
    assumptions = list(plan.assumptions or [])
    filters = list(plan.filters)
    group_by = list(plan.group_by)
    query_kind = plan.query_kind
    if contract.group_fields:
        for field in contract.group_fields:
            if field not in group_by:
                group_by.append(field)
        if not aggregations:
            for req in contract.aggregation_requests:
                aggregations.append(
                    AggregationSpec(
                        function=req.function,
                        field=req.field,
                        alias="n" if req.function == "count" else f"{req.function}_{req.field}",
                    )
                )
            if not aggregations and contract.wants_count:
                aggregations.append(AggregationSpec(function="count", alias="n"))
        if aggregations:
            query_kind = "aggregate"
        if "violation_status" in contract.group_fields:
            filters = [item for item in filters if item.field != "violation_status"]
    for req in contract.percentile_requests:
        if not any(
            item.function == "percentile"
            and abs(float(item.percentile or 0) - float(req.percentile)) < 1e-9
            for item in aggregations
        ):
            aggregations.append(
                AggregationSpec(
                    function="percentile",
                    field=req.field or "height_m",
                    percentile=req.percentile,
                    alias="pctl",
                )
            )
            query_kind = "aggregate"
    for req in contract.derived_metrics:
        if not any(
            item.expression is not None and item.expression.kind == "divide"
            for item in aggregations
        ):
            aggregations.append(
                AggregationSpec(
                    function="avg",
                    expression=ExpressionSpec(
                        kind="divide",
                        left=ExpressionSpec(kind="field", field=req.left),
                        right=ExpressionSpec(kind="field", field=req.right),
                    ),
                    alias="avg_ratio",
                )
            )
            query_kind = "aggregate"
    if contract.fixed_bins and not any(
        item.startswith("width_bucket:") or item == "approval_decade"
        for item in assumptions
    ):
        bin_field = None
        bin_width = None
        for span in contract.numbers:
            field = span.meta.get("field")
            if field and span.value:
                bin_field = str(field)
                bin_width = float(span.value)
                break
        if bin_field and bin_width and bin_width > 0:
            if bin_field not in group_by:
                group_by.append(bin_field)
            assumptions.append(f"width_bucket:{bin_field}:{bin_width:g}")
            if not aggregations:
                aggregations.append(AggregationSpec(function="count", alias="n"))
            query_kind = "aggregate"
    return plan.model_copy(
        update={
            "aggregations": aggregations,
            "assumptions": assumptions,
            "filters": filters,
            "group_by": group_by,
            "query_kind": query_kind,
        }
    )


def _generate_with_llm(
    question: str,
    settings: Settings,
    *,
    hints: dict[str, Any],
    ollama_client: Any | None,
    extra_examples: list[str] | None = None,
) -> SemanticQueryPlan:
    messages = build_messages(question, hints=hints, extra_examples=extra_examples)
    retries = max(0, int(settings.semantic_plan_max_retries))
    schema = SemanticQueryPlan.model_json_schema()
    raw = chat(
        model=settings.planner_model(),
        messages=messages,
        host=settings.ollama_host if ollama_client is None else None,
        client=ollama_client,
        temperature=0.0,
        response_format=schema,
        timeout=settings.llm_timeout_s,
    )
    try:
        return parse_plan_json(raw)
    except SemanticPlanGenerationError:
        if retries < 1:
            raise
        repair_messages = messages + [
            {"role": "assistant", "content": raw},
            {
                "role": "user",
                "content": (
                    "The previous output was invalid. "
                    "Return a valid SemanticQueryPlan JSON object only."
                ),
            },
        ]
        repaired = chat(
            model=settings.planner_model(),
            messages=repair_messages,
            host=settings.ollama_host if ollama_client is None else None,
            client=ollama_client,
            temperature=0.0,
            response_format=schema,
            timeout=settings.llm_timeout_s,
        )
        return parse_plan_json(repaired)


def _extract_json_object(text: str) -> str:
    blob = (text or "").strip()
    if blob.startswith("```"):
        blob = re.sub(r"^```(?:json)?\s*", "", blob, flags=re.I)
        blob = re.sub(r"\s*```$", "", blob)
    start = blob.find("{")
    end = blob.rfind("}")
    if start < 0 or end < start:
        raise SemanticPlanGenerationError("no json object in model output")
    payload = blob[start : end + 1]
    json.loads(payload)
    return payload


def _extract_distance_m(question: str) -> float | None:
    if not any(
        k in question for k in ("이내", "주변", "근처", "버퍼", "반경", "바깥", "경계 밖")
    ) and not re.search(r"\d+(?:\.\d+)?\s*(?:m|미터|km)\s*안", question):
        return None
    match = re.search(LENGTH_DIST_PATTERN, question)
    if not match:
        return None
    converted = convert_for_schema(match.group(1), match.group(2), "m")
    if converted is None:
        return None
    return float(converted.canonical)


def _term_is_negated(question: str, term: str) -> bool:
    """term이 '아닌/제외/빼고'의 피연산자인지. '공장 중 X이 아닌'의 공장은 양성."""
    if not question or not term:
        return False
    escaped = re.escape(term)
    if re.search(
        escaped
        + r"(?:[·･、,/][가-힣0-9]+)*(?:구조)?(?:이|가|을|를|은|는|도)?"
        r"\s*(?:아닌|아니고|아니면서|제외한|제외하고|빼고|뺀|이외)",
        question,
    ):
        return True
    if re.search(
        r"(?:제외한|제외하고|빼고|뺀)\s*" + escaped,
        question,
    ):
        return True
    return False


def _pred_field_names(pred: PredicateSpec | None) -> list[str]:
    if pred is None:
        return []
    found: list[str] = []
    if pred.left and pred.left.kind == "field" and pred.left.field:
        found.append(pred.left.field)
    if pred.right and pred.right.kind == "field" and pred.right.field:
        found.append(pred.right.field)
    for arg in pred.args or []:
        found.extend(_pred_field_names(arg))
    return found


def _and_pred(
    existing: PredicateSpec | None, extra: PredicateSpec | None
) -> PredicateSpec | None:
    if extra is None:
        return existing
    if existing is None:
        return extra
    if existing.op == "and":
        return PredicateSpec(op="and", args=[*(existing.args or []), extra])
    return PredicateSpec(op="and", args=[existing, extra])


def _filters_to_predicate(items: list[FilterSpec]) -> PredicateSpec | None:
    from txt2sql.semantic_plan.migrate import filter_to_predicate

    pred = None
    for item in items:
        pred = _and_pred(pred, filter_to_predicate(item))
    return pred


def _build_ratio_specs(question: str, filters: list[FilterSpec]) -> list[RatioSpec]:
    usage_f = [item for item in filters if item.field == "usage"]
    violate_f = [item for item in filters if item.field == "violation_status"]
    land_f = [item for item in filters if item.field == "special_land"]
    numeric_f = [
        item
        for item in filters
        if item.field
        not in {"usage", "violation_status", "special_land", "legal_dong", "building_dong_name"}
    ]
    compact = question.replace(" ", "")
    if "위반" in question and ("위반+N" in compact or "/(위반" in compact):
        return [
            RatioSpec(
                numerator_predicate=PredicateSpec(
                    op="cmp",
                    operator="eq",
                    left=OperandSpec(kind="field", field="violation_status"),
                    right=OperandSpec(kind="literal", value="Y"),
                ),
                denominator_predicate=PredicateSpec(
                    op="cmp",
                    operator="in",
                    left=OperandSpec(kind="field", field="violation_status"),
                    right=OperandSpec(kind="literal", value=["Y", "N"]),
                ),
            )
        ]
    if question.count("비율") >= 2:
        from txt2sql.query_understanding.contract import extract_contract

        specs: list[RatioSpec] = []
        for index, span in enumerate(extract_contract(question).numbers):
            field = span.meta.get("field")
            if not field:
                continue
            specs.append(
                RatioSpec(
                    numerator_predicate=PredicateSpec(
                        op="cmp",
                        operator="gte",
                        left=OperandSpec(kind="field", field=str(field)),
                        right=OperandSpec(kind="literal", value=span.value),
                    ),
                    denominator_predicate=None,
                    alias=f"ratio_{index + 1}",
                )
            )
        if specs:
            return specs
    if "중" in question:
        left = question[: question.rfind("중")]
        usage_before = extract_usage(left) is not None
        numeric_before = bool(re.search(r"\d+", left)) and any(
            k in left for k in ("층", "㎡", "m", "이상", "이하")
        )
        if usage_before and not numeric_before:
            den = _filters_to_predicate(usage_f)
            num = _filters_to_predicate(usage_f + numeric_f)
        else:
            den = _filters_to_predicate(numeric_f)
            num = _filters_to_predicate(numeric_f + usage_f)
        if num is None:
            return []
        return [RatioSpec(numerator_predicate=num, denominator_predicate=den)]
    num = _filters_to_predicate(usage_f + violate_f + land_f + numeric_f)
    if num is None:
        return []
    return [RatioSpec(numerator_predicate=num)]


def _usage_eq(value: str) -> PredicateSpec:
    return _field_eq("usage", value)


def _field_eq(field: str, value: str) -> PredicateSpec:
    return PredicateSpec(
        op="cmp",
        operator="eq",
        left=OperandSpec(kind="field", field=field),
        right=OperandSpec(kind="literal", value=value),
    )


def _predicate_has_field(pred: PredicateSpec, fields: set[str]) -> bool:
    from txt2sql.semantic_plan.predicate_utils import walk_predicate

    for node in walk_predicate(pred):
        if node.op == "cmp" and node.left and node.left.field in fields:
            return True
    return False


def _dual_count_subset_usage(question: str, usages: list[str]) -> str | None:
    if not re.search(r"전체.{0,16}채수.{0,16}그\s*중", question):
        return None
    if not usages:
        return None
    return usages[0]


def _structure_contains(value: str) -> PredicateSpec:
    return PredicateSpec(
        op="cmp",
        operator="contains",
        left=OperandSpec(kind="field", field="structure"),
        right=OperandSpec(kind="literal", value=value),
    )


def _agg_metrics(question: str) -> list[str]:
    metrics: list[str] = []
    mapping = (
        (("높이", "고도"), "height_m"),
        (("연면적",), "gross_floor_area_m2"),
        (("건축면적", "건물면적"), "building_area_m2"),
        (("대지면적",), "site_area_m2"),
        (("지상층", "층수"), "ground_floors"),
        (("건폐율",), "building_coverage_ratio"),
        (("용적율", "용적률"), "floor_area_ratio"),
    )
    for keys, field in mapping:
        if any(k in question for k in keys) and field not in metrics:
            metrics.append(field)
    return metrics or [_rank_metric(question)]


def _extract_field_compare(question: str) -> FilterSpec | None:
    contract = extract_contract(question)
    if not contract.comparisons:
        return None
    span = contract.comparisons[0]
    payload = span.value if isinstance(span.value, dict) else span.meta
    left = payload.get("left")
    right = payload.get("right")
    op = payload.get("op") or "gt"
    if not left or not right:
        return None
    return FilterSpec(field=str(left), operator=str(op), value_field=str(right))


def _aggregate_functions(question: str) -> list[str]:
    found: list[str] = []
    for text, fn in AGG_MAP.items():
        if text in question and fn not in found:
            found.append(fn)
    if any(k in question for k in ("건수", "채수", "몇 채", "몇채", "건물 수", "건물수")) and "count" not in found:
        found.append("count")
    if not found:
        if any(k in question for k in ("가장 높", "제일 높", "가장 큰", "제일 큰")):
            return ["max"]
        return ["avg"]
    return found


def _aggregate_function(question: str) -> str:
    return _aggregate_functions(question)[0]


def _extract_range_numerics(question: str) -> list[dict[str, Any]]:
    from txt2sql.query_understanding.contract import extract_contract

    contract = extract_contract(question)
    if not contract.ranges:
        return []
    out: list[dict[str, Any]] = []
    for span in contract.ranges:
        field = span.meta.get("field")
        if not field:
            if "층" in (span.text or ""):
                field = "ground_floors"
            else:
                continue
        low, high = span.meta.get("low"), span.meta.get("high")
        if (
            isinstance(low, (int, float))
            and isinstance(high, (int, float))
            and 1900 <= float(low) <= 2100
            and 1900 <= float(high) <= 2100
            and any(k in question for k in ("년", "사용승인", "허가"))
        ):
            continue
        unit = (
            "percent"
            if field in {"building_coverage_ratio", "floor_area_ratio"}
            else (
                "m2"
                if str(field).endswith("m2")
                else ("floor" if field == "ground_floors" else "m")
            )
        )
        lo_rel = span.meta.get("lo_rel") or "이상"
        hi_rel = span.meta.get("hi_rel") or "이하"
        lo_op = {"초과": "gt", "이상": "gte", "부터": "gte"}.get(lo_rel, "gte")
        hi_op = {"미만": "lt", "이하": "lte", "까지": "lte", "사이": "lte"}.get(hi_rel, "lte")
        if lo_op == "gte" and hi_op == "lte":
            out.append(
                {
                    "field": field,
                    "operator": "between",
                    "value": low,
                    "value2": high,
                    "unit": unit,
                }
            )
        else:
            out.append(
                {
                    "field": field,
                    "operator": lo_op,
                    "value": low,
                    "unit": unit,
                }
            )
            out.append(
                {
                    "field": field,
                    "operator": hi_op,
                    "value": high,
                    "unit": unit,
                }
            )
    return out


def _guess_kind(question: str) -> str:
    from txt2sql.domain import wants_map_display

    if wants_map_display(question):
        return "count"
    if "기초구역" in question and any(
        k in question for k in ("최대", "가장", "상위", "제일")
    ):
        return "rank"
    if any(k in question for k in ("비율", "퍼센트", "몇%", "%씩", "몇 프로")):
        return "aggregate"
    contract = extract_contract(question)
    if contract.percentile_requests or contract.derived_metrics:
        return "aggregate"
    if any(k in question for k in ("용도별", "층수별", "층별", "분포", "구성", "구간별", "년대별", "연도별")) or (
        "용도" in question
        and any(k in question for k in ("상위", "순위"))
        and not any(k in question for k in ("높이", "연면적", "층수", "이름"))
    ):
        return "distribution"
    if any(k in question for k in AGG_MAP) or (
        any(k in question for k in ("가장 높", "제일 높"))
        and "높이" in question
        and not re.search(r"\d+\s*(개|곳|채|동)\b", question)
    ):
        return "aggregate"
    if any(
        k in question
        for k in (
            "몇 채",
            "몇채",
            "몇 개",
            "몇개",
            "건수",
            "채수",
            "몇 동",
            "동수",
            "건물 수",
            "채야",
            "얼마나",
            "되나요",
        )
    ):
        return "count"
    if any(k in question for k in ("건폐율", "용적율", "용적률", "지하")) and not any(
        k in question
        for k in ("이름", "건물명", "목록", "보여", "어떤", "찾아", "알려줘")
    ):
        return "count"
    stripped = question.strip()
    if re.search(r"(인\s+)?[가-힣A-Za-z0-9]+ 수\s*[?？]?$", stripped):
        return "count"
    if re.search(r"\s수\s*[?？]?$", stripped) and any(
        k in stripped for k in ("건물", "주택", "시설", "아파트", "구조", "층")
    ):
        return "count"
    if any(k in question for k in ("상위", "큰 순", "높은 순", "낮은 순", "작은 순", "랭킹", "순위", "많은 순")):
        return "rank"
    if any(
        k in question
        for k in (
            "최근 준공",
            "최근준공",
            "오래된 준공",
            "오래된준공",
            "가장 최근",
            "제일 최근",
            "가장 오래",
            "제일 오래",
        )
    ) and any(k in question for k in ("준공", "사용승인", "건물", "건축물")):
        return "rank"
    if re.search(r"\d+\s*(개|곳|채|동)\b", question) and any(
        k in question for k in ("큰", "높", "상위", "낮은", "작은", "오래", "최근", "많은", "많")
    ):
        return "rank"
    if any(k in question for k in ("많은", "많 ")) and any(
        k in question for k in ("층수", "지상층", "연면적", "높이", "건축면적", "건물면적")
    ):
        return "rank"
    return "list"


def _rank_metric(question: str) -> str:
    if "기초구역" in question:
        return "area_m2"
    if any(k in question for k in ("준공", "사용승인", "건축연령", "허가일", "허가일자")):
        return "approval_date"
    if any(k in question for k in ("높이", "고도", "낮은")):
        return "height_m"
    if "건축면적" in question or "건물면적" in question:
        return "building_area_m2"
    if "대지면적" in question:
        return "site_area_m2"
    if any(k in question for k in ("지상층", "층수", "많은 층")):
        return "ground_floors"
    return "gross_floor_area_m2"


def _list_select(question: str) -> list[str]:
    wanted: list[str] = ["name", "legal_dong", "lot_address"]
    mapping = (
        (("용도",), "usage"),
        (("높이",), "height_m"),
        (("연면적",), "gross_floor_area_m2"),
        (("건축면적", "건물면적"), "building_area_m2"),
        (("대지면적",), "site_area_m2"),
        (("지상", "층수"), "ground_floors"),
        (("구조",), "structure"),
    )
    for keys, field in mapping:
        if any(k in question for k in keys) and field not in wanted:
            wanted.append(field)
    return wanted


def _extract_limit(question: str) -> int | None:
    limit = extract_contract(question).limit
    if limit is None:
        return None
    return max(1, min(int(limit), 1000))
