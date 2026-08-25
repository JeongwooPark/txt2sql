"""llm_schema_catalog 요약을 갱신하고 mxbai-embed-large(1024d)로 재임베딩합니다.

기본은 DB의 공간 테이블·pnu_def·D198을 발견해 전부 갱신한다.
업로드 직후에도 coverage.sync_dataset_after_change가 해당 테이블만 임베딩한다.
"""

from __future__ import annotations

import argparse
import sys

from txt2sql.config import load_settings
from txt2sql.data.coverage import refresh_dataset_coverage
from txt2sql.db import connect
from txt2sql.domain import D198_TABLES
from txt2sql.schema_retriever import discover_searchable_tables, upsert_catalog_embedding

_FALLBACK_TABLES = [
    "AL_D010_26_20250704",
    "AL_D060_00_20250804",
    "AL_D198_26260_20250115",
    "AL_D198_26410_20250115",
    "BND_ADM_DONG_PG",
    "TL_KODIS_BAS_26_202507",
    "pnu_def",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh llm_schema_catalog embeddings")
    parser.add_argument(
        "--tables",
        nargs="*",
        default=None,
        help="갱신할 테이블명 (생략 시 DB에서 공간/참조 테이블을 발견)",
    )
    args = parser.parse_args()

    settings = load_settings()
    try:
        refresh_dataset_coverage(settings)
    except Exception:
        pass
    with connect(settings.database_url) as conn:
        if args.tables:
            tables = list(args.tables)
        else:
            tables = discover_searchable_tables(conn)
            if not tables:
                tables = list(dict.fromkeys([*_FALLBACK_TABLES, *D198_TABLES]))
        probe = conn.execute(
            """
            SELECT atttypmod AS dims
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relname = 'llm_schema_catalog'
              AND a.attname = 'embedding'
            """
        ).fetchone()
        print(f"catalog embedding dims: {probe['dims'] if probe else '?'}")
        print(f"embed model: {settings.ollama_embed_model}")
        print(f"tables ({len(tables)}): {', '.join(tables)}")

        for table in tables:
            print(f"refreshing {table} ...", flush=True)
            upsert_catalog_embedding(
                conn,
                table,
                embed_model=settings.ollama_embed_model,
                host=settings.ollama_host,
            )
            conn.commit()
            print(f"  ok: public.{table}")

    print("done")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
