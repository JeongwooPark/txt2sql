from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    database_url: str
    ollama_host: str
    ollama_model: str
    ollama_embed_model: str
    schema_top_k: int
    default_limit: int


def load_settings() -> Settings:
    load_dotenv()

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise ValueError(
            "DATABASE_URL이 설정되지 않았습니다. .env 파일을 확인하세요."
        )

    return Settings(
        database_url=database_url,
        ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434").strip(),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen3:latest").strip(),
        ollama_embed_model=os.getenv(
            "OLLAMA_EMBED_MODEL", "mxbai-embed-large"
        ).strip(),
        schema_top_k=int(os.getenv("SCHEMA_TOP_K", "5")),
        default_limit=int(os.getenv("DEFAULT_LIMIT", "100")),
    )
