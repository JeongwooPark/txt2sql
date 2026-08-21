"""FastAPI 기반 버블 챗봇 (SSE 스트리밍)."""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from queue import Empty, Queue
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from llm2sql import Llm2SqlEngine, SessionContext

STATIC_DIR = Path(__file__).resolve().parent / "static"
_SENTINEL = object()


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    session_id: str | None = None


def create_app() -> FastAPI:
    engine_holder: dict[str, Any] = {"engine": None}
    sessions: dict[str, SessionContext] = {}
    ask_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        engine_holder["engine"] = Llm2SqlEngine.from_env()
        try:
            yield
        finally:
            engine = engine_holder.get("engine")
            if engine is not None:
                engine.close()

    app = FastAPI(title="llm2sql Chat", version="0.1.4", lifespan=lifespan)

    def get_engine() -> Llm2SqlEngine:
        engine = engine_holder.get("engine")
        if engine is None:
            raise HTTPException(
                status_code=503, detail="엔진이 아직 준비되지 않았습니다."
            )
        return engine

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/session")
    def new_session() -> dict[str, str]:
        sid = uuid.uuid4().hex
        sessions[sid] = SessionContext()
        return {"session_id": sid}

    @app.post("/api/chat")
    async def chat(body: ChatRequest) -> StreamingResponse:
        question = body.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="질문이 비어 있습니다.")

        engine = get_engine()
        session_id = body.session_id or uuid.uuid4().hex
        session = sessions.setdefault(session_id, SessionContext())
        event_q: Queue[Any] = Queue()

        def on_progress(
            stage: str, message: str, detail: dict[str, Any] | None
        ) -> None:
            event_q.put(
                {
                    "type": "progress",
                    "stage": stage,
                    "message": message,
                    "detail": detail or {},
                }
            )

        def on_token(text: str) -> None:
            if text:
                event_q.put({"type": "token", "text": text})

        def worker() -> None:
            try:
                with ask_lock:
                    result = engine.ask(
                        question,
                        session=session,
                        on_progress=on_progress,
                        on_token=on_token,
                    )
                payload = result.to_dict()
                rows = payload.get("rows") or []
                if isinstance(rows, list) and len(rows) > 20:
                    payload["rows"] = rows[:20]
                    payload["rows_truncated"] = len(rows) - 20
                event_q.put(
                    {
                        "type": "done",
                        "session_id": session_id,
                        "result": payload,
                    }
                )
            except Exception as exc:
                event_q.put(
                    {
                        "type": "error",
                        "session_id": session_id,
                        "message": f"{type(exc).__name__}: {exc}",
                    }
                )
            finally:
                event_q.put(_SENTINEL)

        threading.Thread(target=worker, daemon=True).start()

        async def event_stream() -> AsyncIterator[bytes]:
            yield _sse({"type": "ready", "session_id": session_id})
            while True:
                try:
                    item = await asyncio.to_thread(event_q.get, True, 0.25)
                except Empty:
                    yield b": ping\n\n"
                    continue
                if item is _SENTINEL:
                    break
                yield _sse(item)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    return app


def _sse(payload: dict[str, Any]) -> bytes:
    data = json.dumps(payload, ensure_ascii=False, default=str)
    return f"data: {data}\n\n".encode("utf-8")


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run(
        "llm2sql.webapp.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
