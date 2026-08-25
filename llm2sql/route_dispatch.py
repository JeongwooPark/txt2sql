"""규칙 SQL 라우트 조기 디스패치 (baseline vs optimized).

baseline: 파이프라인 early 구간에서 try_route를 여러 번 호출하던 방식
optimized: try_route 1회 + allowlist early + 잔여 결과는 이후 단계 재사용
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import psycopg

from llm2sql.domain import D198_TABLES, looks_like_building_name_lookup
from llm2sql.intent_router import (
    RoutedQuery,
    _route_building_rank,
    try_route,
)

DispatchMode = Literal["baseline", "optimized"]

EARLY_INDUSTRIAL_INTENTS = frozenset(
    {
        "industrial_count",
        "industrial_code_prefix",
        "industrial_names",
        "buildings_in_industrial",
    }
)


@dataclass(frozen=True)
class RouteMatch:
    """조기 실행용 매치 결과. deferred는 clarify/meta 이후 try_route 자리에 재사용."""

    early: RoutedQuery | None
    deferred: RoutedQuery | None
    mode: DispatchMode
    try_route_calls: int


def tables_from_sql(sql: str | None) -> list[str]:
    if not sql:
        return []
    seen: list[str] = []
    for name in re.findall(r'FROM\s+"([^"]+)"', sql, flags=re.I):
        if name not in seen:
            seen.append(name)
    return seen


def tables_for_intent(intent: str) -> list[str]:
    d010 = ["AL_D010_26_20250704"]
    d060 = ["AL_D060_00_20250804"]
    d198 = list(D198_TABLES)
    bas = ["TL_KODIS_BAS_26_202507"]
    if intent == "buildings_in_industrial":
        return d010 + d060
    if intent == "industrial_bas_intersect":
        return d060 + bas
    if intent.startswith("industrial_"):
        return d060
    if intent.startswith("building_rank_") or intent in {
        "building_name_lookup",
        "building_place_count",
        "building_usage_count",
        "building_height_count",
        "building_floor_count",
        "building_area_topn",
        "building_area_top1_value",
        "building_area_threshold_count",
        "building_area_threshold_list",
        "building_height_threshold_list",
        "building_floor_threshold_list",
        "building_structure_list",
        "building_structure_count",
        "building_special_land_list",
        "building_special_land_count",
        "building_attr_list",
        "building_attr_count",
        "building_in_dong_spatial",
        "building_in_dong_spatial_list",
        "buffer_count",
        "place_buffer_count",
        "place_buffer_list",
        "place_buffer_outside_count",
        "place_buffer_outside_list",
    }:
        if intent in {
            "building_in_dong_spatial",
            "building_in_dong_spatial_list",
            "place_buffer_count",
            "place_buffer_list",
            "place_buffer_outside_count",
            "place_buffer_outside_list",
        }:
            return d010 + ["BND_ADM_DONG_PG"]
        return d010
    if intent in {"spatial_bldg_bas_count", "spatial_bldg_bas_list"}:
        return d010 + ["TL_KODIS_BAS_26_202507"]
    if intent == "legal_dong_admin_share":
        return d010 + ["BND_ADM_DONG_PG"]
    if intent == "legal_dong_admin_members":
        return ["BND_ADM_DONG_PG"]
    if intent.startswith("spatial_bas_dong") or intent == "spatial_bas_bnd_gu_count":
        return ["TL_KODIS_BAS_26_202507", "BND_ADM_DONG_PG"]
    if intent == "spatial_dong_touch_list":
        return ["BND_ADM_DONG_PG"]
    if intent.startswith("d010_attr"):
        return d010
    if intent.startswith("d060_attr"):
        return d060
    if intent.startswith("bnd_attr"):
        return ["BND_ADM_DONG_PG"]
    if intent.startswith("bas_attr") or intent.startswith("bas_"):
        return bas
    if intent.startswith("building_age") or intent.startswith("d198_"):
        return d198
    return []


def _is_early_intent(intent: str) -> bool:
    if intent == "building_name_lookup":
        return True
    if intent in EARLY_INDUSTRIAL_INTENTS:
        return True
    if intent == "legal_dong_admin_members":
        return True
    if intent.startswith("building_rank_"):
        return True
    return False


def match_route_baseline(
    question: str,
    *,
    conn: psycopg.Connection | None = None,
    contract=None,
) -> RouteMatch:
    """최적화 전: early 구간에서 try_route / rank를 분리 호출."""
    calls = 0
    q = question.strip()

    _ = contract
    if looks_like_building_name_lookup(q):
        calls += 1
        routed = try_route(q, conn=conn)
        if routed is not None and routed.intent == "building_name_lookup":
            return RouteMatch(early=routed, deferred=None, mode="baseline", try_route_calls=calls)

    calls += 1
    early = try_route(q, conn=conn)
    if early is not None and early.intent in EARLY_INDUSTRIAL_INTENTS:
        return RouteMatch(early=early, deferred=None, mode="baseline", try_route_calls=calls)

    ranked = _route_building_rank(q)
    if ranked is not None:
        return RouteMatch(early=ranked, deferred=None, mode="baseline", try_route_calls=calls)

    # 이후 파이프라인에서 다시 try_route 호출한다고 가정해 deferred에 보관하지 않음
    # (벤치의 '재사용' 효과는 optimized만 측정)
    return RouteMatch(early=None, deferred=early, mode="baseline", try_route_calls=calls)


def match_route_optimized(
    question: str,
    *,
    conn: psycopg.Connection | None = None,
    contract=None,
) -> RouteMatch:
    """최적화: try_route 1회. early allowlist면 early, 아니면 deferred로 재사용."""
    _ = contract
    q = question.strip()
    routed = try_route(q, conn=conn)
    if routed is None:
        return RouteMatch(early=None, deferred=None, mode="optimized", try_route_calls=1)

    if _is_early_intent(routed.intent):
        # building_name은 try_route 내부 looks_like 조건과 동일
        return RouteMatch(early=routed, deferred=None, mode="optimized", try_route_calls=1)

    return RouteMatch(early=None, deferred=routed, mode="optimized", try_route_calls=1)


def match_route(
    question: str,
    *,
    mode: DispatchMode = "optimized",
    conn: psycopg.Connection | None = None,
    contract=None,
) -> RouteMatch:
    if mode == "baseline":
        return match_route_baseline(question, conn=conn, contract=contract)
    return match_route_optimized(question, conn=conn, contract=contract)
