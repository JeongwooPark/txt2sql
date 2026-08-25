"""Polygon 단계구분도(Choropleth) 분류 · 팔레트 · SLD 생성."""

from __future__ import annotations

import hashlib
import math
import random
import re
import xml.sax.saxutils
from typing import Any

from psycopg import sql

from txt2sql.config import Settings
from txt2sql.data.names import is_protected_table, is_safe_ident
from txt2sql.db import connect
from txt2sql.map.geoserver import GeoServerClient
from txt2sql.map.labels import MetaIndex
from txt2sql.map.publish import is_catalog_layer_name, is_safe_layer_name

MIN_CLASSES = 3
DEFAULT_CLASSES = 5
MAX_CLASSES = 9
JENKS_SAMPLE_LIMIT = 10_000
DEFAULT_NULL_COLOR = "#BDBDBD"
DEFAULT_STROKE = "#666666"
DEFAULT_STROKE_WIDTH = 0.7
DEFAULT_FILL_OPACITY = 0.8
NULL_LEGEND_LABEL = "데이터 없음"
STYLE_PREFIX = "choropleth__"
_HEX_RE = re.compile(r"^#([0-9A-Fa-f]{6})$")
_STYLE_SAFE_RE = re.compile(r"[^A-Za-z0-9_-]+")
_ID_FIELD_RE = re.compile(
    r"(^|_)(id|fid|gid|oid|pk|cd|code|sgis|objectid|ogc_fid)(_|$)",
    re.I,
)
_NUMERIC_UDT = {
    "int2",
    "int4",
    "int8",
    "float4",
    "float8",
    "numeric",
    "decimal",
    "smallint",
    "integer",
    "bigint",
    "real",
    "double precision",
}
_NUMERIC_DATA_TYPES = {
    "smallint",
    "integer",
    "bigint",
    "numeric",
    "decimal",
    "real",
    "double precision",
}
_POLYGON_TYPES = {"POLYGON", "MULTIPOLYGON"}
_METHODS = {"jenks", "equal_interval", "quantile", "manual"}

# ColorBrewer sequential palettes (3–9 classes). Viridis from matplotlib samples.
PALETTES: dict[str, dict[int, list[str]]] = {
    "Blues": {
        3: ["#deebf7", "#9ecae1", "#3182bd"],
        4: ["#eff3ff", "#bdd7e7", "#6baed6", "#2171b5"],
        5: ["#eff3ff", "#bdd7e7", "#6baed6", "#3182bd", "#08519c"],
        6: ["#eff3ff", "#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"],
        7: ["#eff3ff", "#c6dbef", "#9ecae1", "#6baed6", "#4292c6", "#2171b5", "#084594"],
        8: ["#f7fbff", "#deebf7", "#c6dbef", "#9ecae1", "#6baed6", "#4292c6", "#2171b5", "#084594"],
        9: ["#f7fbff", "#deebf7", "#c6dbef", "#9ecae1", "#6baed6", "#4292c6", "#2171b5", "#08519c", "#08306b"],
    },
    "Greens": {
        3: ["#e5f5e0", "#a1d99b", "#31a354"],
        4: ["#edf8e9", "#bae4b3", "#74c476", "#238b45"],
        5: ["#edf8e9", "#bae4b3", "#74c476", "#31a354", "#006d2c"],
        6: ["#edf8e9", "#c7e9c0", "#a1d99b", "#74c476", "#31a354", "#006d2c"],
        7: ["#edf8e9", "#c7e9c0", "#a1d99b", "#74c476", "#41ab5d", "#238b45", "#005a32"],
        8: ["#f7fcf5", "#e5f5e0", "#c7e9c0", "#a1d99b", "#74c476", "#41ab5d", "#238b45", "#005a32"],
        9: ["#f7fcf5", "#e5f5e0", "#c7e9c0", "#a1d99b", "#74c476", "#41ab5d", "#238b45", "#006d2c", "#00441b"],
    },
    "Oranges": {
        3: ["#fee6ce", "#fdae6b", "#e6550d"],
        4: ["#feedde", "#fdbe85", "#fd8d3c", "#d94701"],
        5: ["#feedde", "#fdbe85", "#fd8d3c", "#e6550d", "#a63603"],
        6: ["#feedde", "#fdd0a2", "#fdae6b", "#fd8d3c", "#e6550d", "#a63603"],
        7: ["#feedde", "#fdd0a2", "#fdae6b", "#fd8d3c", "#f16913", "#d94801", "#8c2d04"],
        8: ["#fff5eb", "#fee6ce", "#fdd0a2", "#fdae6b", "#fd8d3c", "#f16913", "#d94801", "#8c2d04"],
        9: ["#fff5eb", "#fee6ce", "#fdd0a2", "#fdae6b", "#fd8d3c", "#f16913", "#d94801", "#a63603", "#7f2704"],
    },
    "Reds": {
        3: ["#fee0d2", "#fc9272", "#de2d26"],
        4: ["#fee5d9", "#fcae91", "#fb6a4a", "#cb181d"],
        5: ["#fee5d9", "#fcae91", "#fb6a4a", "#de2d26", "#a50f15"],
        6: ["#fee5d9", "#fcbba1", "#fc9272", "#fb6a4a", "#de2d26", "#a50f15"],
        7: ["#fee5d9", "#fcbba1", "#fc9272", "#fb6a4a", "#ef3b2c", "#cb181d", "#99000d"],
        8: ["#fff5f0", "#fee0d2", "#fcbba1", "#fc9272", "#fb6a4a", "#ef3b2c", "#cb181d", "#99000d"],
        9: ["#fff5f0", "#fee0d2", "#fcbba1", "#fc9272", "#fb6a4a", "#ef3b2c", "#cb181d", "#a50f15", "#67000d"],
    },
    "Purples": {
        3: ["#efedf5", "#bcbddc", "#756bb1"],
        4: ["#f2f0f7", "#cbc9e2", "#9e9ac8", "#6a51a3"],
        5: ["#f2f0f7", "#cbc9e2", "#9e9ac8", "#756bb1", "#54278f"],
        6: ["#f2f0f7", "#dadaeb", "#bcbddc", "#9e9ac8", "#756bb1", "#54278f"],
        7: ["#f2f0f7", "#dadaeb", "#bcbddc", "#9e9ac8", "#807dba", "#6a51a3", "#4a1486"],
        8: ["#fcfbfd", "#efedf5", "#dadaeb", "#bcbddc", "#9e9ac8", "#807dba", "#6a51a3", "#4a1486"],
        9: ["#fcfbfd", "#efedf5", "#dadaeb", "#bcbddc", "#9e9ac8", "#807dba", "#6a51a3", "#54278f", "#3f007d"],
    },
    "YlOrRd": {
        3: ["#ffeda0", "#feb24c", "#f03b20"],
        4: ["#ffffb2", "#fecc5c", "#fd8d3c", "#e31a1c"],
        5: ["#ffffb2", "#fecc5c", "#fd8d3c", "#f03b20", "#bd0026"],
        6: ["#ffffb2", "#fed976", "#feb24c", "#fd8d3c", "#f03b20", "#bd0026"],
        7: ["#ffffb2", "#fed976", "#feb24c", "#fd8d3c", "#fc4e2a", "#e31a1c", "#b10026"],
        8: ["#ffffcc", "#ffeda0", "#fed976", "#feb24c", "#fd8d3c", "#fc4e2a", "#e31a1c", "#b10026"],
        9: ["#ffffcc", "#ffeda0", "#fed976", "#feb24c", "#fd8d3c", "#fc4e2a", "#e31a1c", "#bd0026", "#800026"],
    },
    "Viridis": {
        3: ["#440154", "#21918c", "#fde725"],
        4: ["#440154", "#31688e", "#35b779", "#fde725"],
        5: ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"],
        6: ["#440154", "#414487", "#2a788e", "#22a884", "#7ad151", "#fde725"],
        7: ["#440154", "#443a83", "#31688e", "#21918c", "#35b779", "#8fd744", "#fde725"],
        8: ["#440154", "#46327e", "#365c8d", "#277f8e", "#1fa187", "#4ac16d", "#9fda3a", "#fde725"],
        9: ["#440154", "#472d7b", "#3b528b", "#2c728e", "#21918c", "#27ad81", "#5dc863", "#aadc32", "#fde725"],
    },
}

