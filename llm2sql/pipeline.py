from __future__ import annotations

from typing import Any

from llm2sql.answer import format_failure, format_success
from llm2sql.clarify_qa import check_ambiguity
from llm2sql.config import Settings
from llm2sql.db import connect, execute_query
from llm2sql.followup_qa import answer_followup, is_followup_question
from llm2sql.guide_qa import try_guide
from llm2sql.intent_router import fix_common_sql_mistakes, try_route
from llm2sql.meta_qa import answer_metadata_question, is_metadata_question
from llm2sql.profile_qa import answer_profile_question, is_profile_question
from llm2sql.progress import ProgressCallback, ProgressTracker
from llm2sql.schema_retriever import retrieve_schema
from llm2sql.session import SessionContext
from llm2sql.spatial_templates import (
    building_in_dong_count_sql,
    extract_place_token,
    spatial_fewshot,
)
from llm2sql.sql_fix import load_name_maps, rewrite_display_names
from llm2sql.sql_generator import generate_sql
from llm2sql.sql_validator import diagnose_sql

_SPATIAL_INTENT = ("안에", "내부", "속하는", "교차", "버퍼", "거리", "근처", "이내")


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
) -> str:
    sql = rewrite_display_names(sql, table_map, column_map)
    return fix_common_sql_mistakes(sql)


