"""요청 단위 LLM 호출 추적 (contextvar)."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Callable

Recorder = Callable[[str], None]

_recorder: ContextVar[Recorder | None] = ContextVar("llm_recorder", default=None)


_active_token: ContextVar[Token | None] = ContextVar("llm_active_token", default=None)


def activate_llm_tracking(record: Recorder) -> Token:
    token = _recorder.set(record)
    _active_token.set(token)
    return token


def deactivate_llm_tracking(token: Token) -> None:
    _recorder.reset(token)
    if _active_token.get() is token:
        _active_token.set(None)


def cleanup_llm_tracking() -> None:
    token = _active_token.get()
    if token is not None:
        deactivate_llm_tracking(token)


def notify_llm_call(purpose: str = "chat") -> None:
    rec = _recorder.get()
    if rec is not None:
        rec(purpose)
