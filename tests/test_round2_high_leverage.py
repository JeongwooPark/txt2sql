"""Round2 고레버리지 회귀: meta 오탐 · 건물명 컬럼 오탐 · age coverage."""

from __future__ import annotations

from txt2sql.domain import (
    extract_building_name_candidate,
    looks_like_building_name_lookup,
)
from txt2sql.meta_qa import is_metadata_question
from txt2sql.semantic_plan.generator import try_heuristic_plan
from txt2sql.semantic_plan.models import (
    FilterSpec,
    OrderSpec,
    PlaceSpec,
    ScopeSpec,
    SemanticQueryPlan,
)
from txt2sql.semantic_plan.validator import validate_semantic_plan


def test_place_building_count_알려줘_is_not_meta() -> None:
    assert is_metadata_question("연산동 건물 수를 알려줘") is False
    assert is_metadata_question("금정구 기초구역 수를 알려줘") is False
    # 스키마 질문은 여전히 메타
    assert is_metadata_question("건물 수 컬럼이 뭐야?") is True


def test_building_name_column_list_is_not_name_lookup() -> None:
    cases = [
        "동래구의 공동주택 건물명과 지번을 보여줘",
        "사하구 건물 중 건물명이 있는 것만 보여줘",
        "해운대구 건물명과 지번을 20개만 보여줘",
        "금정구의 의료시설 건물명과 지번을 보여줘",
    ]
    for q in cases:
        assert looks_like_building_name_lookup(q) is False, q
        cand = extract_building_name_candidate(q)
        assert cand is None or "보여줘" not in (cand or ""), q


def test_named_building_with_column_phrase_still_lookup() -> None:
    q = "구서동 롯데캐슬 골드 구서동의 제1종근린생활시설 건물명과 지번을 보여줘"
    assert "롯데캐슬" in (extract_building_name_candidate(q) or "")
    assert looks_like_building_name_lookup(q) is True


def test_real_building_name_lookup_still_true() -> None:
    q = "구서역포르투나 아파트 주소 알려줘"
    assert looks_like_building_name_lookup(q) is True


def test_admin_dong_phrase_not_jeongdong_place() -> None:
    from txt2sql.domain import extract_places

    assert "정동" not in extract_places("산업단지와 겹치는 행정동 수를 구·군별로 집계해줘")
    assert "정동" not in extract_places("법정동코드별 건물 수를 집계해줘")


def test_age_rank_plan_has_approval_order() -> None:
    q = "금정구에서 가장 최근 준공된 건물 10개를 보여줘"
    plan = try_heuristic_plan(q)
    assert plan is not None
    assert plan.query_kind == "rank"
    assert any(o.field == "approval_date" for o in plan.order_by)
    checked = validate_semantic_plan(plan, q)
    assert checked.status == "ready"
    assert not any("unsupported_coverage" in e for e in checked.errors)


def test_age_without_temporal_ref_still_falls_back() -> None:
    plan = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="금정구", kind="gu")),
    )
    result = validate_semantic_plan(plan, "금정구에서 30년 넘은 건물 몇 채")
    assert result.status == "fallback"


def test_age_order_only_is_allowed() -> None:
    plan = SemanticQueryPlan(
        query_kind="rank",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="동래구", kind="gu")),
        select=["name", "legal_dong", "approval_date"],
        order_by=[OrderSpec(field="approval_date", direction="desc", nulls="last")],
        limit=10,
    )
    result = validate_semantic_plan(plan, "동래구에서 가장 최근 준공된 건물 10개")
    assert result.status == "ready"


def test_age_filter_still_allowed() -> None:
    plan = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="서동", kind="legal_dong")),
        filters=[FilterSpec(field="approval_date", operator="lte", value="1986-01-01")],
    )
    result = validate_semantic_plan(plan, "서동에서 40년 이상 된 건물 수")
    assert result.status == "ready"
