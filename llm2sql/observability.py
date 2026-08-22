"""역할별 모델 pin, 공식 벤치 :latest 금지, 질의 트레이스 마스킹."""

from __future__ import annotations

import re
from typing import Any

_URL_CRED = re.compile(r"(postgres(?:ql)?://)([^:/@]+):([^@/]+)@", re.IGNORECASE)
_KV_SECRET = re.compile(
    r"(password|passwd|pwd|secret|api[_-]?key|database_url)\s*[=:]\s*([^\s,;]+)",
    re.IGNORECASE,
)


def is_unpinned_latest(model: str) -> bool:
    name = (model or "").strip().lower()
    return name.endswith(":latest") or name == "latest"


def official_benchmark_allowed(plan_model: str, embed_model: str) -> tuple[bool, str]:
    if is_unpinned_latest(plan_model):
        return False, "plan model uses :latest"
    if is_unpinned_latest(embed_model):
        return False, "embed model uses :latest"
    return True, "ok"


def mask_text(value: str) -> str:
    text = _URL_CRED.sub(r"\1\2:***@", value)
    text = _KV_SECRET.sub(lambda match: f"{match.group(1)}=***", text)
    return text


def mask_value(value: Any) -> Any:
    if isinstance(value, str):
        return mask_text(value)
    if isinstance(value, dict):
        return mask_mapping(value)
    if isinstance(value, list):
        return [mask_value(item) for item in value]
    return value


def mask_mapping(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        lowered = key.lower()
        if lowered in {"password", "passwd", "secret", "database_url", "geoserver_password"}:
            out[key] = "***"
        else:
            out[key] = mask_value(value)
    return out
