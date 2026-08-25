from fastapi import FastAPI
from fastapi.testclient import TestClient

from txt2sql.config import Settings
from txt2sql.map.router import create_map_router


def _client() -> TestClient:
    settings = Settings(
        database_url="postgresql://x:x@localhost:5432/x",
        geoserver_url="",
    )
    app = FastAPI()
    app.include_router(create_map_router(lambda: settings))
    return TestClient(app)


def test_palettes_endpoint() -> None:
    res = _client().get("/api/map/choropleth/palettes")
    assert res.status_code == 200
    data = res.json()
    assert "YlOrRd" in data["palettes"]
    assert "Viridis" in data["palettes"]


def test_invalid_layer_rejected() -> None:
    res = _client().get("/api/map/choropleth/fields", params={"layer": "not valid!"})
    assert res.status_code == 400


def test_protected_table_rejected() -> None:
    res = _client().get("/api/map/choropleth/fields", params={"layer": "spatial_ref_sys"})
    assert res.status_code == 400


def test_missing_layer_param() -> None:
    res = _client().get("/api/map/choropleth/fields", params={"layer": "  "})
    assert res.status_code == 400


def test_stats_invalid_payload() -> None:
    res = _client().post("/api/map/choropleth/stats", json={"layer": "", "field": "x"})
    assert res.status_code == 422


def test_classify_invalid_hex() -> None:
    res = _client().post(
        "/api/map/choropleth/preview",
        json={
            "layer": "spatial_ref_sys",
            "field": "urban_pc",
            "null_color": "red",
        },
    )
    assert res.status_code == 400


def test_reset_invalid_layer() -> None:
    res = _client().post(
        "/api/map/choropleth/reset",
        json={"layer": "nope!"},
    )
    assert res.status_code == 400
