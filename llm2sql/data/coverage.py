"""업로드된 공간 테이블을 질의 엔진(메타·임베딩·D198 구 맵)에 연결한다."""

from __future__ import annotations

from typing import Any

from llm2sql.config import Settings
from llm2sql.data import catalog
from llm2sql.data.names import parse_al_table_name, split_schema_table
from llm2sql.db import connect
from llm2sql.domain import (
    D198_BY_GU,
    gu_from_pnu_code,
    set_d198_coverage,
)


def discover_d198_coverage(settings: Settings) -> dict[str, str]:
    """public 스키마의 AL_D198_* 테이블을 구별로 최신 날짜만 남긴다."""
    schema = settings.map_schema or "public"
    with connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_type = 'BASE TABLE'
                  AND table_name LIKE 'AL\\_D198\\_%%' ESCAPE '\\'
                """,
                (schema,),
            )
            names = [str(row["table_name"]) for row in cur.fetchall()]
    best: dict[str, tuple[str, str]] = {}
    for name in names:
        parsed = parse_al_table_name(name)
        if parsed is None or parsed.get("data_code") != "AL_D198":
            continue
        gu = gu_from_pnu_code(parsed["pnu_code"])
        if not gu:
            continue
        date = parsed["update_date"]
        prev = best.get(gu)
        if prev is None or date > prev[0]:
            best[gu] = (date, name)
    return {gu: table for gu, (_date, table) in best.items()}


def refresh_dataset_coverage(settings: Settings) -> dict[str, str]:
    """DB에 있는 D198을 질의 라우팅 맵에 반영. 실패·빈 결과는 기존 맵 유지."""
    try:
        discovered = discover_d198_coverage(settings)
    except Exception:
        return dict(D198_BY_GU)
    if not discovered:
        return dict(D198_BY_GU)
    set_d198_coverage(discovered)
    return dict(D198_BY_GU)


def register_uploaded_dataset(settings: Settings, table_name: str) -> dict[str, Any]:
    """Shapefile 업로드 직후: 메타 채우기 → 스키마 임베딩 → D198 커버리지."""
    return sync_dataset_after_change(settings, table_name, auto_metadata=True)


def sync_dataset_after_change(
    settings: Settings,
    table_name: str | None = None,
    *,
    auto_metadata: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "metadata": False,
        "embedding": False,
        "d198_coverage": {},
        "message": "",
    }
    if table_name:
        if auto_metadata:
            try:
                result["metadata"] = _auto_fill_metadata(settings, table_name)
            except Exception:
                result["metadata"] = False
        try:
            result["embedding"] = _upsert_embedding(settings, table_name)
        except Exception:
            result["embedding"] = False
    result["d198_coverage"] = refresh_dataset_coverage(settings)
    if table_name:
        short = table_name.split(".")[-1]
        from llm2sql.domain import gu_from_d198_table

        gu = gu_from_d198_table(short)
        if gu:
            result["message"] = (
                f"{gu} 용도별건물({short})이 질의 엔진에 연결되었습니다."
            )
        elif result["metadata"]:
            result["message"] = f"{short} 메타데이터가 자동 등록되었습니다."
    return result


def _auto_fill_metadata(settings: Settings, table_name: str) -> bool:
    parsed = catalog.parse_table_code(settings, table_name)
    if parsed is None:
        return False
    data_code = str(parsed.get("data_code") or "")
    category = ""
    if data_code in {"AL_D198", "AL_D010"}:
        category = "건물"
    elif data_code == "AL_D060":
        category = "산업단지"
    table_meta = {
        "display_name": parsed.get("display_name") or "",
        "description": parsed.get("description") or "",
        "category": category,
    }
    columns = parsed.get("column_metadata") or {}
    catalog.update_table_metadata(settings, table_name, table_meta, columns)
    return True


def _upsert_embedding(settings: Settings, table_name: str) -> bool:
    from llm2sql.schema_retriever import upsert_catalog_embedding

    _, table = split_schema_table(table_name, settings.map_schema or "public")
    with connect(settings.database_url) as conn:
        upsert_catalog_embedding(
            conn,
            table,
            embed_model=settings.ollama_embed_model,
            host=settings.ollama_host,
        )
        conn.commit()
    return True
