"""LLM 기반 질문 의도 분류 (하이브리드 라우팅용)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from llm2sql.answer import _chat
from llm2sql.guide_qa import _is_coverage_question, try_guide
from llm2sql.meta_qa import is_metadata_question
from llm2sql.profile_qa import is_profile_question, is_usage_overview_question
from llm2sql.rank_compare_qa import is_rank_compare_question

INTENT_LABELS = (
    "guide",
    "coverage",
    "meta",
    "usage_overview",
    "profile",
    "rank_compare",
    "sql",
    "clarify",
    "out_of_scope",
)

DEFAULT_CONFIDENCE_THRESHOLD = 0.55

SYSTEM_PROMPT = """당신은 부산 GIS 자연어 질의 시스템의 의도 분류기입니다.
사용자 질문을 아래 intent 중 정확히 하나로 분류하세요.

intent 정의:
- guide: 기능/도움말/역할/인사/제한 안내
- coverage: 전국·타시도·자료 범위 유무 (부산만인지)
- meta: 테이블/컬럼/스키마/데이터셋 목록·속성 의미 설명
- usage_overview: 지역 건물의 주요/상위 용도 구성·분포 설명
- profile: 지역·용도 건물 특징 요약, 지역 간 비교, 부산시 전역 대비 비교
- rank_compare: 복수(2개 이상) 지역의 최고(가장 높/큰) 건물끼리 비교
- sql: 건수·순위·목록·공간조건 등 DB 조회가 필요한 일반 질의 (지역 1곳의 최고/가장 포함)
- clarify: 모호한 지명(복수 동명) 또는 주관 표현(좋은/추천)이라 확인이 필요
- out_of_scope: 날씨·뉴스·코딩 등 GIS 밖 주제