_previous_styles: dict[str, str] = {}


class ChoroplethError(ValueError):
    """사용자에게 보여줄 단계구분도 검증 오류."""


def palette_colors(name: str, classes: int, reverse: bool = False) -> list[str]:
    key = str(name or "YlOrRd").strip()
    pack = PALETTES.get(key) or PALETTES.get(key.capitalize())
    if pack is None:
        raise ChoroplethError("지원하지 않는 색상표입니다.")
    n = int(classes)
    if n not in pack:
        nearest = min(pack.keys(), key=lambda k: abs(k - n))
        colors = list(pack[nearest])
        if n < len(colors):
            colors = _resample_colors(colors, n)
        elif n > len(colors):
            colors = _resample_colors(colors, n)
    else:
        colors = list(pack[n])
    if reverse:
        colors = list(reversed(colors))
    return colors


def _resample_colors(colors: list[str], n: int) -> list[str]:
    if n <= 1:
        return colors[:1] or ["#ffffcc"]
    if n == len(colors):
        return list(colors)
    out: list[str] = []
    last = len(colors) - 1
    for i in range(n):
        t = i * last / (n - 1)
        lo = int(math.floor(t))
        hi = min(last, lo + 1)
        frac = t - lo
        out.append(_mix_hex(colors[lo], colors[hi], frac))
    return out


def _mix_hex(a: str, b: str, t: float) -> str:
    ar, ag, ab = _hex_rgb(a)
    br, bg, bb = _hex_rgb(b)
    r = round(ar + (br - ar) * t)
    g = round(ag + (bg - ag) * t)
    bch = round(ab + (bb - ab) * t)
    return f"#{r:02x}{g:02x}{bch:02x}"


def _hex_rgb(value: str) -> tuple[int, int, int]:
    h = normalize_hex(value).lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def normalize_hex(value: str, *, field: str = "색상") -> str:
    text = str(value or "").strip()
    if not _HEX_RE.fullmatch(text):
        raise ChoroplethError(f"{field} 값이 올바르지 않습니다.")
    return f"#{text[1:].lower()}"


def style_name_for(layer: str, field: str) -> str:
    layer_s = _STYLE_SAFE_RE.sub("_", (layer or "").split(":")[-1])[:48]
    field_s = _STYLE_SAFE_RE.sub("_", field or "")[:32]
    name = f"{STYLE_PREFIX}{layer_s}__{field_s}".strip("_")
    if len(name) > 80:
        digest = hashlib.sha1(f"{layer}:{field}".encode("utf-8")).hexdigest()[:6]
        name = f"{STYLE_PREFIX}{layer_s[:24]}__{field_s[:16]}__{digest}"
    return name


