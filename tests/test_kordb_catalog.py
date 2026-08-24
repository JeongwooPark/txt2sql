"""KorDB field catalog artifacts: present, no secrets, core tables covered."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "docs" / "kordb_catalog.json"
MD_PATH = ROOT / "docs" / "kordb_필드카탈로그.md"

CORE = (
    "AL_D010_26_20250704",
    "AL_D198_26260_20250115",
    "AL_D198_26410_20250115",
    "AL_D060_00_20250804",
    "BND_ADM_DONG_PG",
    "TL_KODIS_BAS_26_202507",
)


def test_catalog_files_exist() -> None:
    assert JSON_PATH.is_file()
    assert MD_PATH.is_file()


def test_catalog_json_has_core_tables_and_no_password() -> None:
    raw = JSON_PATH.read_text(encoding="utf-8")
    assert "postgresql://" in raw
    assert ":***@" in raw
    lowered = raw.lower()
    assert "password" not in lowered or "비밀번호" in raw
    cat = json.loads(raw)
    names = [t["name"] for t in cat["tables"]]
    assert names == list(CORE)
    assert all(not t.get("missing") for t in cat["tables"])
    d010 = next(t for t in cat["tables"] if t["name"] == CORE[0])
    cols = {c["physical_name"] for c in d010["columns"]}
    assert {"A0", "A9", "A14", "geometry"} <= cols
    d198 = next(t for t in cat["tables"] if t["name"] == CORE[1])
    d198_cols = {c["physical_name"] for c in d198["columns"]}
    assert {"A25", "A29", "A34", "geometry"} <= d198_cols
    assert cat["relationships"]
    assert cat["nl_aliases"]["busan_gu_codes"]["금정구"] == "26410"


def test_download_routes_registered() -> None:
    from llm2sql.webapp.app import app

    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/download/kordb-catalog.json" in paths
    assert "/download/kordb-catalog.md" in paths
