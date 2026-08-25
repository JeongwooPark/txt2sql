"""지도 발행·WMS 시각화 스모크.

맵 UI가 쓰는 경로와 동일하게 include_map=True 로 질의하고,
GeoServer WMS GetMap PNG에 실제 픽셀이 그려지는지 확인한다.
"""

from __future__ import annotations

import json
import struct
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from txt2sql import Txt2SqlEngine, SessionContext
from txt2sql.config import load_settings
from txt2sql.map.publish import cleanup_session_layers

WEB = "http://127.0.0.1:8000"

CASES = [
    {
        "q": "구서역포르투나를 찾아라",
        "min_features": 1,
        "max_features": 5,
        "forbid_kind": "boundary",
    },
    {
        "q": "구서1동의 아파트는?",
        "min_features": 10,
        "forbid_kind": "boundary",
    },
    {
        "q": "구서동에서 건물면적이 가장 큰 아파트는?",
        "min_features": 1,
        "max_features": 5,
        "forbid_kind": "boundary",
    },
    {
        "q": "구서1동과 구서2동의 단독주택의 특성을 비교하라",
        "min_features": 2,
        "forbid_kind": "boundary",
    },
]


def _get_json(path: str) -> dict:
    with urllib.request.urlopen(f"{WEB}{path}", timeout=12) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _png_chunks(data: bytes):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("PNG가 아닙니다.")
    i = 8
    while i + 8 <= len(data):
        length = struct.unpack(">I", data[i : i + 4])[0]
        ctype = data[i + 4 : i + 8]
        chunk = data[i + 8 : i + 8 + length]
        yield ctype, chunk
        i += 12 + length


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def png_painted_pixels(data: bytes) -> int:
    """투명·완전흰색이 아닌 PNG 픽셀 수."""
    width = height = bit_depth = color_type = None
    idat = b""
    for ctype, chunk in _png_chunks(data):
        if ctype == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", chunk[:10])
        elif ctype == b"IDAT":
            idat += chunk
    if width is None or bit_depth != 8 or color_type not in {2, 6}:
        return 0
    channels = 3 if color_type == 2 else 4
    raw = zlib.decompress(idat)
    stride = width * channels
    prev = bytearray(stride)
    painted = 0
    i = 0
    for _y in range(height):
        ftype = raw[i]
        i += 1
        row = bytearray(raw[i : i + stride])
        i += stride
        for x in range(stride):
            left = row[x - channels] if x >= channels else 0
            up = prev[x]
            ul = prev[x - channels] if x >= channels else 0
            if ftype == 1:
                row[x] = (row[x] + left) & 255
            elif ftype == 2:
                row[x] = (row[x] + up) & 255
            elif ftype == 3:
                row[x] = (row[x] + ((left + up) // 2)) & 255
            elif ftype == 4:
                row[x] = (row[x] + _paeth(left, up, ul)) & 255
        for p in range(0, stride, channels):
            r, g, b = row[p], row[p + 1], row[p + 2]
            a = row[p + 3] if channels == 4 else 255
            if a < 16:
                continue
            if r > 245 and g > 245 and b > 245:
                continue
            painted += 1
        prev = row
    return painted


def wms_getmap(info: dict) -> bytes:
    extent = info.get("extent") or [129.0, 35.1, 129.2, 35.3]
    minx, miny, maxx, maxy = [float(v) for v in extent]
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.1.1",
        "REQUEST": "GetMap",
        "LAYERS": f"{info['workspace']}:{info['layer']}",
        "STYLES": "",
        "SRS": "EPSG:4326",
        "BBOX": f"{minx},{miny},{maxx},{maxy}",
        "WIDTH": "512",
        "HEIGHT": "512",
        "FORMAT": "image/png",
        "TRANSPARENT": "true",
    }
    url = f"{info['wms_url']}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def _assert_map(case: dict, result) -> dict:
    mapped = result.map or {}
    assert result.ok, f"질의 실패: {case['q']} {result.error}"
    assert mapped.get("available"), (
        f"지도 미발행: {case['q']} {mapped.get('error') or mapped}"
    )
    n = int(mapped.get("feature_count") or 0)
    assert n >= case["min_features"], (
        f"{case['q']}: feature_count={n} < {case['min_features']}"
    )
    if "max_features" in case:
        assert n <= case["max_features"], (
            f"{case['q']}: feature_count={n} > {case['max_features']}"
        )
    kind = mapped.get("kind")
    if case.get("forbid_kind"):
        assert kind != case["forbid_kind"], (
            f"{case['q']}: 경계 레이어가 나오면 안 됩니다 (kind={kind})"
        )
    geom = (mapped.get("geom_type") or "").upper()
    assert "POINT" not in geom or "POLY" in geom or n <= 5, geom
    png = wms_getmap(mapped)
    painted = png_painted_pixels(png)
    assert painted > 20, f"{case['q']}: WMS PNG에 도형이 거의 없음 ({painted}px)"
    return {
        "q": case["q"],
        "route": result.route,
        "layer": mapped.get("layer"),
        "kind": kind,
        "features": n,
        "geom": mapped.get("geom_type"),
        "painted": painted,
        "title": mapped.get("title"),
    }


def main() -> int:
    status = _get_json("/api/map/status")
    assert status.get("enabled") and status.get("online"), status
    print("PASS map-status", status.get("wms_url"))

    with urllib.request.urlopen(f"{WEB}/map", timeout=8) as resp:
        html = resp.read().decode("utf-8")
    assert 'data-ui="map"' in html
    assert "/static/js/map/main.js" in html
    print("PASS map-html")

    layers = _get_json("/api/map/layers")
    catalog = layers.get("layers") or []
    assert layers.get("online") and len(catalog) >= 1, layers
    print("PASS kordb-catalog", len(catalog))

    session_id = uuid.uuid4().hex
    session = SessionContext()
    reports = []
    with Txt2SqlEngine.from_env() as engine:
        guide = engine.ask("기능 알려줘", include_map=True)
        assert guide.ok
        assert not (guide.map or {}).get("available"), guide.map
        print("PASS no-map-guide")

        for case in CASES:
            result = engine.ask(
                case["q"],
                session=session,
                session_id=session_id,
                include_map=True,
            )
            report = _assert_map(case, result)
            reports.append(report)
            print(
                "PASS",
                report["q"],
                "route=",
                report["route"],
                "n=",
                report["features"],
                "kind=",
                report["kind"],
                "painted=",
                report["painted"],
            )

    settings = load_settings()
    cleanup_session_layers(settings, session_id)
    print("PASS cleanup", session_id)
    print("map smoke OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("FAIL", type(exc).__name__, exc)
        raise
