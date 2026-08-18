from __future__ import annotations

import re
from typing import Any

import psycopg

from llm2sql.answer import emit_text_chunks, format_failure, format_success
from llm2sql.chart_qa import (
    attach_chart_offer,
    chart_capability_answer,
    chart_type_label,
    filter_chart_series,
    is_chart_accept_question,
    is_chart_capability_question,
    is_chart_decline_question,
    is_chart_series_filter_question,
    parse_chart_type_request,
    with_chart_type,
)
from llm2sql.clarify_qa import check_ambiguity, resolve_place_clarify_choice
from llm2sql.config import Settings
from llm2sql.db import connect, execute_query
from llm2sql.domain import (
    extract_age_years,
    has_anaphora,
    looks_like_age_question,
    looks_like_building_name_lookup,
    looks_like_standalone_question,
)
from llm2sql.followup_qa import answer_followup, is_followup_question
from llm2sql.guide_qa import _coverage_text, _is_coverage_question, try_guide
from llm2sql.intent_classifier import (
    IntentPrediction,
    classify_intent_hybrid,
    classify_intent_llm,
)
from llm2sql.intent_router import try_route
from llm2sql.meta_qa import answer_metadata_question, is_metadata_question
from llm2sql.profile_qa import (
    answer_profile_question,
    answer_usage_overview_question,
    is_profile_question,
    is_usage_overview_question,
)
from llm2sql.progress import ProgressCallback, ProgressTracker, TokenCallback
from llm2sql.rag_sql import run_rag_sql
from llm2sql.rank_compare_qa import answer_rank_compare, is_rank_compare_question
from llm2sql.route_dispatch import DispatchMode, match_route, tables_for_intent
from llm2sql.session import SessionContext

_AGE_REPLY_HINTS = (
    "건축년수",
    "건축년",
    "준공일",
    "준공",
    "사용승인",
    "허가일",
    "경과 년",
    "경과년",
)
_UNKNOWN_TERM_NAME_HINTS = (
    "건물이름",
    "건물명",
    "건물 이름",
    "아파트명",
    "단지명",
    "이름",
    "명칭",
)
_META_ATTR_ONLY = re.compile(
    r"(지번|주소|이름|건물명|높이|용도|연면적|건물면적|층수|몇\s*층)"
    r"(은|는|이|가)?\s*\??"
)


