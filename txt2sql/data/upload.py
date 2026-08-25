"""Shapefile ZIP → PostGIS + GeoServer (llm2_geodb shapefile_uploader 대응)."""

from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from txt2sql.config import Settings
from txt2sql.data.names import is_protected_table, table_from_shapefile
from txt2sql.map.geoserver import GeoServerClient

TARGET_EPSG = 4326
CHUNK_SIZE = 1000
_ENCODINGS = ("utf-8", "euc-kr", "cp949", "iso-8859-1")


def process_zip_upload(
    settings: Settings,
    *,
    filename: str,
    content: bytes,
) -> dict[str, Any]:
    if not (filename or "").lower().endswith(".zip"):
        raise ValueError("Shapefile ZIP 파일만 업로드할 수 있습니다.")
    if not content:
        raise ValueError("파일이 비어 있습니다.")

    with tempfile.TemporaryDirectory(prefix="txt2sql_shp_") as tmp:
        zip_path = Path(tmp) / "upload.zip"
        zip_path.write_bytes(content)
        extract_dir = Path(tmp) / "extracted"
        extract_dir.mkdir()
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)
        except zipfile.BadZipFile as exc:
            raise ValueError("잘못된 ZIP 파일입니다.") from exc

        shp = _find_shp(extract_dir)
        if shp is None:
            raise ValueError("ZIP 파일에 SHP 파일이 없습니다.")
        table_name = table_from_shapefile(shp.name)
        if is_protected_table(table_name):
            raise ValueError("이 테이블명은 업로드할 수 없습니다.")
        rows = _upload_shapefile(settings, shp, table_name)
        geoserver_ok = _register_geoserver(settings, table_name)
        wired: dict[str, Any] = {}
        try:
            from txt2sql.data.coverage import register_uploaded_dataset

            wired = register_uploaded_dataset(settings, table_name)
        except Exception:
            wired = {}
        message = f"업로드 성공: {table_name} ({rows}건)"
        if not geoserver_ok:
            message += ". GeoServer 레이어 등록은 실패했거나 건너뛰었습니다."
        extra = str(wired.get("message") or "").strip()
        if extra:
            message += f". {extra}"
        elif wired.get("d198_coverage"):
            message += ". 질의 엔진 커버리지를 갱신했습니다."
        return {
            "ok": True,
            "table_name": table_name,
            "rows": rows,
            "geoserver": geoserver_ok,
            "wired": wired,
            "message": message,
        }


def _find_shp(root: Path) -> Path | None:
    found: list[Path] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".shp") and not name.startswith("."):
                found.append(Path(dirpath) / name)
    if not found:
        return None
    found.sort(key=lambda p: len(p.parts))
    return found[0]


def _upload_shapefile(settings: Settings, shp_path: Path, table_name: str) -> int:
    try:
        import geopandas as gpd
        from sqlalchemy import create_engine
    except ImportError as exc:
        raise RuntimeError(
            "geopandas가 필요합니다. `uv sync` 후 다시 시도하세요."
        ) from exc

    encoding, gdf = _read_shapefile(shp_path)
    if gdf is None:
        raise ValueError("Shapefile을 읽지 못했습니다.")
    if gdf.crs is not None:
        try:
            if gdf.crs.to_epsg() != TARGET_EPSG:
                gdf = gdf.to_crs(epsg=TARGET_EPSG)
        except Exception:
            gdf = gdf.to_crs(epsg=TARGET_EPSG)
    if getattr(gdf, "geometry", None) is None:
        raise ValueError("Shapefile에 geometry가 없습니다.")
    gdf = _convert_to_utf8(gdf, encoding)
    schema = settings.map_schema or "public"
    engine = create_engine(_sqlalchemy_url(settings.database_url))
    total = len(gdf)
    for start in range(0, max(total, 1), CHUNK_SIZE):
        chunk = gdf.iloc[start : start + CHUNK_SIZE]
        chunk.to_postgis(
            name=table_name,
            con=engine,
            schema=schema,
            if_exists="replace" if start == 0 else "append",
            index=False,
        )
    engine.dispose()
    return total


def _read_shapefile(shp_path: Path) -> tuple[str, Any]:
    import geopandas as gpd

    last_error: Exception | None = None
    for encoding in _ENCODINGS:
        try:
            gdf = gpd.read_file(shp_path, encoding=encoding)
            return encoding, gdf
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
        except Exception as exc:
            last_error = exc
            if "encoding" in str(exc).lower():
                continue
            try:
                return encoding, gpd.read_file(shp_path)
            except Exception as inner:
                last_error = inner
    if last_error:
        raise ValueError(f"Shapefile 읽기 실패: {last_error}") from last_error
    raise ValueError("Shapefile 읽기 실패")


def _convert_to_utf8(gdf: Any, source_encoding: str) -> Any:
    if (source_encoding or "").lower() == "utf-8":
        return gdf
    import pandas as pd

    for col in gdf.columns:
        if col == "geometry":
            continue
        if gdf[col].dtype == "object":
            try:
                gdf[col] = gdf[col].astype(str).where(pd.notna(gdf[col]), None)
            except Exception:
                continue
    return gdf


def _sqlalchemy_url(database_url: str) -> str:
    url = database_url or ""
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    return url


def _register_geoserver(settings: Settings, table_name: str) -> bool:
    client = GeoServerClient(settings)
    if not client.enabled:
        return False
    return client.ensure_featuretype(table_name, title=table_name)
