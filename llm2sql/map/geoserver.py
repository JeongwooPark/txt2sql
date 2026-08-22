"""GeoServer REST 클라이언트 (자격 증명은 Settings/env)."""

from __future__ import annotations

import base64
import json
import math
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import unquote, urlparse

from llm2sql.config import Settings

_TEMP_PREFIX = "temp_"


class GeoServerClient:
    """워크스페이스·데이터스토어·피처타입 등록/삭제."""

    def __init__(self, settings: Settings) -> None:
        self.base_url = (settings.geoserver_url or "").rstrip("/")
        self.user = settings.geoserver_user
        self.password = settings.geoserver_password
        self.workspace = settings.geoserver_workspace or "korDB"
        self.datastore = settings.geoserver_datastore or "llm2sql_map"
        self.map_schema = settings.map_schema or "llm2sql_map"
        self.database_url = settings.database_url
        self._timeout = 8

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    def wms_url(self) -> str:
        return f"{self.base_url}/wms"

    def wfs_url(self) -> str:
        return f"{self.base_url}/wfs"

    def qualified_layer(self, layer: str) -> str:
        return f"{self.workspace}:{layer}"

    def check(self) -> bool:
        if not self.enabled:
            return False
        status, _ = self._request(
            "GET", f"{self.base_url}/rest/about/status", timeout=3
        )
        return status == 200

    def list_workspace_layers(self) -> list[str]:
        status, body = self._request(
            "GET",
            f"{self.base_url}/rest/workspaces/{self.workspace}/layers",
        )
        if status != 200:
            return []
        try:
            data = json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return []
        layers = data.get("layers", {}).get("layer") or []
        if isinstance(layers, dict):
            layers = [layers]
        names: list[str] = []
        for item in layers:
            name = str(item.get("name") or "")
            if name:
                names.append(name)
        return names

    def catalog_layers(self) -> list[dict[str, Any]]:
        """KorDB 카탈로그용: 임시 분석 레이어를 제외한 워크스페이스 레이어."""
        out: list[dict[str, Any]] = []
        for name in self.list_workspace_layers():
            short = name.split(":")[-1]
            if short.startswith(_TEMP_PREFIX):
                continue
            out.append(
                {
                    "name": short,
                    "qualified": self.qualified_layer(short),
                    "wms_url": self.wms_url(),
                    "wfs_url": self.wfs_url(),
                    "extent": self.layer_latlon_extent(short) or [],
                }
            )
        return out

    def layer_latlon_extent(self, layer: str) -> list[float] | None:
        """레이어 lat/lon bbox. 줌에 쓸 EPSG:4326 [minx, miny, maxx, maxy]."""
        short = (layer or "").split(":")[-1]
        if not short:
            return None
        status, body = self._request(
            "GET",
            f"{self.base_url}/rest/workspaces/{self.workspace}/layers/{short}",
            timeout=3,
        )
        href = ""
        if status == 200:
            try:
                data = json.loads(body.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                data = {}
            href = str(
                ((data.get("layer") or {}).get("resource") or {}).get("href") or ""
            )
        if href:
            status, body = self._request("GET", href, timeout=3)
            if status == 200:
                try:
                    parsed = parse_latlon_bbox(json.loads(body.decode("utf-8") or "{}"))
                except json.JSONDecodeError:
                    parsed = None
                if parsed:
                    return parsed
        status, body = self._request(
            "GET",
            f"{self.base_url}/rest/workspaces/{self.workspace}"
            f"/datastores/{self.datastore}/featuretypes/{short}",
            timeout=3,
        )
        if status != 200:
            return None
        try:
            return parse_latlon_bbox(json.loads(body.decode("utf-8") or "{}"))
        except json.JSONDecodeError:
            return None

    def ensure_workspace(self) -> bool:
        status, body = self._request(
            "GET", f"{self.base_url}/rest/workspaces/{self.workspace}"
        )
        if status == 200:
            return True
        status, body = self._request(
            "POST",
            f"{self.base_url}/rest/workspaces",
            {"workspace": {"name": self.workspace}},
        )
        return status in {200, 201}

    def ensure_datastore(self) -> bool:
        if not self.ensure_workspace():
            return False
        status, _ = self._request(
            "GET",
            f"{self.base_url}/rest/workspaces/{self.workspace}/datastores/{self.datastore}",
        )
        if status == 200:
            return True
        params = _postgis_params(self.database_url, self.map_schema)
        if params is None:
            return False
        payload = {
            "dataStore": {
                "name": self.datastore,
                "type": "PostGIS",
                "enabled": True,
                "connectionParameters": {
                    "entry": [{"@key": k, "$": v} for k, v in params.items()]
                },
            }
        }
        status, _ = self._request(
            "POST",
            f"{self.base_url}/rest/workspaces/{self.workspace}/datastores",
            payload,
        )
        return status in {200, 201}

    def create_featuretype(
        self,
        layer_name: str,
        table_name: str,
        *,
        srs: str = "EPSG:4326",
        title: str | None = None,
    ) -> bool:
        if not self.ensure_datastore():
            return False
        payload = {
            "featureType": {
                "name": layer_name,
                "nativeName": table_name,
                "title": title or layer_name,
                "srs": srs,
                "enabled": True,
            }
        }
        url = (
            f"{self.base_url}/rest/workspaces/{self.workspace}"
            f"/datastores/{self.datastore}/featuretypes"
        )
        status, _ = self._request("POST", url, payload)
        return status in {200, 201}

    def ensure_featuretype(
        self,
        table_name: str,
        *,
        srs: str = "EPSG:4326",
        title: str | None = None,
    ) -> bool:
        """레이어가 없으면 만들고, 이미 있으면 성공으로 본다."""
        if self.create_featuretype(table_name, table_name, srs=srs, title=title):
            return True
        short = {name.split(":")[-1] for name in self.list_workspace_layers()}
        return table_name in short

    def delete_layer(self, layer_name: str) -> bool:
        short = layer_name.split(":")[-1]
        qualified = self.qualified_layer(short)
        status, _ = self._request(
            "DELETE",
            f"{self.base_url}/rest/layers/{qualified}?recurse=true",
        )
        if status not in {200, 204, 404}:
            status, _ = self._request(
                "DELETE",
                f"{self.base_url}/rest/layers/{short}?recurse=true",
            )
        ft_url = (
            f"{self.base_url}/rest/workspaces/{self.workspace}"
            f"/datastores/{self.datastore}/featuretypes/{short}?recurse=true"
        )
        self._request("DELETE", ft_url)
        return status in {200, 204, 404}

    def _request(
        self,
        method: str,
        url: str,
        json_body: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> tuple[int, bytes]:
        data = None
        headers = {"Accept": "application/json"}
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        if self.user:
            token = base64.b64encode(
                f"{self.user}:{self.password}".encode("utf-8")
            ).decode("ascii")
            req.add_header("Authorization", f"Basic {token}")
        try:
            with urllib.request.urlopen(
                req, timeout=timeout or self._timeout
            ) as resp:
                return int(resp.status), resp.read()
        except urllib.error.HTTPError as exc:
            return int(exc.code), exc.read() if exc.fp else b""
        except Exception:
            return 0, b""


def parse_latlon_bbox(payload: dict[str, Any] | None) -> list[float] | None:
    """GeoServer featureType JSON에서 EPSG:4326 bbox를 꺼낸다."""
    if not isinstance(payload, dict):
        return None
    ft = payload.get("featureType") or payload.get("coverage") or payload
    if not isinstance(ft, dict):
        return None
    box = ft.get("latLonBoundingBox")
    if not isinstance(box, dict):
        return None
    try:
        ext = [
            float(box["minx"]),
            float(box["miny"]),
            float(box["maxx"]),
            float(box["maxy"]),
        ]
    except (KeyError, TypeError, ValueError):
        return None
    minx, miny, maxx, maxy = ext
    if not all(math.isfinite(v) for v in ext):
        return None
    if maxx <= minx or maxy <= miny:
        return None
    if abs(minx) <= 1 and abs(miny) <= 1 and abs(maxx) <= 1 and abs(maxy) <= 1:
        return None
    return ext


def _postgis_params(database_url: str, schema: str) -> dict[str, str] | None:
    parsed = urlparse(database_url)
    if not parsed.hostname or not parsed.path:
        return None
    dbname = unquote(parsed.path.lstrip("/").split("/")[0])
    if not dbname:
        return None
    return {
        "host": parsed.hostname,
        "port": str(parsed.port or 5432),
        "database": dbname,
        "schema": schema,
        "user": unquote(parsed.username or ""),
        "passwd": unquote(parsed.password or ""),
        "dbtype": "postgis",
        "Expose primary keys": "true",
    }
