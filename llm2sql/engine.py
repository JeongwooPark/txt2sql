"""재사용 가능한 llm2sql 엔진."""

from __future__ import annotations

from typing import Any

import ollama
import psycopg
from psycopg.rows import dict_row

from llm2sql.config import Settings, load_settings
from llm2sql.pipeline import run_ask
from llm2sql.progress import ProgressCallback, TokenCallback
from llm2sql.session import SessionContext
from llm2sql.types import AskResult


class Llm2SqlEngine:
    """자연어 GIS 질의 엔진.

    앱에서 인스턴스를 한 번 만들고 `ask()`를 반복 호출하세요.
    DB 연결과 Ollama 클라이언트를 재사용합니다.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._conn: psycopg.Connection | None = None
        self._ollama: Any | None = None
        self._closed = False

    @classmethod
    def from_env(cls, *, dotenv: bool = True) -> Llm2SqlEngine:
        return cls(load_settings(dotenv=dotenv))

    @classmethod
    def from_settings(cls, settings: Settings) -> Llm2SqlEngine:
        return cls(settings)

    @classmethod
    def from_mapping(cls, data: dict[str, object]) -> Llm2SqlEngine:
        return cls(Settings.from_mapping(data))

    def ask(
        self,
        question: str,
        *,
        session: SessionContext | None = None,
        session_id: str | None = None,
        on_progress: ProgressCallback | None = None,
        on_token: TokenCallback | None = None,
        include_map: bool = True,
    ) -> AskResult:
        if self._closed:
            raise RuntimeError("엔진이 이미 close() 되었습니다.")
        self._ensure_resources()
        assert self._conn is not None
        result = run_ask(
            question,
            self.settings,
            conn=self._conn,
            ollama_client=self._ollama,
            on_progress=on_progress,
            on_token=on_token,
            session=session,
            session_id=session_id,
            include_map=include_map,
        )
        return AskResult.from_dict(result)

    def _ensure_resources(self) -> None:
        if self._ollama is None:
            self._ollama = ollama.Client(host=self.settings.ollama_host)
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(
                self.settings.database_url,
                row_factory=dict_row,
            )
            try:
                from llm2sql.data.coverage import refresh_dataset_coverage

                refresh_dataset_coverage(self.settings)
            except Exception:
                pass

    @property
    def ollama_client(self) -> Any:
        self._ensure_resources()
        return self._ollama

    def close(self) -> None:
        if self._conn is not None and not self._conn.closed:
            self._conn.close()
        self._conn = None
        self._ollama = None
        self._closed = True

    def __enter__(self) -> Llm2SqlEngine:
        self._ensure_resources()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
