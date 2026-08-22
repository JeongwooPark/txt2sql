"""데이터 관리 REST API."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from llm2sql.config import Settings
from llm2sql.data import catalog, upload as shp_upload


class TableMetaIn(BaseModel):
    display_name: str = ""
    description: str = ""
    category: str = ""


class ColumnMetaIn(BaseModel):
    display_name: str = ""
    description: str = ""
    data_type: str = ""
    unit: str = ""


class UpdateMetadataRequest(BaseModel):
    table_name: str = Field(..., min_length=1, max_length=200)
    table_metadata: TableMetaIn = Field(default_factory=TableMetaIn)
    column_metadata: dict[str, ColumnMetaIn] = Field(default_factory=dict)
    new_table_name: str | None = None


def create_data_router(get_settings: Callable[[], Settings]) -> APIRouter:
    router = APIRouter(prefix="/api/data", tags=["data"])

    @router.get("/tables")
    def list_tables() -> dict[str, Any]:
        tables = catalog.list_spatial_tables(get_settings())
        return {"ok": True, "tables": tables}

    @router.get("/tables/{table_name}/structure")
    def table_structure(table_name: str) -> dict[str, Any]:
        try:
            structure = catalog.get_table_structure(get_settings(), table_name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"ok": True, "structure": structure}

    @router.get("/tables/{table_name}/metadata")
    def table_metadata(table_name: str) -> dict[str, Any]:
        settings = get_settings()
        try:
            metadata = catalog.get_table_metadata(settings, table_name)
            comments = catalog.get_database_comments(settings, table_name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"ok": True, "metadata": metadata, "database_comments": comments}

    @router.get("/tables/{table_name}/display-name")
    def table_display_name(table_name: str) -> dict[str, Any]:
        try:
            name = catalog.get_table_display_name(get_settings(), table_name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "display_name": name}

    @router.get("/tables/{table_name}/parse")
    def parse_table(table_name: str) -> dict[str, Any]:
        try:
            parsed = catalog.parse_table_code(get_settings(), table_name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        if parsed is None:
            raise HTTPException(
                status_code=400,
                detail="테이블 코드를 해석할 수 없습니다. (예: AL_D198_26_20250704)",
            )
        return {"ok": True, "parsed_metadata": parsed}

    @router.post("/metadata")
    def update_metadata(body: UpdateMetadataRequest) -> dict[str, Any]:
        settings = get_settings()
        table_name = body.table_name
        columns = {
            key: value.model_dump() for key, value in body.column_metadata.items()
        }
        try:
            if body.new_table_name:
                table_name = catalog.rename_table(
                    settings, table_name, body.new_table_name
                )
            catalog.update_table_metadata(
                settings,
                table_name,
                body.table_metadata.model_dump(),
                columns,
            )
            try:
                from llm2sql.data.coverage import sync_dataset_after_change

                sync_dataset_after_change(
                    settings, table_name, auto_metadata=False
                )
            except Exception:
                pass
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        message = "메타데이터가 업데이트되었습니다."
        payload: dict[str, Any] = {"ok": True, "message": message}
        if body.new_table_name:
            payload["new_table_name"] = table_name
            payload["message"] = "테이블명 변경 및 메타데이터가 업데이트되었습니다."
        return payload

    @router.post("/upload")
    async def upload_shapefile(
        shapefile: UploadFile = File(...),
    ) -> dict[str, Any]:
        filename = shapefile.filename or "upload.zip"
        content = await shapefile.read()
        try:
            result = shp_upload.process_zip_upload(
                get_settings(), filename=filename, content=content
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return result

    return router
