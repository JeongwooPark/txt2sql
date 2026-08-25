from txt2sql.config import Settings
from txt2sql.map.geoserver import GeoServerClient


def _client() -> GeoServerClient:
    return GeoServerClient(
        Settings(
            database_url="postgresql://x:x@localhost:5432/x",
            geoserver_url="http://geoserver.example",
            geoserver_workspace="korDB",
        )
    )


def test_style_exists_404(monkeypatch) -> None:
    client = _client()

    def send(method, url, data, headers, timeout):
        assert method == "GET"
        return 404, b""

    monkeypatch.setattr(client, "_send", send)
    assert client.style_exists("choropleth__demo__field") is False


def test_create_and_update_style(monkeypatch) -> None:
    client = _client()
    calls: list[tuple[str, str]] = []

    def send(method, url, data, headers, timeout):
        calls.append((method, url))
        if method == "GET":
            return 404, b""
        if method == "POST":
            return 201, b""
        if method == "PUT":
            assert headers["Content-Type"] == "application/vnd.ogc.sld+xml"
            return 200, b""
        return 500, b""

    monkeypatch.setattr(client, "_send", send)
    assert client.create_style("choropleth__demo__field", "<StyledLayerDescriptor/>")
    assert any(m == "POST" for m, _ in calls)
    assert any(m == "PUT" for m, _ in calls)


def test_refuses_unmanaged_style() -> None:
    client = _client()
    assert client.create_style("polygon", "<sld/>") is False
    assert client.delete_style("generic") is False
    assert client.style_exists("generic") is False


def test_assign_style(monkeypatch) -> None:
    client = _client()

    def send(method, url, data, headers, timeout):
        if method == "GET":
            return 200, b'{"layer": {"name": "adm_urban_area_per_capita", "defaultStyle": {"name": "polygon"}}}'
        if method == "PUT":
            return 200, b""
        return 500, b""

    monkeypatch.setattr(client, "_send", send)
    assert client.assign_style_to_layer(
        "adm_urban_area_per_capita",
        "choropleth__adm_urban_area_per_capita__urban_pc",
    )


def test_delete_style_404(monkeypatch) -> None:
    client = _client()
    monkeypatch.setattr(client, "_send", lambda *a, **k: (404, b""))
    assert client.delete_style("choropleth__demo__field") is True


def test_5xx_failure(monkeypatch) -> None:
    client = _client()
    monkeypatch.setattr(client, "_send", lambda *a, **k: (500, b"boom"))
    assert client.update_style("choropleth__demo__field", "<sld/>") is False
    assert client.assign_style_to_layer("layer", "choropleth__x__y") is False


def test_existing_json_request_still_works(monkeypatch) -> None:
    client = _client()
    seen = {}

    def send(method, url, data, headers, timeout):
        seen["method"] = method
        seen["headers"] = headers
        seen["data"] = data
        return 200, b'{"workspace": {"name": "korDB"}}'

    monkeypatch.setattr(client, "_send", send)
    status, _ = client._request(
        "POST",
        "http://geoserver.example/rest/workspaces",
        {"workspace": {"name": "korDB"}},
    )
    assert status == 200
    assert seen["headers"]["Content-Type"] == "application/json"
    assert b"korDB" in seen["data"]
