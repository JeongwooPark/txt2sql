"""llm_schema_catalog 요약을 갱신하고 mxbai-embed-large(1024d)로 재임베딩합니다."""

from __future__ import annotations

import argparse
import sys

from llm2sql.config import load_settings
from llm2sql.db import connect
from llm2sql.schema_retriever import upsert_catalog_embedding

SPATIAL_TABLES = [
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
        default=SPATIAL_TABLES,
        help="갱신할 테이블명 (기본: 공간 테이블 세트)",
    )
    args = parser.parse_args()

    settings = load_settings()
    with connect(settings.database_url) as conn:
        # 임베딩 차원 확인
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

        for table in args.tables:
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