def ask(
    question: str,
    settings: Settings,
    *,
    on_progress: ProgressCallback | None = None,
    session: SessionContext | None = None,
) -> dict[str, Any]:
    """자연어 질문 → SQL → 실행 → 한국어 답변.

    session이 있으면 직전 결과 기반 후속 질문(그 아파트 이름은? 등)을 처리하고
    성공 시 session을 갱신한다.
    """
    progress = ProgressTracker(on_step=on_progress)
    progress.emit("start", f"질문 수신: {question.strip()}")

    # 역할/기능/제한·범위 외 안내는 DB 없이 즉시 응답
    guide = try_guide(question)
    if guide is not None:
        progress.emit("route", f"안내 응답 ({guide.intent})")
        progress.emit("answer", "역할·제한·범위 안내 완료")
        result = {
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
        return result

    try:
        result = _ask_inner(question, settings, progress, session)
    except Exception as exc:
        progress.emit("error", f"처리 중 예외: {type(exc).__name__}")
        answer = format_failure(question, error=exc, sql=None)
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
    if session is not None and result.get("ok"):
        session.update_from_result(question, result)
    return result


def _ask_inner(
    question: str,
    settings: Settings,
    progress: ProgressTracker,
    session: SessionContext | None = None,
) -> dict[str, Any]:
    with connect(settings.database_url) as conn:
        # 직전 결과 기반 후속 질문
        if is_followup_question(question, session) and session is not None:
            progress.emit("route", "후속 질문(직전 결과 참조)으로 판단")
            follow = answer_followup(conn, question, session)
            progress.emit("answer", f"후속 답변 완료 ({follow.intent})")
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

        # 데이터/속성 설명 질의 → 메타데이터 기반 답변 (SQL 조회 우회)
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

        # 의미 불분명·모호 용어 → 확인 요청 (추측 실행 방지)
        progress.emit("route", "모호성/미지 용어 점검")
        clarify = check_ambiguity(conn, question)
        if clarify is not None:
            progress.emit(
                "clarify",
                f"확인 필요: {', '.join(clarify.ambiguous_terms) or clarify.intent}",
            )
            progress.emit("answer", "확인 요청 답변 완료")
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

        # 장소·용도 특징 요약 (집계 프로필)
        if is_profile_question(question):
            progress.emit("route", "건물 특징 요약 질의로 판단")
            profile = answer_profile_question(conn, question)
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
            progress.emit("route", "특징 요약 매칭 실패 → SQL 경로")

        progress.emit("route", "규칙 라우터 매칭 시도")
        routed = try_route(question)
        if routed is not None:
            progress.emit(
                "route",
                f"라우트 적중: {routed.intent}",
                intent=routed.intent,
            )
            progress.emit("sql", "라우터 SQL 확정", sql=routed.sql)
            progress.emit("execute", "DB 조회 실행")
            try:
                rows = execute_query(
                    conn, routed.sql, default_limit=settings.default_limit
                )
            except Exception as exc:
                progress.emit("error", f"실행 실패: {type(exc).__name__}")
                answer = format_failure(
                    question, error=exc, sql=routed.sql
                )
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
            answer = format_success(
                question,
                sql=routed.sql,
                rows=rows,
                row_count=len(rows),
                route=routed.intent,
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
            host=settings.ollama_host,
            top_k=settings.schema_top_k,
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
        sql: str | None = None

        try:
            progress.emit("llm", "SQL 생성 (Ollama)")
            sql = generate_sql(
                question,
                schema_text,
                model=settings.ollama_model,
                host=settings.ollama_host,
            )
            sql = _normalize_sql(sql, table_map, column_map)
            progress.emit("sql", "SQL 초안 정규화 완료", sql=sql)

            if spatial_intent and not _has_spatial_sql(sql):
                progress.emit("llm", "공간 조건 누락 → 재생성")
                sql = generate_sql(
                    question,
                    schema_text + "\n\n" + spatial_fewshot(place),
                    model=settings.ollama_model,
                    host=settings.ollama_host,
                    error_feedback=(
                        "Previous SQL missed PostGIS predicates.\n"
                        + spatial_fewshot(place)
                    ),
                )
                sql = _normalize_sql(sql, table_map, column_map)
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

            pre_diag = diagnose_sql(question, sql)
            if pre_diag:
                progress.emit("validate", f"사전 진단: {pre_diag}")
                sql = generate_sql(
                    question,
                    schema_text,
                    model=settings.ollama_model,
                    host=settings.ollama_host,
                    error_feedback=pre_diag,
                )
                sql = _normalize_sql(sql, table_map, column_map)
                progress.emit("sql", "진단 반영 재생성 완료", sql=sql)
            else:
                progress.emit("validate", "사전 진단 통과")

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
                        f"실행 오류 (재시도 {retries}): {type(exc).__name__}",
                    )
                    if retries > 1:
                        raise
                    progress.emit("llm", "오류 피드백으로 SQL 재생성")
                    sql = generate_sql(
                        question,
                        schema_text,
                        model=settings.ollama_model,
                        host=settings.ollama_host,
                        error_feedback=(
                            f"{type(exc).__name__}: {exc}\n"
                            "Use physical table/column names only "
                            '(e.g. table "AL_D010_26_20250704", column "geometry").\n'
                            'District name filters must use "A4" (법정동명), not "A3".\n'
                            + (spatial_fewshot(place) if spatial_intent else "")
                        ),
                    )
                    sql = _normalize_sql(sql, table_map, column_map)
                    if spatial_intent and place and not _has_spatial_sql(sql):
                        sql = building_in_dong_count_sql(place)
                    progress.emit("sql", "재생성 SQL 확정", sql=sql)

            progress.emit(
                "result",
                f"조회 완료 ({len(rows)}행)",
                row_count=len(rows),
            )
            post_diag = diagnose_sql(question, sql, row_count=len(rows))
            if post_diag and len(rows) == 0 and retries < 2:
                progress.emit("validate", f"빈 결과 진단: {post_diag}")
                progress.emit("llm", "빈 결과 보정 재생성")
                sql = generate_sql(
                    question,
                    schema_text,
                    model=settings.ollama_model,
                    host=settings.ollama_host,
                    error_feedback=(
                        f"Query returned 0 rows. Likely issues:\n{post_diag}\n"
                        "Rewrite using AL_D010 + A4 LIKE for gu filters when applicable."
                    ),
                )
                sql = _normalize_sql(sql, table_map, column_map)
                progress.emit("execute", "보정 SQL 재실행")
                rows = execute_query(
                    conn, sql, default_limit=settings.default_limit
                )
                progress.emit(
                    "result",
                    f"재조회 완료 ({len(rows)}행)",
                    row_count=len(rows),
                )

            answer = format_success(
                question,
                sql=sql,
                rows=rows,
                row_count=len(rows),
                route=None,
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
