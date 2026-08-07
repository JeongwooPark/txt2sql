from __future__ import annotations

from typing import Any

import psycopg

from llm2sql.answer import emit_text_chunks, format_failure, format_success
from llm2sql.chart_qa import (
    attach_chart_offer,
    chart_capability_answer,
    chart_type_label,
    is_chart_accept_question,
    is_chart_capability_question,
    is_chart_decline_question,
    parse_chart_type_request,
    with_chart_type,
)
from llm2sql.clarify_qa import check_ambiguity, resolve_place_clarify_choice
from llm2sql.config import Settings
from llm2sql.db import connect, execute_query
from llm2sql.domain import (
    extract_age_years,
    looks_like_age_question,
    looks_like_standalone_question,
)
from llm2sql.followup_qa import answer_followup, is_followup_question
from llm2sql.guide_qa import try_guide
from llm2sql.intent_classifier import (
    IntentPrediction,
    classify_intent_hybrid,
    classify_intent_llm,
)
from llm2sql.intent_router import fix_common_sql_mistakes, try_route
from llm2sql.meta_qa import answer_metadata_question, is_metadata_question
from llm2sql.profile_qa import (
    answer_profile_question,
    answer_usage_overview_question,
    is_profile_question,
    is_usage_overview_question,
)
from llm2sql.progress import ProgressCallback, ProgressTracker, TokenCallback
from llm2sql.rank_compare_qa import answer_rank_compare, is_rank_compare_question
from llm2sql.schema_retriever import retrieve_schema
from llm2sql.session import SessionContext
from llm2sql.spatial_templates import (
    building_in_dong_count_sql,
    extract_place_token,
    spatial_fewshot,
)
from llm2sql.sql_fix import load_name_maps, rewrite_display_names
from llm2sql.sql_generator import build_few_shot_for_question, generate_sql
from llm2sql.sql_validator import diagnose_sql, validate_sql_preexec

_SPATIAL_INTENT = ("안에", "내부", "속하는", "교차", "버퍼", "거리", "근처", "이내")

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


def _has_spatial_sql(sql: str) -> bool:
    upper = sql.upper()
    return any(
        fn in upper
        for fn in (
            "ST_INTERSECTS",
            "ST_WITHIN",
            "ST_DWITHIN",
            "ST_DISTANCE",
            "ST_CONTAINS",
        )
    )


def _normalize_sql(
    sql: str,
    table_map: dict[str, str],
    column_map: dict[str, str],
    *,
    question: str | None = None,
) -> str:
    sql = rewrite_display_names(sql, table_map, column_map)
    return fix_common_sql_mistakes(sql, question=question)