def _payload(
    *,
    ok: bool = True,
    answer: str | None = "",
    sql: str | None = None,
    tables: list[str] | None = None,
    rows: list | None = None,
    route: str | None = None,
    error: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    rows = list(rows or [])
    out: dict[str, Any] = {
        "ok": ok,
        "answer": answer,
        "sql": sql,
        "tables": list(tables or []),
        "rows": rows,
        "row_count": len(rows),
        "route": route,
        "error": error,
    }
    out.update(extra)
    return out


def _qa_ok(obj: Any, **extra: Any) -> dict[str, Any]:
    rows = getattr(obj, "rows", None)
    if rows is None:
        rows = getattr(obj, "options", [])
    return _payload(
        answer=obj.answer,
        sql=getattr(obj, "sql", None),
        tables=getattr(obj, "tables", None),
        rows=rows,
        route=obj.intent,
        **extra,
    )


def _llm_kw(settings: Settings, ollama_client: Any | None) -> dict[str, Any]:
    return {
        "model": settings.ollama_model,
        "host": settings.ollama_host if ollama_client is None else None,
        "client": ollama_client,
    }


def _expand_followup_question(
    question: str,
    session: SessionContext | None,
) -> str:
    """짧은 기준 보정(건축년수·준공일 등)만 직전 질문과 합친다.

    새 장소·새 주제의 독립 질문은 그대로 둔다.
    """
    if session is None:
        return question
    q = question.strip()
    if looks_like_standalone_question(q):
        return question
    base = session.last_full_question or session.last_question
    if not base:
        return question
    if len(q) > 40:
        return question
    if not any(k in q for k in _AGE_REPLY_HINTS):
        return question
    last = base.strip()
    if looks_like_age_question(last) or (
        session.last_route
        and str(session.last_route).startswith("clarify_")
        and any(k in last for k in ("지어", "년", "단독", "주택", "건물"))
    ):
        if extract_age_years(last) is not None:
            return f"{last} (기준: {q})"
        if extract_age_years(q) is not None:
            return f"{last} {q}"
        return f"{last} (기준: {q})"
    return question


def ask(
    question: str,
    settings: Settings,
    *,
    on_progress: ProgressCallback | None = None,
    on_token: TokenCallback | None = None,
    session: SessionContext | None = None,
) -> dict[str, Any]:
    """일회성 질의 (호환 API). 연결을 열고 닫는다.

    반복 호출 시에는 `Llm2SqlEngine` 사용을 권장한다.
    """
    return run_ask(
        question,
        settings,
        conn=None,
        ollama_client=None,
        on_progress=on_progress,
        on_token=on_token,
        session=session,
    )


def _rewrite_session_question(
    question: str,
    session: SessionContext,
    progress: ProgressTracker,
    on_token: TokenCallback | None,
) -> tuple[str, dict[str, Any] | None]:
    rewritten, choice_err = resolve_place_clarify_choice(
        question,
        last_route=session.last_route,
        last_question=session.last_full_question or session.last_question,
        options=session.last_rows,
    )
    if choice_err:
        progress.emit("clarify", "선택 번호 범위 오류")
        emit_text_chunks(choice_err, on_token)
        return question, _payload(
            answer=choice_err,
            rows=session.last_rows,
            route="clarify_place",
            steps=progress.steps,
        )
    if rewritten:
        progress.emit("route", f"모호 지역 선택 → {rewritten}")
        question = rewritten

    if session.last_route == "clarify_unknown_term" and any(
        k in question.strip() for k in _UNKNOWN_TERM_NAME_HINTS
    ):
        base = session.last_full_question or session.last_question
        if base and not looks_like_standalone_question(question):
            rewritten = f"{base} 건물명"
            progress.emit("route", f"미지용어→건물명 조회: {rewritten}")
            question = rewritten

    if (
        session.last_route in {"industrial_count", "industrial_names"}
        and any(k in question for k in ("이름", "명칭", "목록", "리스트", "어떤"))
        and (
            has_anaphora(question)
            or "산업단지" in question
            or len(question.strip()) <= 18
        )
        and not looks_like_standalone_question(question)
    ):
        base = session.last_full_question or session.last_question
        if base and "산업단지" in base:
            rewritten = f"{base} 이름"
            progress.emit("route", f"산업단지 후속→이름: {rewritten}")
            question = rewritten

    return question, None


def _chart_reply(
    *,
    answer: str,
    route: str,
    progress: ProgressTracker,
    on_token: TokenCallback | None,
    route_msg: str,
    session: SessionContext | None = None,
    question: str | None = None,
    chart: dict[str, Any] | None = None,
) -> dict[str, Any]:
    progress.emit("route", route_msg)
    emit_text_chunks(answer, on_token)
    extra: dict[str, Any] = {"steps": progress.steps}
    if chart:
        extra["chart"] = chart
        extra["chart_spec"] = chart
    result = _payload(answer=answer, route=route, **extra)
    if session is not None and question is not None:
        session.update_from_result(question, result)
    return result


def _try_chart_turn(
    question: str,
    session: SessionContext | None,
    progress: ProgressTracker,
    on_token: TokenCallback | None,
) -> dict[str, Any] | None:
    if session is not None and (session.pending_chart or session.last_chart):
        base_chart = session.pending_chart or session.last_chart
        assert base_chart is not None
        if is_chart_capability_question(question):
            return _chart_reply(
                answer=chart_capability_answer(base_chart),
                route="chart_help",
                progress=progress,
                on_token=on_token,
                route_msg="차트 가능 종류 안내",
                session=session,
                question=question,
            )
        new_type = parse_chart_type_request(question)
        if new_type:
            chart = with_chart_type(base_chart, new_type)
            return _chart_reply(
                answer=f"같은 내용을 {chart_type_label(new_type)} 차트로 다시 정리했습니다.",
                route="chart_render",
                progress=progress,
                on_token=on_token,
                route_msg=f"차트 종류 변경 → {new_type}",
                session=session,
                question=question,
                chart=chart,
            )
        if is_chart_series_filter_question(question):
            progress.emit("route", "차트 지표 필터")
            chart, answer = filter_chart_series(base_chart, question)
            emit_text_chunks(answer, on_token)
            extra: dict[str, Any] = {"steps": progress.steps}
            if chart:
                extra["chart"] = chart
                extra["chart_spec"] = chart
            result = _payload(
                answer=answer,
                route="chart_render" if chart else "chart_help",
                **extra,
            )
            session.update_from_result(question, result)
            return result
        if session.pending_chart and is_chart_accept_question(question):
            return _chart_reply(
                answer="요청하신 내용을 차트로 정리했습니다.",
                route="chart_render",
                progress=progress,
                on_token=on_token,
                route_msg="차트 시각화 요청",
                session=session,
                question=question,
                chart=dict(session.pending_chart),
            )
        if session.pending_chart and is_chart_decline_question(question):
            return _chart_reply(
                answer="알겠습니다. 텍스트 답변만 유지할게요. 다른 질문이 있으면 말씀해 주세요.",
                route="chart_decline",
                progress=progress,
                on_token=on_token,
                route_msg="차트 시각화 거절",
                session=session,
                question=question,
            )

    if is_chart_capability_question(question):
        return _chart_reply(
            answer=chart_capability_answer(None),
            route="chart_help",
            progress=progress,
            on_token=on_token,
            route_msg="차트 가능 종류 안내",
        )
    if is_chart_series_filter_question(question):
        return _chart_reply(
            answer=(
                "직전 차트가 없어 지표만 골라 다시 그릴 수 없습니다. "
                "먼저 비교·집계 답변에서 차트를 보신 뒤 "
                "「높이만으로 차트를 그려라」처럼 요청해 주세요."
            ),
            route="chart_help",
            progress=progress,
            on_token=on_token,
            route_msg="차트 지표 필터(맥락 없음)",
        )
    return None


def _guide_result(
    guide: Any,
    progress: ProgressTracker,
    on_token: TokenCallback | None,
) -> dict[str, Any]:
    progress.emit("route", f"안내 응답 ({guide.intent})")
    progress.emit("answer", "역할·제한·범위 안내 완료")
    emit_text_chunks(guide.answer, on_token)
    return _payload(answer=guide.answer, route=guide.intent, steps=progress.steps)


def _try_guide_turn(
    question: str,
    preferred: IntentPrediction | None,
    progress: ProgressTracker,
    on_token: TokenCallback | None,
) -> tuple[IntentPrediction | None, dict[str, Any] | None]:
    if preferred and preferred.intent in {"guide", "coverage", "out_of_scope"}:
        guide = try_guide(question)
        if (
            guide is None
            and preferred.intent == "coverage"
            and _is_coverage_question(question)
        ):
            progress.emit("route", "자료 범위 안내")
            answer = _coverage_text()
            emit_text_chunks(answer, on_token)
            return preferred, _payload(
                answer=answer, route="guide_coverage", steps=progress.steps
            )
        if guide is not None:
            return preferred, _guide_result(guide, progress, on_token)
        if preferred.intent == "coverage":
            preferred = IntentPrediction(
                "meta",
                preferred.confidence,
                "coverage 오분류→meta 재시도",
                "hybrid",
            )
            progress.emit("route", "coverage 오분류 → meta로 재해석")

    if preferred is None or preferred.intent not in {
        "guide",
        "coverage",
        "out_of_scope",
    }:
        guide = try_guide(question)
        if guide is not None:
            return preferred, _guide_result(guide, progress, on_token)
    return preferred, None


def _classify_intent(
    question: str,
    settings: Settings,
    progress: ProgressTracker,
    ollama_client: Any | None,
) -> IntentPrediction | None:
    if settings.intent_mode not in {"hybrid", "llm"}:
        return None
    progress.emit("route", f"의도 분류 ({settings.intent_mode})")
    llm = _llm_kw(settings, ollama_client)
    try:
        if settings.intent_mode == "hybrid":
            preferred = classify_intent_hybrid(
                question,
                threshold=settings.intent_confidence_threshold,
                **llm,
            )
        else:
            preferred = classify_intent_llm(question, **llm)
        progress.emit(
            "route",
            (
                f"의도={preferred.intent} "
                f"conf={preferred.confidence:.2f} ({preferred.source})"
            ),
        )
        return preferred
    except Exception as exc:
        progress.emit("route", f"의도 분류 실패 → 규칙: {type(exc).__name__}")
        return None


def run_ask(
    question: str,
    settings: Settings,
    *,
    conn: psycopg.Connection | None,
    ollama_client: Any | None,
    on_progress: ProgressCallback | None = None,
    on_token: TokenCallback | None = None,
    session: SessionContext | None = None,
) -> dict[str, Any]:
    """핵심 파이프라인. conn/ollama_client가 있으면 재사용."""
    progress = ProgressTracker(on_step=on_progress)
    progress.emit("start", f"질문 수신: {question.strip()}")

    if session is not None:
        question, early = _rewrite_session_question(
            question, session, progress, on_token
        )
        if early is not None:
            return early

    chart = _try_chart_turn(question, session, progress, on_token)
    if chart is not None:
        return chart

    preferred = _classify_intent(question, settings, progress, ollama_client)
    preferred, guide = _try_guide_turn(question, preferred, progress, on_token)
    if guide is not None:
        return guide

    effective = _expand_followup_question(question, session)
    if effective != question.strip():
        progress.emit("route", f"후속 기준 병합: {effective}")
    try:
        if conn is None:
            with connect(settings.database_url) as owned:
                result = _ask_inner(
                    effective,
                    settings,
                    progress,
                    session,
                    conn=owned,
                    ollama_client=ollama_client,
                    on_token=on_token,
                    preferred_intent=preferred,
                )
        else:
            result = _ask_inner(
                effective,
                settings,
                progress,
                session,
                conn=conn,
                ollama_client=ollama_client,
                on_token=on_token,
                preferred_intent=preferred,
            )
    except Exception as exc:
        progress.emit("error", f"처리 중 예외: {type(exc).__name__}")
        answer = format_failure(effective, error=exc, sql=None)
        emit_text_chunks(answer, on_token)
        result = _payload(
            ok=False,
            answer=answer,
            error=f"{type(exc).__name__}: {exc}",
        )
    result["steps"] = progress.steps
    before_offer = str(result.get("answer") or "")
    result = attach_chart_offer(result, question=effective)
    if (
        result.get("chart_offer")
        and on_token is not None
        and str(result.get("answer") or "").startswith(before_offer)
        and len(str(result.get("answer") or "")) > len(before_offer)
    ):
        emit_text_chunks(str(result["answer"])[len(before_offer) :], on_token)
    if session is not None and result.get("ok"):
        if looks_like_standalone_question(question) and not str(
            result.get("route") or ""
        ).startswith("followup_"):
            session.clear_focus()
        session.update_from_result(effective, result)
    return result


def _try_preferred_intent(
    question: str,
    settings: Settings,
    progress: ProgressTracker,
    *,
    conn: psycopg.Connection,
    ollama_client: Any | None,
    on_token: TokenCallback | None,
    preferred: IntentPrediction,
) -> dict[str, Any] | None:
    """분류된 의도로 핸들러를 우선 시도. 실패하면 None."""
    intent = preferred.intent
    if intent in {"guide", "coverage", "out_of_scope", "sql"}:
        return None
    llm = _llm_kw(settings, ollama_client)

    if intent == "rank_compare":
        progress.emit("route", "선호 의도: 최고 건물 비교")
        ranked = answer_rank_compare(conn, question, on_token=on_token, **llm)
        return None if ranked is None else _qa_ok(ranked)

    if intent == "usage_overview":
        progress.emit("route", "선호 의도: 용도 구성 설명")
        usage_ov = answer_usage_overview_question(
            conn, question, on_token=on_token, force=True, **llm
        )
        return None if usage_ov is None else _qa_ok(usage_ov)

    if intent == "profile":
        progress.emit("route", "선호 의도: 건물 특징/비교")
        profile = answer_profile_question(
            conn, question, on_token=on_token, force=True, **llm
        )
        return None if profile is None else _qa_ok(profile)

    if intent == "meta":
        if looks_like_building_name_lookup(question):
            return None
        if _META_ATTR_ONLY.fullmatch(question.strip()):
            return None
        progress.emit("route", "선호 의도: 메타데이터")
        meta = answer_metadata_question(conn, question, force=True)
        if meta is None:
            return None
        emit_text_chunks(meta.answer, on_token)
        return _qa_ok(meta)

    if intent == "clarify":
        progress.emit("route", "선호 의도: 모호성 확인")
        clarify = check_ambiguity(conn, question)
        if clarify is None:
            return None
        emit_text_chunks(clarify.answer, on_token)
        return _qa_ok(clarify, ambiguous_terms=clarify.ambiguous_terms)

    return None


def _finish_routed_query(
    question: str,
    settings: Settings,
    progress: ProgressTracker,
    *,
    conn: psycopg.Connection,
    ollama_client: Any | None,
    on_token: TokenCallback | None,
    routed: Any,
    route_label: str,
) -> dict[str, Any]:
    """규칙 라우터 SQL을 실행하고 한국어 답변까지 만든다."""
    tables = tables_for_intent(routed.intent)
    progress.emit("route", route_label)
    progress.emit("sql", "라우터 SQL 확정", sql=routed.sql)
    progress.emit("execute", "DB 조회 실행")
    try:
        rows = execute_query(conn, routed.sql, default_limit=settings.default_limit)
    except Exception as exc:
        progress.emit("error", f"실행 실패: {type(exc).__name__}")
        answer = format_failure(question, error=exc, sql=routed.sql)
        emit_text_chunks(answer, on_token)
        return _payload(
            ok=False,
            answer=answer,
            sql=routed.sql,
            tables=tables,
            route=routed.intent,
            error=f"{type(exc).__name__}: {exc}",
        )
    progress.emit("result", f"조회 완료 ({len(rows)}행)", row_count=len(rows))
    progress.emit("answer", "한국어 답변 생성")
    answer = format_success(
        question,
        sql=routed.sql,
        rows=rows,
        row_count=len(rows),
        route=routed.intent,
        on_token=on_token,
        **_llm_kw(settings, ollama_client),
    )
    return _payload(
        answer=answer,
        sql=routed.sql,
        tables=tables,
        rows=rows,
        route=routed.intent,
    )


def _ask_inner(
    question: str,
    settings: Settings,
    progress: ProgressTracker,
    session: SessionContext | None,
    *,
    conn: psycopg.Connection,
    ollama_client: Any | None,
    on_token: TokenCallback | None = None,
    preferred_intent: IntentPrediction | None = None,
) -> dict[str, Any]:
    if is_followup_question(question, session) and session is not None:
        progress.emit("route", "후속 질문(직전 결과 참조)으로 판단")
        follow = answer_followup(conn, question, session)
        progress.emit("answer", f"후속 답변 완료 ({follow.intent})")
        emit_text_chunks(follow.answer, on_token)
        return _qa_ok(follow)

    mode: DispatchMode = (
        "baseline" if settings.route_dispatch_mode == "baseline" else "optimized"
    )
    route_match = match_route(question, mode=mode, conn=conn)
    deferred_route = route_match.deferred
    if route_match.early is not None:
        early = route_match.early
        if early.intent == "building_name_lookup":
            label = "건물명 조회 라우트"
        elif early.intent.startswith("building_rank_"):
            label = f"건물 순위 라우트 ({early.intent})"
        else:
            label = f"산업단지 라우트 ({early.intent})"
        return _finish_routed_query(
            question,
            settings,
            progress,
            conn=conn,
            ollama_client=ollama_client,
            on_token=on_token,
            routed=early,
            route_label=label,
        )

    if preferred_intent is not None and settings.intent_mode in {"hybrid", "llm"}:
        dispatched = _try_preferred_intent(
            question,
            settings,
            progress,
            conn=conn,
            ollama_client=ollama_client,
            on_token=on_token,
            preferred=preferred_intent,
        )
        if dispatched is not None:
            return dispatched
        progress.emit("route", "선호 의도 처리 실패 → 규칙 체인")

    llm = _llm_kw(settings, ollama_client)
    if is_rank_compare_question(question):
        progress.emit("route", "복수 지역 최고 건물 비교로 판단")
        progress.emit("answer", "최고 건물 비교 답변 생성")
        ranked = answer_rank_compare(conn, question, on_token=on_token, **llm)
        if ranked is not None:
            progress.emit("answer", "최고 건물 비교 완료")
            return _qa_ok(ranked)
        progress.emit("route", "최고 건물 비교 매칭 실패 → 계속 진행")

    if is_usage_overview_question(question):
        progress.emit("route", "건물 용도 구성 설명 질의로 판단")
        progress.emit("answer", "용도 분포 자연어 생성")
        usage_ov = answer_usage_overview_question(
            conn, question, on_token=on_token, **llm
        )
        if usage_ov is not None:
            progress.emit(
                "profile",
                "용도 상위 집계 완료",
                tables=usage_ov.tables,
                sql=usage_ov.sql,
            )
            progress.emit("answer", "한국어 용도 설명 완료")
            return _qa_ok(usage_ov)
        progress.emit("route", "용도 구성 설명 매칭 실패 → 계속 진행")

    if is_profile_question(question):
        progress.emit("route", "건물 특징 요약 질의로 판단")
        progress.emit("answer", "특징 요약 자연어 생성")
        profile = answer_profile_question(conn, question, on_token=on_token, **llm)
        if profile is not None:
            progress.emit(
                "profile",
                "속성 기반 집계 요약 완료",
                tables=profile.tables,
                sql=profile.sql,
            )
            progress.emit("answer", "한국어 특징 답변 완료")
            return _qa_ok(profile)
        progress.emit("route", "특징 요약 매칭 실패 → 계속 진행")

    if is_metadata_question(question):
        progress.emit("route", "메타데이터 설명 질의로 판단")
        meta = answer_metadata_question(conn, question)
        if meta is not None:
            progress.emit(
                "meta",
                f"속성/스키마 설명 생성 ({meta.intent})",
                tables=meta.tables,
            )
            progress.emit("answer", "한국어 설명 답변 완료")
            emit_text_chunks(meta.answer, on_token)
            return _qa_ok(meta)
        progress.emit("route", "메타 질의로 보였으나 매칭 실패 → SQL 경로")

    progress.emit("route", "모호성/미지 용어 점검")
    clarify = check_ambiguity(conn, question)
    if clarify is not None:
        progress.emit(
            "clarify",
            f"확인 필요: {', '.join(clarify.ambiguous_terms) or clarify.intent}",
        )
        progress.emit("answer", "확인 요청 답변 완료")
        emit_text_chunks(clarify.answer, on_token)
        return _qa_ok(clarify, ambiguous_terms=clarify.ambiguous_terms)

    progress.emit("route", "규칙 라우터 매칭 시도")
    routed = deferred_route if deferred_route is not None else try_route(question, conn=conn)
    if routed is not None:
        progress.emit(
            "route",
            f"라우트 적중: {routed.intent}",
            intent=routed.intent,
        )
        if routed.intent == "building_age_count_d198_partial":
            progress.emit(
                "clarify",
                "건축년수는 동래·금정만 지원 → 해당 범위로 조회",
            )
        return _finish_routed_query(
            question,
            settings,
            progress,
            conn=conn,
            ollama_client=ollama_client,
            on_token=on_token,
            routed=routed,
            route_label=f"라우트 적중: {routed.intent}",
        )

    progress.emit("route", "라우트 미매칭 → RAG+LLM 경로")
    rag = run_rag_sql(
        question,
        settings,
        conn=conn,
        ollama_client=ollama_client,
        skip_answer=True,
        progress=progress,
    )
    if not rag.get("ok"):
        answer = format_failure(
            question, error=rag.get("error") or "실패", sql=rag.get("sql")
        )
        emit_text_chunks(answer, on_token)
        return _payload(
            ok=False,
            answer=answer,
            sql=rag.get("sql"),
            tables=rag.get("tables"),
            error=rag.get("error"),
        )

    progress.emit("answer", "LLM 한국어 답변 생성")
    rows = list(rag.get("rows") or [])
    sql = rag.get("sql")
    answer = format_success(
        question,
        sql=sql or "",
        rows=rows,
        row_count=len(rows),
        route=None,
        on_token=on_token,
        **llm,
    )
    progress.emit("answer", "한국어 답변 생성 완료")
    return _payload(
        answer=answer,
        sql=sql,
        tables=rag.get("tables"),
        rows=rows,
        diagnostics=rag.get("diagnostics"),
    )
