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
    extract_gu,
    extract_place,
    extract_structure,
    extract_usage,
    looks_like_age_question,
)
from llm2sql.llm import chat
from llm2sql.semantic_plan.models import (
    AggregationSpec,
    FilterSpec,
    OrderSpec,
    PlaceSpec,
    ScopeSpec,
    SemanticPlanGenerationError,
    SemanticQueryPlan,
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
    "역전",
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
    kind = "unknown"
    if gu and (place == gu or not place):
        kind = "gu"
    elif place:
        kind = "legal_dong" if place.endswith("동") else "unknown"
    return {
        "place": place or gu,
        "place_kind": kind if (place or gu) else None,
        "usage": usage,
        "structure": structure[0] if structure else None,
        "numeric_expressions": numerics,
        "age_question": looks_like_age_question(q),
    }


def parse_plan_json(text: str) -> SemanticQueryPlan:
    payload = _extract_json_object(text)
    if _PHYSICAL_LEAK.search(payload):
        raise SemanticPlanGenerationError("physical identifier or SQL leaked into plan")
    try:
        return SemanticQueryPlan.model_validate_json(payload)
    except Exception as exc:
        raise SemanticPlanGenerationError(f"invalid plan json: {exc}") from exc


def try_heuristic_plan(question: str, hints: dict[str, Any] | None = None) -> SemanticQueryPlan | None:
    """Router가 놓친 단순 건물 질의를 LLM 없이 Plan으로 옮긴다."""
    q = question.strip()
    if not q:
        return None
    if any(k in q for k in _UNSUPPORTED_HINTS):
        return None
    if looks_like_age_question(q):
        return None
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
    if not any(k in q for k in ("건물", "아파트", "주택", "건축물", "공동주택", "창고", "학교")):
        if not hints.get("numeric_expressions") and not hints.get("usage"):
            return None

    query_kind = _guess_kind(q)
    filters: list[FilterSpec] = []
    if hints.get("usage"):
        filters.append(FilterSpec(field="usage", operator="eq", value=hints["usage"]))
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
                unit=item.get("unit"),
            )
        )

    place_name = hints.get("place")
    scope = None
    if place_name:
        kind = hints.get("place_kind") or "unknown"
        if kind not in {"sido", "gu", "legal_dong", "admin_dong", "basic_zone", "unknown"}:
            kind = "unknown"
        mode = "boundary" if any(k in q for k in ("안에", "내부", "경계 안", "경계안")) else "auto"
        scope = ScopeSpec(place=PlaceSpec(name=place_name, kind=kind), spatial_mode=mode)

    select: list[str] = []
    order_by: list[OrderSpec] = []
    aggregations: list[AggregationSpec] = []
    group_by: list[str] = []
    limit = _extract_limit(q)

    if query_kind == "rank":
        metric = _rank_metric(q)
        order_by = [OrderSpec(field=metric, direction="desc", nulls="last")]
        select = ["name", "legal_dong", "lot_address", metric]
        if limit is None:
            limit = 10
    elif query_kind == "list":
        select = _list_select(q)
        if limit is None:
            limit = 100
    elif query_kind == "aggregate":
        metric = _rank_metric(q)
        aggregations = [
            AggregationSpec(function="avg", field=metric, alias=f"avg_{metric}")
        ]
    elif query_kind == "distribution":
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
        select=select,
        aggregations=aggregations,
        group_by=group_by,
        order_by=order_by,
        limit=limit,
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
    heuristic = try_heuristic_plan(question, hints)
    if heuristic is not None and (
        heuristic.requires_clarification
        or (
            heuristic.unsupported_reason is None
            and (heuristic.scope is not None or heuristic.filters)
        )
    ):
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
    if heuristic is not None:
        return heuristic
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
    raw = chat(
        model=settings.ollama_model,
        messages=messages,
        host=settings.ollama_host if ollama_client is None else None,
        client=ollama_client,
        temperature=0.0,
        response_format="json",
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
            model=settings.ollama_model,
            messages=repair_messages,
            host=settings.ollama_host if ollama_client is None else None,
            client=ollama_client,
            temperature=0.0,
            response_format="json",
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


def _guess_kind(question: str) -> str:
    if any(k in question for k in ("용도별", "층수별", "층별", "분포", "구성")):
        return "distribution"
    if any(k in question for k in ("평균", "합계", "최대", "최소")):
        return "aggregate"
    if any(k in question for k in ("몇 채", "몇채", "몇 개", "몇개", "건수", "몇 동", "동수")):
        return "count"
    if any(k in question for k in ("상위", "큰 순", "높은 순", "가장 큰", "가장 높", "랭킹", "순위")):
        return "rank"
    if re.search(r"\d+\s*(개|곳|채|동)\b", question) and any(
        k in question for k in ("큰", "높", "상위")
    ):
        return "rank"
    return "list"


def _rank_metric(question: str) -> str:
    if any(k in question for k in ("높이", "고도")):
        return "height_m"
    if "건축면적" in question or "건물면적" in question:
        return "building_area_m2"
    if "대지면적" in question:
        return "site_area_m2"
    if any(k in question for k in ("지상층", "층수")):
        return "ground_floors"
    return "gross_floor_area_m2"


def _list_select(question: str) -> list[str]:
    wanted: list[str] = []
    mapping = (
        (("이름", "건물명"), "name"),
        (("법정동",), "legal_dong"),
        (("지번",), "lot_address"),
        (("용도",), "usage"),
        (("높이",), "height_m"),
        (("연면적",), "gross_floor_area_m2"),
        (("건축면적", "건물면적"), "building_area_m2"),
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
