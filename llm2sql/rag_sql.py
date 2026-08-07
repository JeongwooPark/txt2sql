"""규칙 라우터를 우회하는 RAG+LLM SQL 경로 (벤치마크/비교용)."""

from __future__ import annotations

from typing import Any

import psycopg

from llm2sql.config import Settings
from llm2sql.db import execute_query
from llm2sql.schema_retriever import retrieve_schema
from llm2sql.spatial_templates import (
    building_in_dong_count_sql,
    extract_place_token,
    spatial_fewshot,
)
from llm2sql.sql_fix import load_name_maps, rewrite_display_names
from llm2sql.sql_generator import build_few_shot_for_question, generate_sql
from llm2sql.sql_validator import diagnose_sql, validate_sql_preexec
from llm2sql.intent_router import fix_common_sql_mistakes

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
    *,
    question: str | None = None,
) -> str:
    sql = rewrite_display_names(sql, table_map, column_map)
    return fix_common_sql_mistakes(sql, question=question)


def run_rag_sql(
    question: str,
    settings: Settings,
    *,
    conn: psycopg.Connection,
    ollama_client: Any | None = None,
    skip_answer: bool = True,
) -> dict[str, Any]:
    """Schema RAG + 동적 few-shot + SQLGlot/EXPLAIN + 실행 재시도.

    의도 라우터/안내 QA를 건너뛰어 모델 SQL 생성 능력을 공정 비교한다.
    """
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

    def _gen(error_feedback: str | None = None, schema_extra: str = "") -> str:
        return generate_sql(
            question,
            schema_text + schema_extra,
            model=settings.ollama_model,
            host=settings.ollama_host if ollama_client is None else None,
            client=ollama_client,
            error_feedback=error_feedback,
            few_shot=few_shot,
        )

    sql: str | None = None
    retries = 0
    max_retries = max(1, settings.sql_max_retries)
    pre_diag: str | None = None
    post_diag: str | None = None
    rows: list[dict[str, Any]] = []

    try:
        sql = _normalize_sql(
            _gen(), table_map, column_map, question=question
        )

        if spatial_intent and not _has_spatial_sql(sql):
            sql = _normalize_sql(
                _gen(
                    error_feedback=(
                        "Previous SQL missed PostGIS predicates.\n"
                        + spatial_fewshot(place)
                    ),
                    schema_extra="\n\n" + spatial_fewshot(place),
                ),
                table_map,
                column_map,
                question=question,
            )

        if (
            spatial_intent
            and place
            and place.endswith("동")
            and "건물" in question
            and ("건수" in question or "개수" in question or "몇" in question)
            and not _has_spatial_sql(sql)
        ):
            sql = building_in_dong_count_sql(place)

        pre_diag = validate_sql_preexec(
            question,
            sql,
            conn=conn if settings.use_explain else None,
            default_limit=settings.default_limit,
            use_explain=settings.use_explain,
        )
        if pre_diag:
            sql = _normalize_sql(
                _gen(error_feedback=pre_diag),
                table_map,
                column_map,
                question=question,
            )

        while True:
            try:
                rows = execute_query(
                    conn, sql, default_limit=settings.default_limit
                )
                break
            except Exception as exc:
                conn.rollback()
                retries += 1
                if retries >= max_retries:
                    raise
                sql = _normalize_sql(
                    _gen(
                        error_feedback=(
                            f"{type(exc).__name__}: {exc}\n"
                            "Use physical table/column names only "
                            '(e.g. table "AL_D010_26_20250704", column "geometry").\n'
                            'District name filters must use "A4" (법정동명), not "A3".\n'
                            + (spatial_fewshot(place) if spatial_intent else "")
                        )
                    ),
                    table_map,
                    column_map,
                    question=question,
                )
                if spatial_intent and place and not _has_spatial_sql(sql):
                    sql = building_in_dong_count_sql(place)

        post_diag = diagnose_sql(question, sql, row_count=len(rows))
        if post_diag and len(rows) == 0 and retries < max_retries:
            sql = _normalize_sql(
                _gen(
                    error_feedback=(
                        f"Query returned 0 rows. Likely issues:\n{post_diag}\n"
                        "Rewrite using AL_D010 + A4 LIKE for gu filters when applicable."
                    )
                ),
                table_map,
                column_map,
                question=question,
            )
            rows = execute_query(
                conn, sql, default_limit=settings.default_limit
            )

        return {
            "ok": True,
            "answer": None if skip_answer else "",
            "sql": sql,
            "tables": tables,
            "rows": rows,
            "row_count": len(rows),
            "route": "rag_sql",
            "diagnostics": post_diag or pre_diag,
            "retries": retries,
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "answer": None,
            "sql": sql,
            "tables": tables,
            "rows": [],
            "row_count": 0,
            "route": "rag_sql",
            "diagnostics": pre_diag,
            "retries": retries,
            "error": f"{type(exc).__name__}: {exc}",
        }