def is_safe_style_name(name: str) -> bool:
    return bool(name) and name.startswith(STYLE_PREFIX) and re.fullmatch(
        r"[A-Za-z0-9_-]+", name
    )


def is_identifier_field(name: str, display_name: str = "") -> bool:
    """코드·ID 열은 단계구분도 기본 선택에서 뒤로 보낸다."""
    n = (name or "").strip()
    d = display_name or ""
    if _ID_FIELD_RE.search(n):
        return True
    if "코드" in d:
        return True
    return False


def list_numeric_fields(settings: Settings, layer: str) -> dict[str, Any]:
    resolved = resolve_polygon_layer(settings, layer)
    index = MetaIndex.load(settings)
    meta_table = index.resolve_table(resolved["table"]) or resolved["table"]
    fields: list[dict[str, Any]] = []
    for col in resolved["columns"]:
        if not col["numeric"]:
            continue
        display = index.field_display_name(col["name"], table=meta_table)
        fields.append(
            {
                "name": col["name"],
                "display_name": display,
                "unit": index.field_unit(col["name"], table=meta_table),
                "data_type": col["data_type"],
                "identifier": is_identifier_field(col["name"], display),
            }
        )
    fields.sort(
        key=lambda item: (
            bool(item["identifier"]),
            str(item["name"]).lower(),
        )
    )
    return {
        "ok": True,
        "layer": resolved["layer"],
        "title": index.table_title(resolved["layer"]),
        "geometry_type": resolved["geometry_type"],
        "fields": fields,
    }


def field_stats(settings: Settings, layer: str, field: str) -> dict[str, Any]:
    resolved = resolve_polygon_layer(settings, layer)
    col = _require_numeric_column(resolved, field)
    index = MetaIndex.load(settings)
    meta_table = index.resolve_table(resolved["table"]) or resolved["table"]
    ident_schema = sql.Identifier(resolved["schema"])
    ident_table = sql.Identifier(resolved["table"])
    ident_field = sql.Identifier(col["name"])
    query = sql.SQL(
        """
        SELECT
            COUNT(*) AS count,
            COUNT({field}) AS valid_count,
            COUNT(*) FILTER (WHERE {field} IS NULL) AS null_count,
            MIN({field}) AS min,
            MAX({field}) AS max,
            AVG({field})::float8 AS mean,
            percentile_cont(0.5) WITHIN GROUP (ORDER BY {field}) AS median
        FROM {schema}.{table}
        """
    ).format(
        field=ident_field,
        schema=ident_schema,
        table=ident_table,
    )
    with connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone() or {}
    stats = _stats_from_row(row)
    return {
        "ok": True,
        "layer": resolved["layer"],
        "field": col["name"],
        "display_name": index.field_display_name(col["name"], table=meta_table),
        "unit": index.field_unit(col["name"], table=meta_table),
        **stats,
    }


def classify(
    settings: Settings,
    *,
    layer: str,
    field: str,
    method: str = "jenks",
    classes: int = DEFAULT_CLASSES,
    palette: str = "YlOrRd",
    reverse: bool = False,
    null_color: str = DEFAULT_NULL_COLOR,
    stroke: str = DEFAULT_STROKE,
    stroke_width: float = DEFAULT_STROKE_WIDTH,
    fill_opacity: float = DEFAULT_FILL_OPACITY,
    break_values: list[float] | None = None,
    manual_breaks: list[float] | None = None,
) -> dict[str, Any]:
    method_key = str(method or "jenks").strip().lower()
    if method_key not in _METHODS:
        raise ChoroplethError("지원하지 않는 분류 방법입니다.")
    n_classes = DEFAULT_CLASSES if method_key == "manual" else _parse_classes(classes)
    null_hex = normalize_hex(null_color, field="결측 색상")
    stroke_hex = normalize_hex(stroke, field="경계색")
    width = _parse_stroke_width(stroke_width)
    opacity = _parse_opacity(fill_opacity)

    resolved = resolve_polygon_layer(settings, layer)
    col = _require_numeric_column(resolved, field)
    index = MetaIndex.load(settings)
    meta_table = index.resolve_table(resolved["table"]) or resolved["table"]
    stats = _compute_stats(settings, resolved, col["name"])
    sampled = False
    sample_size = stats["valid_count"]
    message = ""

    edges: list[float]
    if method_key == "equal_interval":
        edges, message = equal_interval_edges(
            stats["min"], stats["max"], n_classes, stats.get("unique_count")
        )
    elif method_key == "quantile":
        edges, message = quantile_edges(settings, resolved, col["name"], n_classes, stats)
    elif method_key == "manual":
        raw = break_values if break_values is not None else manual_breaks
        edges = manual_edges(raw, stats["min"], stats["max"])
    else:
        values, sampled, sample_size = _load_values(
            settings, resolved, col["name"], stats["valid_count"]
        )
        edges, message = jenks_edges(values, n_classes, stats["min"], stats["max"])

    classes_out = max(1, len(edges) - 1)
    colors = palette_colors(palette, classes_out, reverse=reverse)
    breaks = []
    for i in range(classes_out):
        breaks.append(
            {
                "min": edges[i],
                "max": edges[i + 1],
                "color": colors[i],
            }
        )
    result: dict[str, Any] = {
        "layer": resolved["layer"],
        "field": col["name"],
        "field_display_name": index.field_display_name(col["name"], table=meta_table),
        "unit": index.field_unit(col["name"], table=meta_table),
        "method": method_key,
        "classes": classes_out,
        "palette": palette if palette in PALETTES else "YlOrRd",
        "min": stats["min"],
        "max": stats["max"],
        "mean": stats["mean"],
        "median": stats["median"],
        "count": stats["count"],
        "null_count": stats["null_count"],
        "valid_count": stats["valid_count"],
        "breaks": breaks,
        "null_color": null_hex,
        "stroke": stroke_hex,
        "stroke_width": width,
        "fill_opacity": opacity,
        "reverse": bool(reverse),
        "sampled": sampled,
        "geometry_type": resolved["geometry_type"],
        "title": index.table_title(resolved["layer"]),
    }
    if sampled:
        result["sample_size"] = sample_size
    if message:
        result["message"] = message
    return result