규칙:
- JSON만 출력. 설명/마크다운/생각 과정 금지.
- 형식: {"intent":"<label>","confidence":0.0~1.0,"reason":"짧은 한국어"}
- confidence는 확신도. 애매하면 0.5 이하.
- '설명'이어도 컬럼/테이블 의미가 아니면 meta가 아님 (용도 설명→usage_overview, 특징→profile).
- '부산시 전역 대비 구서동' → profile
- '전국자료 있나' → coverage
- '해운대구 건물 몇 채' → sql
- 지역이 하나이고 '가장 큰/높은/넓은'만 있으면 → sql (rank_compare 아님)
- 지역이 둘 이상이고 최고 건물을 서로 비교하면 → rank_compare
- '제일 좋은/추천/괜찮은'처럼 주관이면 → clarify
- '송정동'처럼 여러 구에 있을 수 있는 동 + 건수 → clarify 가능. 확실치 않으면 clarify
- 'A9가 뭐야'처럼 컬럼 코드 의미 → meta
- '사용가능한 데이터 이름/목록' → meta (건물 용도명 조회 sql 아님)
- 'GIS건물통합정보_부산광역시에 들어있는 내용'처럼 특정 데이터셋 설명 → meta (coverage 아님)
- 'GIS건물통합정보_부산광역시 데이터 요약해줘' → meta (지역 건물 프로필이 아님)
- '구서동포르투나 아파트 정보 있나'처럼 특정 건물명 조회 → sql (clarify/meta 아님)
- coverage는 '전국/타시도 자료 있냐'처럼 범위 유무 질문만
"""


@dataclass(frozen=True)
class IntentPrediction:
    intent: str
    confidence: float
    reason: str = ""
    source: str = "llm"  # llm | rules | hybrid

    @property
    def ok(self) -> bool:
        return self.intent in INTENT_LABELS


def classify_intent_llm(
    question: str,
    *,
    model: str,
    host: str | None = None,
    client: Any | None = None,
) -> IntentPrediction:
    q = question.strip()
    if not q:
        return IntentPrediction("guide", 1.0, "빈 질문", "llm")

    raw = _chat(
        model=model,
        host=host,
        client=client,
        temperature=0.0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"질문: {q}"},
        ],
    )
    parsed = _parse_intent_json(raw)
    if parsed is None:
        return IntentPrediction("sql", 0.0, "JSON 파싱 실패", "llm")
    intent, conf, reason = parsed
    if intent not in INTENT_LABELS:
        return IntentPrediction("sql", 0.0, f"알 수 없는 intent={intent}", "llm")
    return IntentPrediction(intent, conf, reason, "llm")


def predict_intent_rules(question: str) -> IntentPrediction:
    """현재 규칙 파이프라인과 유사한 의도 추정 (DB 없이)."""
    q = question.strip()
    if not q:
        return IntentPrediction("guide", 1.0, "빈 질문", "rules")

    if _is_coverage_question(q):
        return IntentPrediction("coverage", 0.95, "전국/범위 규칙", "rules")

    guide = try_guide(q)
    if guide is not None:
        if guide.intent == "guide_coverage":
            return IntentPrediction("coverage", 0.95, guide.intent, "rules")
        if guide.intent == "guide_out_of_scope":
            return IntentPrediction("out_of_scope", 0.9, guide.intent, "rules")
        return IntentPrediction("guide", 0.9, guide.intent, "rules")

    if is_rank_compare_question(q):
        return IntentPrediction("rank_compare", 0.9, "복수지역 최고 비교", "rules")
    if is_usage_overview_question(q):
        return IntentPrediction("usage_overview", 0.9, "용도 구성", "rules")
    if is_profile_question(q):
        return IntentPrediction("profile", 0.85, "특징/비교", "rules")
    if is_metadata_question(q):
        return IntentPrediction("meta", 0.85, "메타/스키마", "rules")
    if _asks_catalog_safe(q):
        return IntentPrediction("meta", 0.85, "데이터셋 목록", "rules")
    if _looks_like_dataset_content_question(q):
        return IntentPrediction("meta", 0.9, "데이터셋 내용", "rules")

    # 규칙상 모호·주관 힌트
    if any(k in q for k in ("제일 좋은", "가장 좋은", "추천", "괜찮은")):
        return IntentPrediction("clarify", 0.7, "주관 표현", "rules")

    return IntentPrediction("sql", 0.6, "기본 SQL 경로", "rules")


def _asks_catalog_safe(q: str) -> bool:
    from llm2sql.meta_qa import _asks_catalog

    return _asks_catalog(q)


def _looks_like_dataset_content_question(question: str) -> bool:
    q = question.strip()
    contentish = any(
        k in q
        for k in (
            "들어있는",
            "담긴",
            "내용",
            "속성",
            "컬럼",
            "스키마",
            "뭐가 있",
            "무엇이 있",
        )
    )
    datasetish = any(
        k in q
        for k in (
            "GIS",
            "AL_",
            "건물통합",
            "용도별건물",
            "산업단지",
            "기초구역",
            "행정구역",
            "데이터셋",
            "테이블",
        )
    ) or ("_" in q and any(k in q for k in ("정보", "건물", "단지", "구역")))
    return contentish and datasetish


def classify_intent_hybrid(
    question: str,
    *,
    model: str,
    host: str | None = None,
    client: Any | None = None,
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> IntentPrediction:
    """LLM 분류를 우선하고, 실패·저신뢰 시 규칙으로 폴백.

    정확도 우선: 단일지역 순위/주관표현 등 LLM 오분류 패턴은 규칙으로 보정.
    """
    rules = predict_intent_rules(question)
    try:
        llm = classify_intent_llm(
            question, model=model, host=host, client=client
        )
    except Exception as exc:
        return IntentPrediction(
            rules.intent,
            rules.confidence,
            f"LLM 실패→규칙 ({type(exc).__name__})",
            "hybrid",
        )

    # 고신뢰 규칙 보정이 분명한 경우 규칙 우선
    q = question.strip()
    if _looks_like_dataset_content_question(q):
        return IntentPrediction(
            "meta", 0.92, "데이터셋 내용/설명→meta", "hybrid"
        )
    if rules.intent == "clarify" and any(
        k in q for k in ("제일 좋은", "가장 좋은", "추천", "괜찮은")
    ):
        return IntentPrediction(
            "clarify", rules.confidence, "주관 표현→규칙 clarify", "hybrid"
        )
    if (
        rules.intent == "sql"
        and llm.intent == "rank_compare"
        and not _has_multi_place_compare(q)
    ):
        return IntentPrediction(
            "sql",
            max(rules.confidence, 0.8),
            "단일지역 순위→sql 보정",
            "hybrid",
        )

    if llm.confidence >= threshold and llm.ok:
        # LLM이 coverage로 왔어도 실제 범위 질문이 아니면 무시
        if llm.intent == "coverage" and not _is_coverage_question(q):
            if rules.intent == "meta" or _looks_like_dataset_content_question(q):
                return IntentPrediction(
                    "meta", 0.9, "coverage 오분류→meta", "hybrid"
                )
            return IntentPrediction(
                rules.intent,
                rules.confidence,
                "coverage 오분류→규칙",
                "hybrid",
            )
        return IntentPrediction(
            llm.intent, llm.confidence, llm.reason or "llm", "hybrid"
        )
    return IntentPrediction(
        rules.intent,
        rules.confidence,
        f"저신뢰({llm.confidence:.2f}/{llm.intent})→규칙",
        "hybrid",
    )


def _has_multi_place_compare(question: str) -> bool:
    from llm2sql.domain import extract_places

    places = extract_places(question)
    if len(places) >= 2:
        return True
    return any(k in question for k in (" vs ", " VS ", "대비", "비교"))


def _parse_intent_json(text: str) -> tuple[str, float, str] | None:
    if not text:
        return None
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.I).strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.I | re.S)
    if fence:
        cleaned = fence.group(1).strip()
    # 첫 JSON 객체
    m = re.search(r"\{[\s\S]*\}", cleaned)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    intent = str(data.get("intent") or "").strip()
    try:
        conf = float(data.get("confidence", 0))
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    reason = str(data.get("reason") or "").strip()
    return intent, conf, reason
