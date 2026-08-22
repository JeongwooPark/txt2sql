"""Semantic Query Plan 생성용 프롬프트. SQL 예시는 넣지 않는다."""

from __future__ import annotations

from typing import Any

from llm2sql.semantic_plan.catalog import catalog_prompt_text

SYSTEM_PROMPT = """You are a semantic query planner for a Korean GIS database.

Your job is NOT to write SQL.
Never output SQL.
Never output physical table names such as AL_D010_26_20250704.
Never output physical column names such as A4, A16, A24.
Never output PostGIS function names such as ST_DWithin.

Convert the Korean user's request into a SemanticQueryPlan JSON object.

Use ONLY the entities, fields, operators, query kinds, and spatial relations
listed in the provided semantic catalog.

If the user's request is ambiguous, do not guess.
Set requires_clarification=true and explain the ambiguity.

If the request cannot be represented by the supported semantic model,
set unsupported_reason.

Normalize common domain aliases:
- 아파트 → usage = 공동주택
- 학교 → usage = 교육연구시설
- 창고 → usage = 창고시설

Bare "면적" without 건축면적/연면적/대지면적 is ambiguous: requires_clarification=true.

Do not invent fields.
Do not invent units.
Do not invent places.

Return JSON only.
"""

_FEW_SHOTS = [
    (
        "해운대구 아파트가 몇 채야?",
        {
            "version": "1.0",
            "query_kind": "count",
            "entity": "building",
            "scope": {
                "place": {"name": "해운대구", "kind": "gu"},
                "spatial_mode": "auto",
            },
            "filters": [
                {"field": "usage", "operator": "eq", "value": "공동주택"}
            ],
            "select": [],
            "aggregations": [],
            "group_by": [],
            "order_by": [],
            "limit": None,
            "spatial_relations": [],
            "requires_clarification": False,
            "ambiguities": [],
            "assumptions": [],
            "unsupported_reason": None,
            "model_confidence": 0.98,
        },
    ),
    (
        "금정구에서 연면적이 가장 큰 건물 5개",
        {
            "version": "1.0",
            "query_kind": "rank",
            "entity": "building",
            "scope": {
                "place": {"name": "금정구", "kind": "gu"},
                "spatial_mode": "auto",
            },
            "filters": [],
            "select": [
                "name",
                "legal_dong",
                "lot_address",
                "gross_floor_area_m2",
            ],
            "aggregations": [],
            "group_by": [],
            "order_by": [
                {
                    "field": "gross_floor_area_m2",
                    "direction": "desc",
                    "nulls": "last",
                }
            ],
            "limit": 5,
            "spatial_relations": [],
            "requires_clarification": False,
            "ambiguities": [],
            "assumptions": [],
            "unsupported_reason": None,
            "model_confidence": 0.98,
        },
    ),
    (
        "해운대구 아파트 중 높이 100m 이상인 건물의 이름과 높이를 보여줘",
        {
            "version": "1.0",
            "query_kind": "list",
            "entity": "building",
            "scope": {
                "place": {"name": "해운대구", "kind": "gu"},
                "spatial_mode": "auto",
            },
            "filters": [
                {"field": "usage", "operator": "eq", "value": "공동주택"},
                {
                    "field": "height_m",
                    "operator": "gte",
                    "value": 100,
                    "unit": "m",
                },
            ],
            "select": ["name", "height_m"],
            "aggregations": [],
            "group_by": [],
            "order_by": [],
            "limit": 100,
            "spatial_relations": [],
            "requires_clarification": False,
            "ambiguities": [],
            "assumptions": [],
            "unsupported_reason": None,
            "model_confidence": 0.95,
        },
    ),
]


def build_messages(
    question: str,
    *,
    hints: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    import json

    shots = []
    for q, plan in _FEW_SHOTS:
        shots.append(f"User: {q}\nPlan:\n{json.dumps(plan, ensure_ascii=False, indent=2)}")
    user = [
        catalog_prompt_text(entity="building"),
        "",
        "Examples:",
        "\n\n".join(shots),
        "",
        f"User question:\n{question.strip()}",
    ]
    if hints:
        user.extend(
            [
                "",
                "Deterministic hints (verify, do not blindly copy):",
                json.dumps({"resolved_hints": hints}, ensure_ascii=False, indent=2),
            ]
        )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user)},
    ]