def preview(settings: Settings, **kwargs: Any) -> dict[str, Any]:
    classification = classify(settings, **kwargs)
    return {
        "ok": True,
        "geoserver_ok": False,
        "classification": classification,
        "legend": legend_spec(classification),
        "sld": build_sld(classification),
    }


def apply_choropleth(settings: Settings, **kwargs: Any) -> dict[str, Any]:
    classification = classify(settings, **kwargs)
    sld = build_sld(classification)
    style_name = style_name_for(classification["layer"], classification["field"])
    client = GeoServerClient(settings)
    if not client.enabled or not client.check():
        return {
            "ok": True,
            "geoserver_ok": False,
            "workspace": client.workspace,
            "layer": classification["layer"],
            "style_name": style_name,
            "classification": classification,
            "legend": legend_spec(classification),
            "message": "GeoServer 스타일을 적용하지 못했습니다. 기존 지도 스타일은 유지됩니다",
        }

    previous = client.get_layer_default_style(classification["layer"])
    created_new = not client.style_exists(style_name)
    assigned = False
    try:
        if not client.ensure_style(style_name, sld):
            raise RuntimeError("style-ensure-failed")
        assigned = client.assign_style_to_layer(classification["layer"], style_name)
        if not assigned:
            raise RuntimeError("style-assign-failed")
    except Exception:
        if created_new:
            try:
                client.delete_style(style_name)
            except Exception:
                pass
        return {
            "ok": True,
            "geoserver_ok": False,
            "workspace": client.workspace,
            "layer": classification["layer"],
            "style_name": style_name,
            "classification": classification,
            "legend": legend_spec(classification),
            "message": "GeoServer 스타일을 적용하지 못했습니다. 기존 지도 스타일은 유지됩니다",
        }

    if previous and previous != style_name:
        _previous_styles[classification["layer"]] = previous
    return {
        "ok": True,
        "geoserver_ok": True,
        "workspace": client.workspace,
        "layer": classification["layer"],
        "style_name": style_name,
        "classification": classification,
        "legend": legend_spec(classification),
        "previous_style": _previous_styles.get(classification["layer"]),
    }


def reset_choropleth(
    settings: Settings,
    layer: str,
    *,
    purge_style: bool = True,
    style_name: str | None = None,
) -> dict[str, Any]:
    short = (layer or "").split(":")[-1]
    if not _layer_name_allowed(short):
        raise ChoroplethError("허용되지 않은 레이어입니다.")
    client = GeoServerClient(settings)
    restore = _previous_styles.get(short) or "polygon"
    target_style = style_name or ""
    geoserver_ok = False
    if client.enabled and client.check():
        current = client.get_layer_default_style(short)
        if not target_style and current and current.startswith(STYLE_PREFIX):
            target_style = current
        restored = client.assign_style_to_layer(short, restore)
        if restored:
            geoserver_ok = True
            if purge_style and target_style and is_safe_style_name(target_style):
                client.delete_style(target_style)
        elif current and current.startswith(STYLE_PREFIX):
            # 기본 polygon 지정 실패 시 연결만 유지
            geoserver_ok = False
    _previous_styles.pop(short, None)
    return {
        "ok": True,
        "geoserver_ok": geoserver_ok,
        "layer": short,
        "restored_style": restore if geoserver_ok else None,
    }


def legend_spec(classification: dict[str, Any]) -> dict[str, Any]:
    items = []
    for brk in classification.get("breaks") or []:
        items.append(
            {
                "color": brk["color"],
                "label": format_break_label(brk["min"], brk["max"]),
                "min": brk["min"],
                "max": brk["max"],
            }
        )
    items.append(
        {
            "color": classification.get("null_color") or DEFAULT_NULL_COLOR,
            "label": NULL_LEGEND_LABEL,
            "null": True,
        }
    )
    return {
        "title": classification.get("field_display_name") or classification.get("field"),
        "field": classification.get("field"),
        "unit": classification.get("unit") or "",
        "items": items,
    }


def format_break_label(lo: float, hi: float) -> str:
    return f"{_fmt_num(lo)} – {_fmt_num(hi)}"


