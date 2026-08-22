from __future__ import annotations

import os
from dataclasses import dataclass, replace

from dotenv import load_dotenv


def _pick(data: dict[str, object], *keys: str, default: object = "") -> object:
    for key in keys:
        val = data.get(key)
        if val not in (None, ""):
            return val
    return default


def _as_bool(raw: object, default: bool) -> bool:
    if raw is None or raw == "":
        return default
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _route_mode(raw: object) -> str:
    mode = str(raw or "optimized").strip().lower()
    return mode if mode in {"baseline", "optimized"} else "optimized"


def _semantic_plan_mode(raw: object) -> str:
    mode = str(raw or "shadow").strip().lower()
    return mode if mode in {"off", "shadow", "hybrid"} else "shadow"


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
    # baseline | optimized — 규칙 SQL early 디스패치 (벤치 후 optimized 기본)
    route_dispatch_mode: str = "optimized"
    # GeoServer (지도 시각화). URL이 비어 있으면 맵 발행을 건너뛴다.
    geoserver_url: str = ""
    geoserver_user: str = ""
    geoserver_password: str = ""
    geoserver_workspace: str = "korDB"
    geoserver_datastore: str = "KoreaDB"
    map_schema: str = "public"
    map_max_features: int = 2000
    map_wfs_max_features: int = 5000
    map_retention_hours: int = 24
    map_max_analysis_layers: int = 8
    # off | shadow | hybrid — 규칙 라우터 미적중 시 Semantic Query Plan
    semantic_plan_mode: str = "shadow"
    semantic_plan_version: str = "1.1"
    semantic_plan_max_retries: int = 1
    semantic_plan_min_quality: float = 0.85
    semantic_plan_min_contract_coverage: float = 1.0
    semantic_plan_min_slot_confidence: float = 0.85
    semantic_plan_debug: bool = False
    ollama_plan_model: str = ""
    ollama_chat_model: str = ""
    ollama_plan_digest: str = ""
    ollama_embed_digest: str = ""

    def planner_model(self) -> str:
        return (self.ollama_plan_model or self.ollama_model).strip()

    def chat_model(self) -> str:
        return (self.ollama_chat_model or self.ollama_model).strip()

    def with_overrides(self, **kwargs: object) -> Settings:
        return replace(self, **kwargs)

    @classmethod
    def from_mapping(cls, data: dict[str, object]) -> Settings:
        database_url = str(_pick(data, "database_url", "DATABASE_URL")).strip()
        if not database_url:
            raise ValueError("database_url / DATABASE_URL이 필요합니다.")

        intent_mode = str(
            _pick(data, "intent_mode", "INTENT_MODE", default="hybrid")
        ).strip().lower()
        if intent_mode not in {"rules", "hybrid", "llm"}:
            intent_mode = "hybrid"

        return cls(
            database_url=database_url,
            ollama_host=str(
                _pick(
                    data,
                    "ollama_host",
                    "OLLAMA_HOST",
                    default="http://localhost:11434",
                )
            ).strip(),
            ollama_model=str(
                _pick(data, "ollama_model", "OLLAMA_MODEL", default="qwen3:latest")
            ).strip(),
            ollama_embed_model=str(
                _pick(
                    data,
                    "ollama_embed_model",
                    "OLLAMA_EMBED_MODEL",
                    default="mxbai-embed-large",
                )
            ).strip(),
            schema_top_k=int(_pick(data, "schema_top_k", "SCHEMA_TOP_K", default=5)),
            default_limit=int(
                _pick(data, "default_limit", "DEFAULT_LIMIT", default=100)
            ),
            example_top_k=int(
                _pick(data, "example_top_k", "EXAMPLE_TOP_K", default=3)
            ),
            sql_max_retries=int(
                _pick(data, "sql_max_retries", "SQL_MAX_RETRIES", default=3)
            ),
            use_explain=_as_bool(_pick(data, "use_explain", "USE_EXPLAIN"), True),
            include_sample_values=_as_bool(
                _pick(data, "include_sample_values", "INCLUDE_SAMPLE_VALUES"),
                True,
            ),
            intent_mode=intent_mode,
            intent_confidence_threshold=float(
                _pick(
                    data,
                    "intent_confidence_threshold",
                    "INTENT_CONFIDENCE_THRESHOLD",
                    default=0.55,
                )
            ),
            route_dispatch_mode=_route_mode(
                _pick(data, "route_dispatch_mode", "ROUTE_DISPATCH_MODE")
            ),
            geoserver_url=str(
                _pick(data, "geoserver_url", "GEOSERVER_URL", default="")
            ).strip().rstrip("/"),
            geoserver_user=str(
                _pick(data, "geoserver_user", "GEOSERVER_USER", default="")
            ).strip(),
            geoserver_password=str(
                _pick(
                    data,
                    "geoserver_password",
                    "GEOSERVER_PASSWORD",
                    default="",
                )
            ),
            geoserver_workspace=str(
                _pick(
                    data,
                    "geoserver_workspace",
                    "GEOSERVER_WORKSPACE",
                    default="korDB",
                )
            ).strip()
            or "korDB",
            geoserver_datastore=str(
                _pick(
                    data,
                    "geoserver_datastore",
                    "GEOSERVER_DATASTORE",
                    default="KoreaDB",
                )
            ).strip()
            or "KoreaDB",
            map_schema=str(
                _pick(data, "map_schema", "MAP_SCHEMA", default="public")
            ).strip()
            or "public",
            map_max_features=int(
                _pick(data, "map_max_features", "MAP_MAX_FEATURES", default=2000)
            ),
            map_wfs_max_features=int(
                _pick(
                    data,
                    "map_wfs_max_features",
                    "MAP_WFS_MAX_FEATURES",
                    default=5000,
                )
            ),
            map_retention_hours=int(
                _pick(
                    data,
                    "map_retention_hours",
                    "MAP_RETENTION_HOURS",
                    default=24,
                )
            ),
            map_max_analysis_layers=int(
                _pick(
                    data,
                    "map_max_analysis_layers",
                    "MAP_MAX_ANALYSIS_LAYERS",
                    default=8,
                )
            ),
            semantic_plan_mode=_semantic_plan_mode(
                _pick(data, "semantic_plan_mode", "SEMANTIC_PLAN_MODE", default="shadow")
            ),
            semantic_plan_version=str(
                _pick(
                    data,
                    "semantic_plan_version",
                    "SEMANTIC_PLAN_VERSION",
                    default="1.1",
                )
            ).strip()
            or "1.1",
            semantic_plan_max_retries=int(
                _pick(
                    data,
                    "semantic_plan_max_retries",
                    "SEMANTIC_PLAN_MAX_RETRIES",
                    default=1,
                )
            ),
            semantic_plan_min_quality=float(
                _pick(
                    data,
                    "semantic_plan_min_quality",
                    "SEMANTIC_PLAN_MIN_QUALITY",
                    default=0.85,
                )
            ),
            semantic_plan_min_contract_coverage=float(
                _pick(
                    data,
                    "semantic_plan_min_contract_coverage",
                    "SEMANTIC_PLAN_MIN_CONTRACT_COVERAGE",
                    default=1.0,
                )
            ),
            semantic_plan_min_slot_confidence=float(
                _pick(
                    data,
                    "semantic_plan_min_slot_confidence",
                    "SEMANTIC_PLAN_MIN_SLOT_CONFIDENCE",
                    default=0.85,
                )
            ),
            semantic_plan_debug=_as_bool(
                _pick(data, "semantic_plan_debug", "SEMANTIC_PLAN_DEBUG"),
                False,
            ),
            ollama_plan_model=str(
                _pick(data, "ollama_plan_model", "OLLAMA_PLAN_MODEL", default="")
            ).strip(),
            ollama_chat_model=str(
                _pick(data, "ollama_chat_model", "OLLAMA_CHAT_MODEL", default="")
            ).strip(),
            ollama_plan_digest=str(
                _pick(data, "ollama_plan_digest", "OLLAMA_PLAN_DIGEST", default="")
            ).strip(),
            ollama_embed_digest=str(
                _pick(data, "ollama_embed_digest", "OLLAMA_EMBED_DIGEST", default="")
            ).strip(),
        )


def load_settings(*, dotenv: bool = True) -> Settings:
    if dotenv:
        load_dotenv()
    try:
        return Settings.from_mapping(dict(os.environ))
    except ValueError as exc:
        if "database_url" in str(exc).lower():
            raise ValueError(
                "DATABASE_URL이 설정되지 않았습니다. .env 파일을 확인하세요."
            ) from exc
        raise
