"""지도 시각화 REST API."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from llm2sql.config import Settings
from llm2sql.map.explain import explain_attributes
from llm2sql.map.geoserver import GeoServerClient
from llm2sql.map.labels import label_catalog_layers, labels_for_layer
from llm2sql.map.publish import (
    cleanup_session_layers,
    delete_published_layer,
    fetch_layer_attributes,
    is_safe_layer_name,
    is_safe_session_id,
)


class LayerAttributesRequest(BaseModel):
    layer: str = Field(..., min_length=1)
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)


class LayerLabelsRequest(BaseModel):
    layer: str = Field(..., min_length=1)
    columns: list[str] | None = None


class SessionCleanupRequest(BaseModel):
    session_id: str = Field(..., min_length=8, max_length=64)


class ExplainRequest(BaseModel):
    kind: Literal["identify", "table"] = "identify"
    title: str = ""
    layer: str = Field("", max_length=120)
    properties: dict[str, Any] | None = None
    columns: list[str] | None = Field(None, max_length=40)
    rows: list[dict[str, Any]] | None = Field(None, max_length=20)
    total: int | None = Field(None, ge=0, le=5_000_000)
    fields: dict[str, str] | None = None


def create_map_router(
    get_settings: Callable[[], Settings],
    *,
    get_ollama: Callable[[], Any] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/map", tags=["map"])

    @router.get("/status")
    def map_status() -> dict[str, Any]:
        settings = get_settings()
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

    @router.get("/layers")
    def map_layers() -> dict[str, Any]:
        settings = get_settings()
        client = GeoServerClient(settings)
        if not client.enabled or not client.check():
            return {"layers": [], "online": False}
        layers = label_catalog_layers(settings, client.catalog_layers())
        return {"layers": layers, "online": True}

    @router.get("/labels")
    def map_labels(layer: str, columns: str | None = None) -> dict[str, Any]:
        if not layer.strip():
            raise HTTPException(status_code=400, detail="레이어가 필요합니다.")
        col_list = None
        if columns:
            col_list = [c for c in columns.split(",") if c.strip()]
        try:
            data = labels_for_layer(
                get_settings(), layer.strip(), columns=col_list
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"ok": True, **data}

    @router.post("/labels")
    def map_labels_post(body: LayerLabelsRequest) -> dict[str, Any]:
        try:
            data = labels_for_layer(
                get_settings(),
                body.layer.strip(),
                columns=body.columns,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"ok": True, **data}

    @router.post("/attributes")
    def map_attributes(body: LayerAttributesRequest) -> dict[str, Any]:
        try:
            data = fetch_layer_attributes(
                get_settings(),
                body.layer,
                limit=body.limit,
                offset=body.offset,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"ok": True, **data}

    @router.post("/explain")
    def map_explain(body: ExplainRequest) -> dict[str, Any]:
        settings = get_settings()
        client = None
        if get_ollama is not None:
            try:
                client = get_ollama()
            except Exception:
                client = None
        try:
            data = explain_attributes(
                settings,
                kind=body.kind,
                title=body.title,
                layer=body.layer,
                properties=body.properties,
                columns=body.columns,
                rows=body.rows,
                total=body.total,
                fields=body.fields,
                client=client,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"ok": True, **data}

    @router.delete("/layer/{name}")
    def map_delete_layer(name: str) -> dict[str, Any]:
        if not is_safe_layer_name(name):
            raise HTTPException(status_code=400, detail="허용되지 않은 레이어입니다.")
        try:
            delete_published_layer(get_settings(), name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"ok": True}

    @router.post("/session/cleanup")
    def map_session_cleanup(body: SessionCleanupRequest) -> dict[str, Any]:
        if not is_safe_session_id(body.session_id):
            raise HTTPException(status_code=400, detail="허용되지 않은 세션입니다.")
        try:
            removed = cleanup_session_layers(get_settings(), body.session_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"ok": True, "removed": removed}

    return router