def build_sld(classification: dict[str, Any]) -> str:
    layer = xml.sax.saxutils.escape(str(classification.get("layer") or "layer"))
    field = str(classification.get("field") or "")
    if not is_safe_ident(field):
        raise ChoroplethError("선택한 속성은 숫자형이 아닙니다")
    field_xml = xml.sax.saxutils.escape(field)
    stroke = xml.sax.saxutils.escape(
        str(classification.get("stroke") or DEFAULT_STROKE)
    )
    width = float(classification.get("stroke_width") or DEFAULT_STROKE_WIDTH)
    opacity = float(classification.get("fill_opacity") or DEFAULT_FILL_OPACITY)
    breaks = list(classification.get("breaks") or [])
    last = len(breaks) - 1
    rules: list[str] = []
    for i, brk in enumerate(breaks):
        lo = float(brk["min"])
        hi = float(brk["max"])
        color = xml.sax.saxutils.escape(str(brk["color"]))
        title = xml.sax.saxutils.escape(format_break_label(lo, hi))
        upper = _sld_le(field_xml, hi) if i == last else _sld_lt(field_xml, hi)
        rules.append(
            f"""        <Rule>
          <Title>{title}</Title>
          <ogc:Filter>
            <ogc:And>
              {_sld_ge(field_xml, lo)}
              {upper}
            </ogc:And>
          </ogc:Filter>
{_polygon_symbolizer(color, opacity, stroke, width)}
        </Rule>"""
        )
    null_color = xml.sax.saxutils.escape(
        str(classification.get("null_color") or DEFAULT_NULL_COLOR)
    )
    null_title = xml.sax.saxutils.escape(NULL_LEGEND_LABEL)
    rules.append(
        f"""        <Rule>
          <Title>{null_title}</Title>
          <ogc:Filter>
            <ogc:PropertyIsNull>
              <ogc:PropertyName>{field_xml}</ogc:PropertyName>
            </ogc:PropertyIsNull>
          </ogc:Filter>
{_polygon_symbolizer(null_color, opacity, stroke, width)}
        </Rule>"""
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<StyledLayerDescriptor version="1.0.0"\n'
        '  xmlns="http://www.opengis.net/sld"\n'
        '  xmlns:ogc="http://www.opengis.net/ogc">\n'
        "  <NamedLayer>\n"
        f"    <Name>{layer}</Name>\n"
        "    <UserStyle>\n"
        "      <FeatureTypeStyle>\n"
        + "\n".join(rules)
        + "\n      </FeatureTypeStyle>\n"
        "    </UserStyle>\n"
        "  </NamedLayer>\n"
        "</StyledLayerDescriptor>"
    )


def equal_interval_edges(
    min_v: float | None,
    max_v: float | None,
    classes: int,
    unique_count: int | None = None,
) -> tuple[list[float], str]:
    if min_v is None or max_v is None:
        raise ChoroplethError("단계구분도를 만들 수 있는 유효한 값이 없습니다")
    lo, hi = float(min_v), float(max_v)
    n = int(classes)
    message = ""
    if unique_count is not None and unique_count < n:
        n = max(1, int(unique_count))
        if n < classes:
            message = (
                f"유효한 값이 부족하여 {classes}개 구간을 만들 수 없습니다. "
                f"{n}개 구간으로 조정했습니다"
            )
    if not math.isfinite(lo) or not math.isfinite(hi):
        raise ChoroplethError("선택한 속성은 숫자형이 아닙니다")
    if hi < lo:
        lo, hi = hi, lo
    if hi == lo:
        return [lo, hi], message
    span = hi - lo
    edges = [lo]
    for i in range(1, n):
        edges.append(lo + span * i / n)
    edges.append(hi)
    return _dedupe_edges(edges), message


def quantile_edges(
    settings: Settings,
    resolved: dict[str, Any],
    field: str,
    classes: int,
    stats: dict[str, Any],
) -> tuple[list[float], str]:
    n = int(classes)
    unique = stats.get("unique_count")
    message = ""
    if unique is not None and unique < n:
        n = max(1, int(unique))
        message = (
            f"유효한 값이 부족하여 {classes}개 구간을 만들 수 없습니다. "
            f"{n}개 구간으로 조정했습니다"
        )
    if stats["min"] is None or stats["max"] is None or stats["valid_count"] <= 0:
        raise ChoroplethError("단계구분도를 만들 수 있는 유효한 값이 없습니다")
    if n <= 1 or stats["min"] == stats["max"]:
        return [float(stats["min"]), float(stats["max"])], message
    probs = [i / n for i in range(1, n)]
    ident_field = sql.Identifier(field)
    query = sql.SQL(
        """
        SELECT percentile_cont(%s::double precision[])
            WITHIN GROUP (ORDER BY {field}) AS qs
        FROM {schema}.{table}
        WHERE {field} IS NOT NULL
        """
    ).format(
        field=ident_field,
        schema=sql.Identifier(resolved["schema"]),
        table=sql.Identifier(resolved["table"]),
    )
    with connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (probs,))
            row = cur.fetchone() or {}
    qs = row.get("qs") or []
    if not isinstance(qs, (list, tuple)):
        qs = [qs]
    edges = [float(stats["min"])]
    for val in qs:
        if val is None:
            continue
        num = float(val)
        if math.isfinite(num):
            edges.append(num)
    edges.append(float(stats["max"]))
    edges = _dedupe_edges(edges)
    actual = max(1, len(edges) - 1)
    if actual < classes and not message:
        message = (
            f"유효한 값이 부족하여 {classes}개 구간을 만들 수 없습니다. "
            f"{actual}개 구간으로 조정했습니다"
        )
    return edges, message


