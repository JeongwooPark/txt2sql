from __future__ import annotations

import os
from dataclasses import dataclass, replace

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    database_url: str
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen3:latest"
    ollama_embed_model: str = "mxbai-embed-large"
    schema_top_k: int = 5
    default_limit: int = 100

    def with_overrides(self, **kwargs: object) -> Settings:
        return replace(self, **kwargs)

    @classmethod
    def from_mapping(cls, data: dict[str, object]) -> Settings:
        database_url = str(data.get("database_url") or data.get("DATABASE_URL") or "").strip()
        if not database_url:
            raise ValueError("database_url / DATABASE_URL이 필요합니다.")
        return cls(
            database_url=database_url,
            ollama_host=str(
                data.get("ollama_host")
                or data.get("OLLAMA_HOST")
                or "http://localhost:11434"
            ).strip(),
            ollama_model=str(
                data.get("ollama_model")
                or data.get("OLLAMA_MODEL")
                or "qwen3:latest"
            ).strip(),
            ollama_embed_model=str(
                data.get("ollama_embed_model")
                or data.get("OLLAMA_EMBED_MODEL")
                or "mxbai-embed-large"
            ).strip(),
            schema_top_k=int(
                data.get("schema_top_k") or data.get("SCHEMA_TOP_K") or 5
            ),
            default_limit=int(
                data.get("default_limit") or data.get("DEFAULT_LIMIT") or 100
            ),
        )


def load_settings(*, dotenv: bool = True) -> Settings:
    if dotenv:
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
