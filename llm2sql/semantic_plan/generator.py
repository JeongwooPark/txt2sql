"""자연어 → SemanticQueryPlan.

LLM structured JSON을 우선 사용하고, 실패 시 단순 건물 질의는
기존 domain/units 힌트로 heuristic plan을 만든다.
"""

from __future__ import annotations

import json
import re
from typing import Any

import psycopg

from llm2sql.config import Settings
from llm2sql.domain import (
    LENGTH_DIST_PATTERN,
    extract_gu,
    extract_place,
    extract_structure,
    extract_usage,
    extract_usages,
    is_vague_age_threshold,
    looks_like_age_question,
)
from llm2sql.llm import chat
from llm2sql.query_understanding.contract import extract_contract
from llm2sql.query_understanding.gate import accept_heuristic_plan
from llm2sql.query_understanding.operators import AGG_MAP
from llm2sql.semantic_plan.migrate import filter_to_predicate, migrate_plan_v11
from llm2sql.semantic_plan.models import (
    AggregationSpec,
    FilterSpec,
    OperandSpec,
    OrderSpec,
    PlaceSpec,
    PredicateSpec,
    ScopeSpec,
    SemanticPlanGenerationError,
    SemanticQueryPlan,
    SpatialRelationSpec,
    SpatialTargetSpec,
)
from llm2sql.semantic_plan.prompts import build_messages
from llm2sql.session import SessionContext
from llm2sql.units import UNIT_TOKEN, convert_for_schema

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
    structure = extract_structure(q)
    numerics: list[dict[str, Any]] = []
    for field, schema_unit, pattern in (
        ("height_m", "m", rf"높이[가이]?\s*(\d+(?:\.\d+)?)\s*{UNIT_TOKEN}\s*(이상|이하|초과|미만|넘는)"),
        (
            "gross_floor_area_m2",
            "㎡",
            rf"연면적[이가]?\s*(\d+(?:\.\d+)?)\s*{UNIT_TOKEN}\s*(이상|이하|초과|미만|넘는)",
        ),
        (
            "building_area_m2",
            "㎡",
            rf"(?:건축면적|건물면적)[이가]?\s*(\d+(?:\.\d+)?)\s*{UNIT_TOKEN}\s*(이상|이하|초과|미만|넘는)",
        ),
        (
            "site_area_m2",
            "㎡",
            rf"대지면적[이가]?\s*(\d+(?:\.\d+)?)\s*{UNIT_TOKEN}\s*(이상|이하|초과|미만|넘는)",
        ),
        (
            "ground_floors",
            "층",
            r"(?:지상\s*층?|층수|지상층)[이가]?\s*(\d+)\s*층?\s*(이상|이하|초과|미만|넘는)",
        ),
    ):
        match = re.search(pattern, q)
        if not match:
            continue
        unit = match.group(2) if match.lastindex and match.lastindex >= 2 else None
        if field == "ground_floors":
            unit = "층"
            rel = match.group(2)
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
        floor_m = re.search(r"(\d+)\s*층\s*(이상|이하|초과|미만|넘는)", q)
        if floor_m:
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
            rf"(\d+(?:\.\d+)?)\s*(킬로미터|㎞|km|미터|m)\s*(이상|이하|초과|미만|넘는)",
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
    kind = "unknown"
    if gu and (place == gu or not place):
        kind = "gu"
    elif place:
        kind = "legal_dong" if place.endswith("동") else "unknown"
    return {
        "place": place or gu,
        "place_kind": kind if (place or gu) else None,
        "usage": usage,
        "usages": extract_usages(q),
        "structure": structure[0] if structure else None,
        "numeric_expressions": numerics,
        "age_question": looks_like_age_question(q),
        "distance_m": _extract_distance_m(q),
        "distance_outside": any(k in q for k in ("경계 밖", "바깥", "외부")),
        "boundary": any(k in q for k in ("안에", "내부", "경계 안", "경계안", "안쪽")),
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


def try_heuristic_plan(question: str, hints: dict[str, Any] | None = None) -> SemanticQueryPlan | None:
    """Router가 놓친 단순 건물 질의를 LLM 없이 Plan으로 옮긴다."""
    q = question.strip()
    if not q:
        return None
    if any(k in q for k in _UNSUPPORTED_HINTS):
        return None
    hints = hints or extract_plan_hints(q)
    if looks_like_age_question(q) or is_vague_age_threshold(q):
        scope = None
        place_name = hints.get("place")
        if place_name:
            kind = hints.get("place_kind") or "unknown"
            if kind not in {"sido", "gu", "legal_dong", "admin_dong", "basic_zone", "unknown"}:
                kind = "unknown"
            scope = ScopeSpec(place=PlaceSpec(name=place_name, kind=kind), spatial_mode="auto")
        return SemanticQueryPlan(
            query_kind="rank",
            entity="building",
            scope=scope,
            requires_clarification=True,
            ambiguities=["건축년수 필드는 v1 catalog 미지원"],
            unsupported_reason="building_age_years not in v1 catalog",
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
    if "면적" in q and not any(k in q for k in ("연면적", "건축면적", "건물면적", "대지면적")):
        return SemanticQueryPlan(
            query_kind="list",
            entity="building",
            requires_clarification=True,
            ambiguities=["면적이 건축면적·연면적·대지면적 중 어떤 것인지 필요합니다"],
        )
    hints = hints or extract_plan_hints(q)
    if not hints.get("place") and not hints.get("usage") and not hints.get("numeric_expressions"):
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
        )
    ):
        if (
            not hints.get("numeric_expressions")
            and not hints.get("usage")
            and not hints.get("distance_m")
        ):
            return None

    query_kind = _guess_kind(q)
    filters: list[FilterSpec] = []
    predicate: PredicateSpec | None = None
    or_tokens = ("또는", "혹은", "둘 중 하나")
    not_tokens = ("제외", "아닌", "빼고", "이외")
    usages = list(hints.get("usages") or [])
    if any(k in q for k in or_tokens) and len(usages) >= 2:
        predicate = PredicateSpec(
            op="or",
            args=[_usage_eq(value) for value in usages],
        )
    elif any(k in q for k in not_tokens):
        usage_not = hints.get("usage")
        if usage_not:
            filters.append(FilterSpec(field="usage", operator="neq", value=usage_not))
            predicate = PredicateSpec(op="not", args=[_usage_eq(usage_not)])
    elif hints.get("usage"):
        filters.append(FilterSpec(field="usage", operator="eq", value=hints["usage"]))
    compare = _extract_field_compare(q)
    if compare is not None:
        filters.append(compare)
    if hints.get("structure"):
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

    select: list[str] = []
    order_by: list[OrderSpec] = []
    aggregations: list[AggregationSpec] = []
    group_by: list[str] = []
    limit = _extract_limit(q)

    if query_kind == "rank":
        metric = _rank_metric(q)
        direction = "asc" if any(k in q for k in ("낮은", "작은", "오래된")) else "desc"
        order_by = [OrderSpec(field=metric, direction=direction, nulls="last")]
        select = ["name", "legal_dong", "lot_address", metric]
        if limit is None:
            limit = 10
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
    elif query_kind == "aggregate":
        metric = _rank_metric(q)
        function = _aggregate_function(q)
        aggregations = [
            AggregationSpec(function=function, field=metric, alias=f"{function}_{metric}")
        ]
        if any(k in q for k in ("용도별",)):
            query_kind = "aggregate"
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
            group_by = [group_field]
            aggregations = [AggregationSpec(function="count", field=None, alias="n")]
            if limit is None:
                limit = 100

    return SemanticQueryPlan(
        query_kind=query_kind,
        entity="building",
        scope=scope,
        filters=filters,
        predicate=predicate,
        select=select,
        aggregations=aggregations,
        group_by=group_by,
        order_by=order_by,
        limit=limit,
        spatial_relations=spatial_relations,
        requires_clarification=False,
        model_confidence=0.7,
        assumptions=["heuristic_plan"],
    )