def jenks_edges(
    values: list[float],
    classes: int,
    min_v: float | None,
    max_v: float | None,
) -> tuple[list[float], str]:
    if not values or min_v is None or max_v is None:
        raise ChoroplethError("단계구분도를 만들 수 있는 유효한 값이 없습니다")
    data = sorted(float(v) for v in values if v is not None and math.isfinite(float(v)))
    if not data:
        raise ChoroplethError("단계구분도를 만들 수 있는 유효한 값이 없습니다")
    unique = sorted(set(data))
    n = int(classes)
    message = ""
    if len(unique) < n:
        n = max(1, len(unique))
        message = (
            f"유효한 값이 부족하여 {classes}개 구간을 만들 수 없습니다. "
            f"{n}개 구간으로 조정했습니다"
        )
    if n <= 1 or unique[0] == unique[-1]:
        return [float(unique[0]), float(unique[-1])], message
    breaks = _jenks_breaks(data, n)
    edges = [float(min_v)]
    for brk in breaks:
        if math.isfinite(brk):
            edges.append(float(brk))
    edges.append(float(max_v))
    return _dedupe_edges(edges), message


def manual_edges(
    break_values: list[float] | None, min_v: float | None, max_v: float | None
) -> list[float]:
    if min_v is None or max_v is None:
        raise ChoroplethError("단계구분도를 만들 수 있는 유효한 값이 없습니다")
    if not break_values:
        raise ChoroplethError("사용자 정의 구간 값이 필요합니다")
    nums: list[float] = []
    for raw in break_values:
        try:
            num = float(raw)
        except (TypeError, ValueError) as exc:
            raise ChoroplethError("구간 값은 유한한 숫자여야 합니다") from exc
        if not math.isfinite(num):
            raise ChoroplethError("구간 값은 유한한 숫자여야 합니다")
        nums.append(num)
    if any(nums[i] >= nums[i + 1] for i in range(len(nums) - 1)):
        raise ChoroplethError("구간 값은 중복 없이 오름차순이어야 합니다")
    lo, hi = float(min_v), float(max_v)
    if nums[0] <= lo and nums[-1] >= hi:
        edges = [lo, *nums[1:-1], hi] if len(nums) >= 2 else [lo, hi]
    else:
        if nums[0] <= lo or nums[-1] >= hi:
            raise ChoroplethError("구간 값이 데이터의 최소/최대와 맞지 않습니다")
        edges = [lo, *nums, hi]
    classes_out = len(edges) - 1
    if classes_out > MAX_CLASSES:
        raise ChoroplethError(f"구간 수는 최대 {MAX_CLASSES}개입니다")
    if classes_out < 1:
        raise ChoroplethError("유효한 구간을 만들 수 없습니다")
    return _dedupe_edges(edges)


def resolve_polygon_layer(settings: Settings, layer: str) -> dict[str, Any]:
    short = (layer or "").strip().split(":")[-1]
    if not _layer_name_allowed(short):
        raise ChoroplethError("허용되지 않은 레이어입니다.")
    if _is_blocked_table(short):
        raise ChoroplethError("허용되지 않은 레이어입니다.")
    if is_catalog_layer_name(short):
        client = GeoServerClient(settings)
        if client.enabled:
            catalog = {item["name"] for item in client.catalog_layers()}
            if catalog and short not in catalog and not is_safe_layer_name(short):
                # GeoServer 오프라인이면 PostGIS 존재 여부로 판단
                pass
            elif catalog and short not in catalog and not _table_exists_anywhere(
                settings, short
            ):
                raise ChoroplethError("허용되지 않은 레이어입니다.")
    found = _locate_table(settings, short)
    if found is None:
        raise ChoroplethError("허용되지 않은 레이어입니다.")
    schema, table = found
    geom = _geometry_info(settings, schema, table)
    if geom is None:
        raise ChoroplethError("이 레이어에는 단계구분도에 사용할 수 있는 숫자 속성이 없습니다")
    gtype = str(geom.get("type") or "").upper().replace("ST_", "")
    if gtype in {"GEOMETRY", "GEOGRAPHY", ""}:
        probed = _probe_geometry_type(
            settings, schema, table, str(geom.get("column") or "geometry")
        )
        if probed:
            gtype = probed.upper().replace("ST_", "")
            geom["type"] = gtype
    if "POLYGON" not in gtype:
        raise ChoroplethError("단계구분도는 면(Polygon) 레이어에서만 사용할 수 있습니다")
    columns = _table_columns(settings, schema, table)
    return {
        "layer": short,
        "schema": schema,
        "table": table,
        "geometry_type": gtype,
        "geometry_column": geom.get("column") or "geometry",
        "columns": columns,
    }


def _layer_name_allowed(name: str) -> bool:
    return is_safe_layer_name(name) or is_catalog_layer_name(name)


def _is_blocked_table(name: str) -> bool:
    if is_safe_layer_name(name):
        return False
    return is_protected_table(name)


def _table_exists_anywhere(settings: Settings, table: str) -> bool:
    return _locate_table(settings, table) is not None