def _gen_sql(
    question: str,
    schema_text: str,
    settings: Settings,
    *,
    ollama_client: Any | None,
    error_feedback: str | None = None,
    few_shot: str | None = None,
) -> str:
    return generate_sql(
        question,
        schema_text,
        model=settings.ollama_model,
        host=settings.ollama_host if ollama_client is None else None,
        client=ollama_client,
        error_feedback=error_feedback,
        few_shot=few_shot,
    )


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

    # 직전 복수 동 확인에 대한 번호 선택 (예: 1 / 1번)
    if session is not None:
        rewritten, choice_err = resolve_place_clarify_choice(
            question,
            last_route=session.last_route,
            last_question=session.last_full_question or session.last_question,
            options=session.last_rows,
        )
        if choice_err:
            progress.emit("clarify", "선택 번호 범위 오류")
            emit_text_chunks(choice_err, on_token)
            return {
                "ok": True,
                "answer": choice_err,
                "sql": None,
                "tables": [],
                "rows": list(session.last_rows or []),
                "row_count": len(session.last_rows or []),
                "route": "clarify_place",
                "error": None,
                "steps": progress.steps,
            }
        if rewritten:
            progress.emit("route", f"모호 지역 선택 → {rewritten}")
            question = rewritten

    # 직전 답변의 차트 제안 수락/거절·종류 변경·가능 종류 안내
    if session is not None and (session.pending_chart or session.last_chart):
        base_chart = session.pending_chart or session.last_chart
        assert base_chart is not None
        if is_chart_capability_question(question):
            progress.emit("route", "차트 가능 종류 안내")
            answer = chart_capability_answer(base_chart)
            emit_text_chunks(answer, on_token)
            result = {
                "ok": True,
                "answer": answer,
                "sql": None,
                "tables": [],
                "rows": [],
                "row_count": 0,
                "route": "chart_help",
                "error": None,
                "steps": progress.steps,
            }
            session.update_from_result(question, result)
            return result
        new_type = parse_chart_type_request(question)
        if new_type:
            progress.emit("route", f"차트 종류 변경 → {new_type}")
            chart = with_chart_type(base_chart, new_type)
            label = chart_type_label(new_type)
            answer = f"같은 내용을 {label} 차트로 다시 정리했습니다."
            emit_text_chunks(answer, on_token)
            result = {
                "ok": True,
                "answer": answer,
                "sql": None,
                "tables": [],
                "rows": [],
                "row_count": 0,
                "route": "chart_render",
                "error": None,
                "chart": chart,
                "chart_spec": chart,
                "steps": progress.steps,
            }
            session.update_from_result(question, result)
            return result
        if session.pending_chart and is_chart_accept_question(question):
            progress.emit("route", "차트 시각화 요청")
            chart = dict(session.pending_chart)
            answer = "요청하신 내용을 차트로 정리했습니다."
            emit_text_chunks(answer, on_token)
            result = {
                "ok": True,
                "answer": answer,
                "sql": None,
                "tables": [],
                "rows": [],
                "row_count": 0,
                "route": "chart_render",
                "error": None,
                "chart": chart,
                "chart_spec": chart,
                "steps": progress.steps,
            }
            session.update_from_result(question, result)
            return result
        if session.pending_chart and is_chart_decline_question(question):
            progress.emit("route", "차트 시각화 거절")
            answer = "알겠습니다. 텍스트 답변만 유지할게요. 다른 질문이 있으면 말씀해 주세요."
            emit_text_chunks(answer, on_token)
            result = {
                "ok": True,
                "answer": answer,
                "sql": None,
                "tables": [],
                "rows": [],
                "row_count": 0,
                "route": "chart_decline",
                "error": None,
                "steps": progress.steps,
            }
            session.update_from_result(question, result)
            return result

    # 차트 맥락이 없어도 종류 안내 질문이면 바로 답변
    if is_chart_capability_question(question):
        progress.emit("route", "차트 가능 종류 안내")
        answer = chart_capability_answer(None)
        emit_text_chunks(answer, on_token)
        return {
            "ok": True,
            "answer": answer,
            "sql": None,
            "tables": [],
            "rows": [],
            "row_count": 0,
            "route": "chart_help",
            "error": None,
            "steps": progress.steps,
        }

    preferred: IntentPrediction | None = None
    if settings.intent_mode in {"hybrid", "llm"}:
        progress.emit("route", f"의도 분류 ({settings.intent_mode})")
        try:
            if settings.intent_mode == "hybrid":
                preferred = classify_intent_hybrid(
                    question,
                    model=settings.ollama_model,
                    host=settings.ollama_host if ollama_client is None else None,
                    client=ollama_client,
                    threshold=settings.intent_confidence_threshold,
                )
            else:
                preferred = classify_intent_llm(
                    question,
                    model=settings.ollama_model,
                    host=settings.ollama_host if ollama_client is None else None,
                    client=ollama_client,
                )
            progress.emit(
                "route",
                (
                    f"의도={preferred.intent} "
                    f"conf={preferred.confidence:.2f} ({preferred.source})"
                ),
            )
        except Exception as exc:
            progress.emit(
                "route", f"의도 분류 실패 → 규칙: {type(exc).__name__}"
            )
            preferred = None

    if preferred and preferred.intent in {"guide", "coverage", "out_of_scope"}:
        from llm2sql.guide_qa import _is_coverage_question

        guide = try_guide(question)
        # coverage 강제 문구는 실제로 전국/범위 질문일 때만 (오분류 방지)
        if (
            guide is None
            and preferred.intent == "coverage"
            and _is_coverage_question(question)
        ):
            from llm2sql.guide_qa import _coverage_text

            progress.emit("route", "자료 범위 안내")
            answer = _coverage_text()
            emit_text_chunks(answer, on_token)
            return {
                "ok": True,
                "answer": answer,
                "sql": None,
                "tables": [],
                "rows": [],
                "row_count": 0,
                "route": "guide_coverage",
                "error": None,
                "steps": progress.steps,
            }
        if guide is not None:
            progress.emit("route", f"안내 응답 ({guide.intent})")
            progress.emit("answer", "역할·제한·범위 안내 완료")
            emit_text_chunks(guide.answer, on_token)
            return {
                "ok": True,
                "answer": guide.answer,
                "sql": None,
                "tables": [],
                "rows": [],
                "row_count": 0,
                "route": guide.intent,
                "error": None,
                "steps": progress.steps,
            }
        # coverage로 오분류됐지만 범위 질문이 아니면 메타/본경로로 계속
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
            progress.emit("route", f"안내 응답 ({guide.intent})")
            progress.emit("answer", "역할·제한·범위 안내 완료")
            emit_text_chunks(guide.answer, on_token)
            return {
                "ok": True,
                "answer": guide.answer,
                "sql": None,
                "tables": [],
                "rows": [],
                "row_count": 0,
                "route": guide.intent,
                "error": None,
                "steps": progress.steps,
            }

    owns_conn = conn is None
    effective = _expand_followup_question(question, session)
    if effective != question.strip():
        progress.emit("route", f"후속 기준 병합: {effective}")
    try:
        if owns_conn:
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
            assert conn is not None
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
        result = {
            "ok": False,
            "answer": answer,
            "sql": None,
            "tables": [],
            "rows": [],
            "row_count": 0,
            "route": None,
            "error": f"{type(exc).__name__}: {exc}",
        }
    result["steps"] = progress.steps
    before_offer = str(result.get("answer") or "")
    result = attach_chart_offer(result, question=effective)
    # 스트리밍된 본문 뒤에 차트 제안 문구만 추가 전송
    if (
        result.get("chart_offer")
        and on_token is not None
        and str(result.get("answer") or "").startswith(before_offer)
        and len(str(result.get("answer") or "")) > len(before_offer)
    ):
        emit_text_chunks(str(result["answer"])[len(before_offer) :], on_token)
    if session is not None and result.get("ok"):
        # 독립 새 질문이면 이전 focus를 끊고 새 맥락으로 갱신
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

    if intent == "rank_compare":
        progress.emit("route", "선호 의도: 최고 건물 비교")
        ranked = answer_rank_compare(
            conn,
            question,
            model=settings.ollama_model,
            host=settings.ollama_host if ollama_client is None else None,
            client=ollama_client,
            on_token=on_token,
        )
        if ranked is None:
            return None
        return {
            "ok": True,
            "answer": ranked.answer,
            "sql": ranked.sql,
            "tables": ranked.tables,
            "rows": ranked.rows,
            "row_count": len(ranked.rows),
            "route": ranked.intent,
            "error": None,
        }

    if intent == "usage_overview":
        progress.emit("route", "선호 의도: 용도 구성 설명")
        usage_ov = answer_usage_overview_question(
            conn,
            question,
            model=settings.ollama_model,
            host=settings.ollama_host if ollama_client is None else None,
            client=ollama_client,
            on_token=on_token,
            force=True,
        )
        if usage_ov is None:
            return None
        return {
            "ok": True,
            "answer": usage_ov.answer,
            "sql": usage_ov.sql,
            "tables": usage_ov.tables,
            "rows": usage_ov.rows,
            "row_count": len(usage_ov.rows),
            "route": usage_ov.intent,
            "error": None,
        }

    if intent == "profile":
        progress.emit("route", "선호 의도: 건물 특징/비교")
        profile = answer_profile_question(
            conn,
            question,
            model=settings.ollama_model,
            host=settings.ollama_host if ollama_client is None else None,
            client=ollama_client,
            on_token=on_token,
            force=True,
        )
        if profile is None:
            return None
        return {
            "ok": True,
            "answer": profile.answer,
            "sql": profile.sql,
            "tables": profile.tables,
            "rows": profile.rows,
            "row_count": len(profile.rows),
            "route": profile.intent,
            "error": None,
        }

    if intent == "meta":
        progress.emit("route", "선호 의도: 메타데이터")
        meta = answer_metadata_question(conn, question, force=True)
        if meta is None:
            return None
        emit_text_chunks(meta.answer, on_token)
        return {
            "ok": True,
            "answer": meta.answer,
            "sql": None,
            "tables": meta.tables,
            "rows": meta.rows,
            "row_count": len(meta.rows),
            "route": meta.intent,
            "error": None,
        }

    if intent == "clarify":
        progress.emit("route", "선호 의도: 모호성 확인")
        clarify = check_ambiguity(conn, question)
        if clarify is None:
            return None
        emit_text_chunks(clarify.answer, on_token)
        return {
            "ok": True,
            "answer": clarify.answer,
            "sql": None,
            "tables": [],
            "rows": clarify.options,
            "row_count": len(clarify.options),
            "route": clarify.intent,
            "ambiguous_terms": clarify.ambiguous_terms,
            "error": None,
        }

    return None


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
        return {
            "ok": True,
            "answer": follow.answer,
            "sql": follow.sql,
            "tables": follow.tables,
            "rows": follow.rows,
            "row_count": len(follow.rows),
            "route": follow.intent,
            "error": None,
        }

    # LLM/하이브리드 의도 우선 디스패치 (실패 시 기존 규칙 체인으로 폴백)
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

    if is_rank_compare_question(question):
        progress.emit("route", "복수 지역 최고 건물 비교로 판단")
        progress.emit("answer", "최고 건물 비교 답변 생성")
        ranked = answer_rank_compare(
            conn,
            question,
            model=settings.ollama_model,
            host=settings.ollama_host if ollama_client is None else None,
            client=ollama_client,
            on_token=on_token,
        )
        if ranked is not None:
            progress.emit("answer", "최고 건물 비교 완료")
            return {
                "ok": True,
                "answer": ranked.answer,
                "sql": ranked.sql,
                "tables": ranked.tables,
                "rows": ranked.rows,
                "row_count": len(ranked.rows),
                "route": ranked.intent,
                "error": None,
            }
        progress.emit("route", "최고 건물 비교 매칭 실패 → 계속 진행")

    if is_usage_overview_question(question):
        progress.emit("route", "건물 용도 구성 설명 질의로 판단")
        progress.emit("answer", "용도 분포 자연어 생성")
        usage_ov = answer_usage_overview_question(
            conn,
            question,
            model=settings.ollama_model,
            host=settings.ollama_host if ollama_client is None else None,
            client=ollama_client,
            on_token=on_token,
        )
        if usage_ov is not None:
            progress.emit(
                "profile",
                "용도 상위 집계 완료",
                tables=usage_ov.tables,
                sql=usage_ov.sql,
            )
            progress.emit("answer", "한국어 용도 설명 완료")
            return {
                "ok": True,
                "answer": usage_ov.answer,
                "sql": usage_ov.sql,
                "tables": usage_ov.tables,
                "rows": usage_ov.rows,
                "row_count": len(usage_ov.rows),
                "route": usage_ov.intent,
                "error": None,
            }
        progress.emit("route", "용도 구성 설명 매칭 실패 → 계속 진행")

    if is_profile_question(question):
        progress.emit("route", "건물 특징 요약 질의로 판단")
        progress.emit("answer", "특징 요약 자연어 생성")
        profile = answer_profile_question(
            conn,
            question,
            model=settings.ollama_model,
            host=settings.ollama_host if ollama_client is None else None,
            client=ollama_client,
            on_token=on_token,
        )
        if profile is not None:
            progress.emit(
                "profile",
                "속성 기반 집계 요약 완료",
                tables=profile.tables,
                sql=profile.sql,
            )
            progress.emit("answer", "한국어 특징 답변 완료")
            return {
                "ok": True,
                "answer": profile.answer,
                "sql": profile.sql,
                "tables": profile.tables,
                "rows": profile.rows,
                "row_count": len(profile.rows),
                "route": profile.intent,
                "error": None,
            }
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
            return {
                "ok": True,
                "answer": meta.answer,
                "sql": None,
                "tables": meta.tables,
                "rows": meta.rows,
                "row_count": len(meta.rows),
                "route": meta.intent,
                "error": None,
            }
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
        return {
            "ok": True,
            "answer": clarify.answer,
            "sql": None,
            "tables": [],
            "rows": clarify.options,
            "row_count": len(clarify.options),
            "route": clarify.intent,
            "ambiguous_terms": clarify.ambiguous_terms,
            "error": None,
        }

    progress.emit("route", "규칙 라우터 매칭 시도")
    routed = try_route(question, conn=conn)
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
        progress.emit("sql", "라우터 SQL 확정", sql=routed.sql)
        progress.emit("execute", "DB 조회 실행")
        try:
            rows = execute_query(
                conn, routed.sql, default_limit=settings.default_limit
            )
        except Exception as exc:
            progress.emit("error", f"실행 실패: {type(exc).__name__}")
            answer = format_failure(question, error=exc, sql=routed.sql)
            emit_text_chunks(answer, on_token)
            return {
                "ok": False,
                "answer": answer,
                "sql": routed.sql,
                "tables": [],
                "rows": [],
                "row_count": 0,
                "route": routed.intent,
                "error": f"{type(exc).__name__}: {exc}",
            }
        progress.emit(
            "result",
            f"조회 완료 ({len(rows)}행)",
            row_count=len(rows),
        )
        progress.emit("answer", "LLM 한국어 답변 생성")
        answer = format_success(
            question,
            sql=routed.sql,
            rows=rows,
            row_count=len(rows),
            route=routed.intent,
            model=settings.ollama_model,
            host=settings.ollama_host if ollama_client is None else None,
            client=ollama_client,
            on_token=on_token,
        )
        progress.emit("answer", "한국어 답변 생성 완료")
        return {
            "ok": True,
            "answer": answer,
            "sql": routed.sql,
            "tables": [],
            "rows": rows,
            "row_count": len(rows),
            "route": routed.intent,
            "error": None,
        }

    progress.emit("route", "라우트 미매칭 → RAG+LLM 경로")
    progress.emit("schema", "스키마 검색(임베딩 RAG)")
    retrieved = retrieve_schema(
        conn,
        question,
        embed_model=settings.ollama_embed_model,
        host=settings.ollama_host if ollama_client is None else None,
        client=ollama_client,
        top_k=settings.schema_top_k,
        include_sample_values=settings.include_sample_values,
    )
    tables = retrieved.get("tables") or []
    progress.emit(
        "schema",
        f"스키마 확보 ({len(tables)}개 테이블)",
        tables=tables,
    )
    schema_text = retrieved["schema_text"]
    table_map, column_map = load_name_maps(conn)
    spatial_intent = any(k in question for k in _SPATIAL_INTENT)
    place = extract_place_token(question)
    few_shot = build_few_shot_for_question(
        question,
        top_k=settings.example_top_k,
        embed_model=settings.ollama_embed_model,
        host=settings.ollama_host if ollama_client is None else None,
        client=ollama_client,
    )
    progress.emit("schema", f"few-shot 예제 검색 (top_k={settings.example_top_k})")
    sql: str | None = None
    max_retries = max(1, settings.sql_max_retries)

    try:
        progress.emit("llm", "SQL 생성 (Ollama)")
        sql = _gen_sql(
            question,
            schema_text,
            settings,
            ollama_client=ollama_client,
            few_shot=few_shot,
        )
        sql = _normalize_sql(sql, table_map, column_map, question=question)
        progress.emit("sql", "SQL 초안 정규화 완료", sql=sql)

        if spatial_intent and not _has_spatial_sql(sql):
            progress.emit("llm", "공간 조건 누락 → 재생성")
            sql = _gen_sql(
                question,
                schema_text + "\n\n" + spatial_fewshot(place),
                settings,
                ollama_client=ollama_client,
                few_shot=few_shot,
                error_feedback=(
                    "Previous SQL missed PostGIS predicates.\n"
                    + spatial_fewshot(place)
                ),
            )
            sql = _normalize_sql(sql, table_map, column_map, question=question)
            progress.emit("sql", "공간 SQL 재생성 완료", sql=sql)

        if (
            spatial_intent
            and place
            and place.endswith("동")
            and "건물" in question
            and ("건수" in question or "개수" in question or "몇" in question)
            and not _has_spatial_sql(sql)
        ):
            sql = building_in_dong_count_sql(place)
            progress.emit("sql", "동 경계 템플릿 SQL 적용", sql=sql)

        pre_diag = validate_sql_preexec(
            question,
            sql,
            conn=conn if settings.use_explain else None,
            default_limit=settings.default_limit,
            use_explain=settings.use_explain,
        )
        if pre_diag:
            progress.emit("validate", f"사전 진단: {pre_diag}")
            sql = _gen_sql(
                question,
                schema_text,
                settings,
                ollama_client=ollama_client,
                few_shot=few_shot,
                error_feedback=pre_diag,
            )
            sql = _normalize_sql(sql, table_map, column_map, question=question)
            progress.emit("sql", "진단 반영 재생성 완료", sql=sql)
        else:
            progress.emit("validate", "사전 진단 통과 (domain/sqlglot/explain)")

        retries = 0
        rows: list[dict[str, Any]] = []
        while True:
            progress.emit("execute", "DB 조회 실행")
            try:
                rows = execute_query(
                    conn, sql, default_limit=settings.default_limit
                )
                break
            except Exception as exc:
                conn.rollback()
                retries += 1
                progress.emit(
                    "error",
                    f"실행 오류 (재시도 {retries}/{max_retries}): {type(exc).__name__}",
                )
                if retries >= max_retries:
                    raise
                progress.emit("llm", "오류 피드백으로 SQL 재생성")
                sql = _gen_sql(
                    question,
                    schema_text,
                    settings,
                    ollama_client=ollama_client,
                    few_shot=few_shot,
                    error_feedback=(
                        f"{type(exc).__name__}: {exc}\n"
                        "Use physical table/column names only "
                        '(e.g. table "AL_D010_26_20250704", column "geometry").\n'
                        'District name filters must use "A4" (법정동명), not "A3".\n'
                        + (spatial_fewshot(place) if spatial_intent else "")
                    ),
                )
                sql = _normalize_sql(sql, table_map, column_map, question=question)
                if spatial_intent and place and not _has_spatial_sql(sql):
                    sql = building_in_dong_count_sql(place)
                progress.emit("sql", "재생성 SQL 확정", sql=sql)

        progress.emit(
            "result",
            f"조회 완료 ({len(rows)}행)",
            row_count=len(rows),
        )
        post_diag = diagnose_sql(question, sql, row_count=len(rows))
        if post_diag and len(rows) == 0 and retries < max_retries:
            progress.emit("validate", f"빈 결과 진단: {post_diag}")
            progress.emit("llm", "빈 결과 보정 재생성")
            sql = _gen_sql(
                question,
                schema_text,
                settings,
                ollama_client=ollama_client,
                few_shot=few_shot,
                error_feedback=(
                    f"Query returned 0 rows. Likely issues:\n{post_diag}\n"
                    "Rewrite using AL_D010 + A4 LIKE for gu filters when applicable."
                ),
            )
            sql = _normalize_sql(sql, table_map, column_map, question=question)
            progress.emit("execute", "보정 SQL 재실행")
            rows = execute_query(
                conn, sql, default_limit=settings.default_limit
            )
            progress.emit(
                "result",
                f"재조회 완료 ({len(rows)}행)",
                row_count=len(rows),
            )

        progress.emit("answer", "LLM 한국어 답변 생성")
        answer = format_success(
            question,
            sql=sql,
            rows=rows,
            row_count=len(rows),
            route=None,
            model=settings.ollama_model,
            host=settings.ollama_host if ollama_client is None else None,
            client=ollama_client,
            on_token=on_token,
        )
        progress.emit("answer", "한국어 답변 생성 완료")
        return {
            "ok": True,
            "answer": answer,
            "sql": sql,
            "tables": tables,
            "rows": rows,
            "row_count": len(rows),
            "route": None,
            "diagnostics": post_diag or pre_diag,
            "error": None,
        }
    except Exception as exc:
        progress.emit("error", f"실패: {type(exc).__name__}: {exc}")
        answer = format_failure(question, error=exc, sql=sql)
        emit_text_chunks(answer, on_token)
        return {
            "ok": False,
            "answer": answer,
            "sql": sql,
            "tables": retrieved.get("tables", []),
            "rows": [],
            "row_count": 0,
            "route": None,
            "error": f"{type(exc).__name__}: {exc}",
        }
