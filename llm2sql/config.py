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
    example_top_k: int = 3
    sql_max_retries: int = 3
    use_explain: bool = True
    include_sample_values: bool = True
    # rules | hybrid | llm — 의도 라우팅 방식 (개발·정확도 우선 기본: hybrid)
    intent_mode: str = "hybrid"
    intent_confidence_threshold: float = 0.55

    def with_overrides(self, **kwargs: object) -> Settings:
        return replace(self, **kwargs)

    @classmethod
    def from_mapping(cls, data: dict[str, object]) -> Settings:
        database_url = str(data.get("database_url") or data.get("DATABASE_URL") or "").strip()
        if not database_url:
            raise ValueError("database_url / DATABASE_URL이 필요합니다.")

        def _bool(key: str, env_key: str, default: bool) -> bool:
            raw = data.get(key, data.get(env_key, default))
            if isinstance(raw, bool):
                return raw
            return str(raw).strip().lower() in {"1", "true", "yes", "on"}

        intent_mode = str(
            data.get("intent_mode")
            or data.get("INTENT_MODE")
            or "hybrid"
        ).strip().lower()
        if intent_mode not in {"rules", "hybrid", "llm"}:
            intent_mode = "hybrid"

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
            example_top_k=int(
                data.get("example_top_k") or data.get("EXAMPLE_TOP_K") or 3
            ),
            sql_max_retries=int(
                data.get("sql_max_retries") or data.get("SQL_MAX_RETRIES") or 3
            ),
            use_explain=_bool("use_explain", "USE_EXPLAIN", True),
            include_sample_values=_bool(
                "include_sample_values", "INCLUDE_SAMPLE_VALUES", True
            ),
            intent_mode=intent_mode,
            intent_confidence_threshold=float(
                data.get("intent_confidence_threshold")
                or data.get("INTENT_CONFIDENCE_THRESHOLD")
                or 0.55
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

    def _env_bool(name: str, default: bool) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    intent_mode = os.getenv("INTENT_MODE", "hybrid").strip().lower()
    if intent_mode not in {"rules", "hybrid", "llm"}:
        intent_mode = "hybrid"

    return Settings(
        database_url=database_url,
        ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434").strip(),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen3:latest").strip(),
        ollama_embed_model=os.getenv(
            "OLLAMA_EMBED_MODEL", "mxbai-embed-large"
        ).strip(),
        schema_top_k=int(os.getenv("SCHEMA_TOP_K", "5")),
        default_limit=int(os.getenv("DEFAULT_LIMIT", "100")),
        example_top_k=int(os.getenv("EXAMPLE_TOP_K", "3")),
        sql_max_retries=int(os.getenv("SQL_MAX_RETRIES", "3")),
        use_explain=_env_bool("USE_EXPLAIN", True),
        include_sample_values=_env_bool("INCLUDE_SAMPLE_VALUES", True),
        intent_mode=intent_mode,
        intent_confidence_threshold=float(
            os.getenv("INTENT_CONFIDENCE_THRESHOLD", "0.55")
        ),
    )
