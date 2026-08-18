"""Ollama 호출 공통 헬퍼."""

from __future__ import annotations

from typing import Any

import ollama

from llm2sql.progress import TokenCallback


def resolve_client(*, host: str | None, client: Any | None) -> Any:
    if client is not None:
        return client
    if not host:
        raise ValueError("host 또는 client가 필요합니다.")
    return ollama.Client(host=host)


def chat(
    *,
    model: str,
    messages: list[dict[str, str]],
    host: str | None = None,
    client: Any | None = None,
    temperature: float = 0.2,
    stream: bool = False,
    on_token: TokenCallback | None = None,
) -> str:
    """Ollama chat. stream이면 토큰마다 on_token을 호출하고 전체 문자열을 반환."""
    client = resolve_client(host=host, client=client)
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "options": {"temperature": temperature},
    }
    if stream:
        kwargs["stream"] = True

    try:
        response = client.chat(**kwargs, think=False)
    except TypeError:
        response = client.chat(**kwargs)

    if not stream:
        return response["message"]["content"]

    parts: list[str] = []
    for chunk in response:
        message = chunk.get("message") if isinstance(chunk, dict) else None
        if isinstance(message, dict):
            content = message.get("content") or ""
        elif message is not None:
            content = getattr(message, "content", None) or ""
        else:
            content = ""
        if not content:
            continue
        parts.append(content)
        if on_token is not None:
            on_token(content)
    return "".join(parts)
