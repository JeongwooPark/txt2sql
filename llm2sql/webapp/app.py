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
from llm2sql.geoserver import GeoServerClient
from llm2sql.map_publish import (
    delete_published_layer,
    fetch_layer_attributes,
    is_safe_layer_name,
    start_cleanup_scheduler,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
_SENTINEL = object()


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    session_id: str | None = None


class LayerAttributesRequest(BaseModel):
    layer: str = Field(..., min_length=1)
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)


def create_app() -> FastAPI:
    engine_holder: dict[str, Any] = {"engine": None}
    sessions: dict[str, SessionContext] = {}
    ask_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        engine_holder["engine"] = Llm2SqlEngine.from_env()
        try:
            start_cleanup_scheduler(engine_holder["engine"].settings)
        except Exception:
            pass
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
                        session_id=session_id,
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

    @app.get("/api/map/status")
    def map_status() -> dict[str, Any]:
        settings = get_engine().settings
        if not settings.geoserver_url:
            return {
                "enabled": False,
                "online": False,
                "message": "GeoServer가 설정되지 않았습니다. 채팅만 사용할 수 있습니다.",
            }
        client = GeoServerClient(settings)
        online = client.check()
        return {
            "enabled": True,
            "online": online,
            "workspace": client.workspace,
            "wms_url": client.wms_url(),
            "wfs_url": client.wfs_url(),
            "message": None
            if online
            else "GeoServer에 연결할 수 없습니다. 채팅은 유지됩니다.",
        }

    @app.get("/api/map/layers")
    def map_layers() -> dict[str, Any]:
        settings = get_engine().settings
        client = GeoServerClient(settings)
        if not client.enabled or not client.check():
            return {"layers": [], "online": False}
        return {"layers": client.catalog_layers(), "online": True}

    @app.post("/api/map/attributes")
    def map_attributes(body: LayerAttributesRequest) -> dict[str, Any]:
        if not is_safe_layer_name(body.layer):
            raise HTTPException(status_code=400, detail="허용되지 않은 레이어입니다.")
        try:
            data = fetch_layer_attributes(
                get_engine().settings,
                body.layer,
                limit=body.limit,
                offset=body.offset,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"ok": True, **data}

    @app.delete("/api/map/layer/{name}")
    def map_delete_layer(name: str) -> dict[str, Any]:
        if not is_safe_layer_name(name):
            raise HTTPException(status_code=400, detail="허용되지 않은 레이어입니다.")
        try:
            delete_published_layer(get_engine().settings, name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"ok": True}

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