def _locate_table(settings: Settings, table: str) -> tuple[str, str] | None:
    map_schema = (settings.map_schema or "public").strip() or "public"
    schemas = []
    for schema in (map_schema, "public"):
        if schema not in schemas and is_safe_ident(schema):
            schemas.append(schema)
    with connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT f_table_schema, f_table_name
                FROM geometry_columns
                WHERE f_table_name IN (%s, lower(%s))
                ORDER BY CASE WHEN f_table_schema = %s THEN 0 ELSE 1 END
                """,
                (table, table, map_schema),
            )
            row = cur.fetchone()
            if row:
                schema = str(row["f_table_schema"] or "public")
                name = str(row["f_table_name"] or table)
                if schema in {"pg_catalog", "information_schema"}:
                    return None
                return schema, name
            for schema in schemas:
                cur.execute(
                    """
                    SELECT table_schema, table_name
                    FROM information_schema.tables
                    WHERE table_schema = %s
                      AND table_name IN (%s, lower(%s))
                    LIMIT 1
                    """,
                    (schema, table, table),
                )
                row = cur.fetchone()
                if row:
                    return str(row["table_schema"]), str(row["table_name"])
    return None


def _geometry_info(
    settings: Settings, schema: str, table: str
) -> dict[str, str] | None:
    with connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT f_geometry_column, type, srid
                FROM geometry_columns
                WHERE f_table_schema = %s AND f_table_name = %s
                LIMIT 1
                """,
                (schema, table),
            )
            row = cur.fetchone()
            if row:
                return {
                    "column": str(row["f_geometry_column"] or "geometry"),
                    "type": str(row["type"] or ""),
                    "srid": str(row["srid"] or ""),
                }
            cur.execute(
                """
                SELECT column_name, udt_name
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
                """,
                (schema, table),
            )
            for item in cur.fetchall():
                udt = str(item["udt_name"] or "").lower()
                name = str(item["column_name"] or "")
                if udt in {"geometry", "geography"} or name.lower() in {
                    "geometry",
                    "geom",
                    "the_geom",
                }:
                    gtype = _probe_geometry_type(settings, schema, table, name)
                    return {"column": name, "type": gtype, "srid": ""}
    return None