def generate_semantic_plan(
    question: str,
    settings: Settings,
    *,
    conn: psycopg.Connection | None = None,
    ollama_client: Any | None = None,
    session: SessionContext | None = None,
    allow_llm: bool = True,
) -> SemanticQueryPlan:
    hints = extract_plan_hints(question)
    contract = extract_contract(question)
    heuristic = try_heuristic_plan(question, hints)
    if heuristic is not None and heuristic.requires_clarification:
        return heuristic
    if heuristic is not None and accept_heuristic_plan(contract, heuristic):
        return heuristic
    last_error: Exception | None = None
    if allow_llm:
        try:
            return _generate_with_llm(
                question,
                settings,
                hints=hints,
                ollama_client=ollama_client,
            )
        except SemanticPlanGenerationError as exc:
            last_error = exc
    if heuristic is not None and heuristic.requires_clarification:
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


def _generate_with_llm(
    question: str,
    settings: Settings,
    *,
    hints: dict[str, Any],
    ollama_client: Any | None,
) -> SemanticQueryPlan:
    messages = build_messages(question, hints=hints)
    retries = max(0, int(settings.semantic_plan_max_retries))
    schema = SemanticQueryPlan.model_json_schema()
    raw = chat(
        model=settings.planner_model(),
        messages=messages,
        host=settings.ollama_host if ollama_client is None else None,
        client=ollama_client,
        temperature=0.0,
        response_format=schema,
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


def _usage_eq(value: str) -> PredicateSpec:
    return PredicateSpec(
        op="cmp",
        operator="eq",
        left=OperandSpec(kind="field", field="usage"),
        right=OperandSpec(kind="literal", value=value),
    )


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


def _aggregate_function(question: str) -> str:
    for text, fn in AGG_MAP.items():
        if text in question:
            return fn
    if any(k in question for k in ("가장 높", "제일 높", "가장 큰", "제일 큰")):
        return "max"
    return "avg"


def _extract_range_numerics(question: str) -> list[dict[str, Any]]:
    from llm2sql.query_understanding.contract import extract_contract

    contract = extract_contract(question)
    if not contract.ranges:
        return []
    span = contract.ranges[0]
    field = span.meta.get("field") or "height_m"
    unit = (
        "m2"
        if str(field).endswith("m2")
        else ("floor" if field == "ground_floors" else "m")
    )
    lo_rel = span.meta.get("lo_rel") or "이상"
    hi_rel = span.meta.get("hi_rel") or "이하"
    lo_op = {"초과": "gt", "이상": "gte", "부터": "gte"}.get(lo_rel, "gte")
    hi_op = {"미만": "lt", "이하": "lte", "까지": "lte", "사이": "lte"}.get(hi_rel, "lte")
    if lo_op == "gte" and hi_op == "lte":
        return [
            {
                "field": field,
                "operator": "between",
                "value": span.meta.get("low"),
                "value2": span.meta.get("high"),
                "unit": unit,
            }
        ]
    return [
        {
            "field": field,
            "operator": lo_op,
            "value": span.meta.get("low"),
            "unit": unit,
        },
        {
            "field": field,
            "operator": hi_op,
            "value": span.meta.get("high"),
            "unit": unit,
        },
    ]


def _guess_kind(question: str) -> str:
    from llm2sql.domain import wants_map_display

    if wants_map_display(question):
        return "count"
    if any(k in question for k in ("용도별", "층수별", "층별", "분포", "구성")):
        return "distribution"
    if any(k in question for k in AGG_MAP) or (
        any(k in question for k in ("가장 높", "제일 높"))
        and "높이" in question
        and not re.search(r"\d+\s*(개|곳|채|동)\b", question)
    ):
        return "aggregate"
    if any(
        k in question
        for k in ("몇 채", "몇채", "몇 개", "몇개", "건수", "몇 동", "동수", "건물 수", "채야")
    ):
        return "count"
    if any(k in question for k in ("상위", "큰 순", "높은 순", "낮은 순", "작은 순", "랭킹", "순위")):
        return "rank"
    if re.search(r"\d+\s*(개|곳|채|동)\b", question) and any(
        k in question for k in ("큰", "높", "상위", "낮은", "작은", "오래")
    ):
        return "rank"
    return "list"


def _rank_metric(question: str) -> str:
    if any(k in question for k in ("높이", "고도", "낮은")):
        return "height_m"
    if "건축면적" in question or "건물면적" in question:
        return "building_area_m2"
    if "대지면적" in question:
        return "site_area_m2"
    if any(k in question for k in ("지상층", "층수")):
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
    match = re.search(r"(?:상위\s*)?(\d+)\s*(?:개|곳|채|동)\b", question)
    if match:
        n = int(match.group(1))
        return max(1, min(n, 1000))
    return None