def _probe_geometry_type(
    settings: Settings, schema: str, table: str, geom: str
) -> str:
    query = sql.SQL(
        "SELECT GeometryType({geom}) AS gtype FROM {schema}.{table} "
        "WHERE {geom} IS NOT NULL LIMIT 1"
    ).format(
        geom=sql.Identifier(geom),
        schema=sql.Identifier(schema),
        table=sql.Identifier(table),
    )
    try:
        with connect(settings.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                row = cur.fetchone() or {}
        return str(row.get("gtype") or "")
    except Exception:
        return ""


def _table_columns(
    settings: Settings, schema: str, table: str
) -> list[dict[str, Any]]:
    with connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name, data_type, udt_name
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
                """,
                (schema, table),
            )
            rows = list(cur.fetchall())
    out: list[dict[str, Any]] = []
    for row in rows:
        name = str(row["column_name"] or "")
        data_type = str(row["data_type"] or "")
        udt = str(row["udt_name"] or "").lower()
        if not name or not is_safe_ident(name):
            continue
        numeric = _is_numeric_type(data_type, udt)
        out.append(
            {
                "name": name,
                "data_type": data_type or udt,
                "udt_name": udt,
                "numeric": numeric,
            }
        )
    return out


def _is_numeric_type(data_type: str, udt: str) -> bool:
    dt = (data_type or "").strip().lower()
    u = (udt or "").strip().lower()
    if u in {"geometry", "geography", "raster"}:
        return False
    return dt in _NUMERIC_DATA_TYPES or u in _NUMERIC_UDT


def _require_numeric_column(resolved: dict[str, Any], field: str) -> dict[str, Any]:
    name = (field or "").strip()
    if not is_safe_ident(name):
        raise ChoroplethError("선택한 속성은 숫자형이 아닙니다")
    for col in resolved["columns"]:
        if col["name"] == name or col["name"].lower() == name.lower():
            if not col["numeric"]:
                raise ChoroplethError("선택한 속성은 숫자형이 아닙니다")
            return col
    raise ChoroplethError("선택한 속성은 숫자형이 아닙니다")


def _compute_stats(
    settings: Settings, resolved: dict[str, Any], field: str
) -> dict[str, Any]:
    ident_field = sql.Identifier(field)
    query = sql.SQL(
        """
        SELECT
            COUNT(*) AS count,
            COUNT({field}) AS valid_count,
            COUNT(*) FILTER (WHERE {field} IS NULL) AS null_count,
            MIN({field}) AS min,
            MAX({field}) AS max,
            AVG({field})::float8 AS mean,
            percentile_cont(0.5) WITHIN GROUP (ORDER BY {field}) AS median,
            COUNT(DISTINCT {field}) AS unique_count
        FROM {schema}.{table}
        """
    ).format(
        field=ident_field,
        schema=sql.Identifier(resolved["schema"]),
        table=sql.Identifier(resolved["table"]),
    )
    with connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone() or {}
    return _stats_from_row(row)


def _stats_from_row(row: dict[str, Any]) -> dict[str, Any]:
    def _num(key: str) -> float | None:
        val = row.get(key)
        if val is None:
            return None
        try:
            num = float(val)
        except (TypeError, ValueError):
            return None
        return num if math.isfinite(num) else None

    return {
        "count": int(row.get("count") or 0),
        "valid_count": int(row.get("valid_count") or 0),
        "null_count": int(row.get("null_count") or 0),
        "min": _num("min"),
        "max": _num("max"),
        "mean": _num("mean"),
        "median": _num("median"),
        "unique_count": int(row.get("unique_count") or 0),
    }


def _load_values(
    settings: Settings,
    resolved: dict[str, Any],
    field: str,
    valid_count: int,
) -> tuple[list[float], bool, int]:
    ident_field = sql.Identifier(field)
    query = sql.SQL(
        "SELECT {field} AS v FROM {schema}.{table} WHERE {field} IS NOT NULL"
    ).format(
        field=ident_field,
        schema=sql.Identifier(resolved["schema"]),
        table=sql.Identifier(resolved["table"]),
    )
    with connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            values = []
            for row in cur.fetchall():
                val = row.get("v")
                if val is None:
                    continue
                try:
                    num = float(val)
                except (TypeError, ValueError):
                    continue
                if math.isfinite(num):
                    values.append(num)
    if len(values) <= JENKS_SAMPLE_LIMIT:
        return values, False, len(values)
    rng = random.Random(42)
    sampled = rng.sample(values, JENKS_SAMPLE_LIMIT)
    return sampled, True, JENKS_SAMPLE_LIMIT


def _parse_classes(classes: int) -> int:
    try:
        n = int(classes)
    except (TypeError, ValueError) as exc:
        raise ChoroplethError("구간 수가 올바르지 않습니다") from exc
    if n < MIN_CLASSES:
        raise ChoroplethError(f"구간 수는 최소 {MIN_CLASSES}개입니다")
    if n > MAX_CLASSES:
        raise ChoroplethError(f"구간 수는 최대 {MAX_CLASSES}개입니다")
    return n


def _parse_stroke_width(value: float) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError) as exc:
        raise ChoroplethError("경계 두께가 올바르지 않습니다") from exc
    if not math.isfinite(num) or num < 0 or num > 12:
        raise ChoroplethError("경계 두께가 올바르지 않습니다")
    return num


def _parse_opacity(value: float) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError) as exc:
        raise ChoroplethError("투명도가 올바르지 않습니다") from exc
    if not math.isfinite(num) or num < 0 or num > 1:
        raise ChoroplethError("투명도가 올바르지 않습니다")
    return num


def _dedupe_edges(edges: list[float]) -> list[float]:
    out: list[float] = []
    for val in edges:
        if not out or val > out[-1]:
            out.append(val)
        elif val < out[-1]:
            continue
    if len(out) == 1:
        out.append(out[0])
    return out


def _fmt_num(value: float) -> str:
    num = float(value)
    if num == 0:
        return "0"
    abs_n = abs(num)
    if abs_n >= 1000:
        return f"{num:,.2f}".rstrip("0").rstrip(".")
    if abs_n >= 10:
        return f"{num:.2f}".rstrip("0").rstrip(".")
    if abs_n >= 1:
        return f"{num:.2f}".rstrip("0").rstrip(".")
    return f"{num:.4f}".rstrip("0").rstrip(".")


def _sld_ge(field_xml: str, value: float) -> str:
    return (
        "<ogc:PropertyIsGreaterThanOrEqualTo>"
        f"<ogc:PropertyName>{field_xml}</ogc:PropertyName>"
        f"<ogc:Literal>{_sld_num(value)}</ogc:Literal>"
        "</ogc:PropertyIsGreaterThanOrEqualTo>"
    )


def _sld_lt(field_xml: str, value: float) -> str:
    return (
        "<ogc:PropertyIsLessThan>"
        f"<ogc:PropertyName>{field_xml}</ogc:PropertyName>"
        f"<ogc:Literal>{_sld_num(value)}</ogc:Literal>"
        "</ogc:PropertyIsLessThan>"
    )


def _sld_le(field_xml: str, value: float) -> str:
    return (
        "<ogc:PropertyIsLessThanOrEqualTo>"
        f"<ogc:PropertyName>{field_xml}</ogc:PropertyName>"
        f"<ogc:Literal>{_sld_num(value)}</ogc:Literal>"
        "</ogc:PropertyIsLessThanOrEqualTo>"
    )


def _sld_num(value: float) -> str:
    return xml.sax.saxutils.escape(format(float(value), ".10g"))


def _polygon_symbolizer(
    color: str, opacity: float, stroke: str, width: float
) -> str:
    return f"""          <PolygonSymbolizer>
            <Fill>
              <CssParameter name="fill">{color}</CssParameter>
              <CssParameter name="fill-opacity">{opacity}</CssParameter>
            </Fill>
            <Stroke>
              <CssParameter name="stroke">{stroke}</CssParameter>
              <CssParameter name="stroke-width">{width}</CssParameter>
            </Stroke>
          </PolygonSymbolizer>"""


def _jenks_breaks(data: list[float], n_classes: int) -> list[float]:
    """Fisher-Jenks natural breaks. `data` must be sorted."""
    n = len(data)
    k = min(n_classes, n)
    if k <= 1:
        return []
    lower = [[0] * (k + 1) for _ in range(n + 1)]
    var = [[0.0] * (k + 1) for _ in range(n + 1)]
    for i in range(1, k + 1):
        lower[1][i] = 1
        var[1][i] = 0.0
        for j in range(2, n + 1):
            var[j][i] = math.inf
    for l in range(2, n + 1):
        s1 = 0.0
        s2 = 0.0
        w = 0.0
        for m in range(1, l + 1):
            i3 = l - m + 1
            val = data[i3 - 1]
            s2 += val * val
            s1 += val
            w += 1.0
            variance = s2 - (s1 * s1) / w
            i4 = i3 - 1
            if i4 != 0:
                for j in range(2, k + 1):
                    if var[l][j] >= variance + var[i4][j - 1]:
                        lower[l][j] = i3
                        var[l][j] = variance + var[i4][j - 1]
        lower[l][1] = 1
        var[l][1] = variance
    kclass = [0] * (k + 1)
    kclass[k] = n
    count_num = k
    idx = n
    while count_num > 1:
        kclass[count_num - 1] = lower[idx][count_num] - 1
        idx = lower[idx][count_num] - 1
        count_num -= 1
    breaks = []
    for i in range(1, k):
        cut = kclass[i]
        if 0 < cut <= n:
            breaks.append(data[cut - 1])
    return breaks
