"""레이어 추가·삭제·위계 이동."""

from __future__ import annotations

from pathlib import Path

from txt2sql.config import Settings
from txt2sql.map import ANALYSIS_Z_BASE, ANALYSIS_Z_STEP, LayerStack
from txt2sql.map.publish import (
    cleanup_session_layers,
    delete_published_layer,
    is_catalog_layer_name,
    is_safe_layer_name,
    is_safe_session_id,
    trim_session_layers,
)


def main() -> int:
    failed: list[str] = []
    passed = 0

    def ok(name: str, cond: bool, detail: str = "") -> None:
        nonlocal passed
        if cond:
            passed += 1
            print(f"[ok] {name}")
        else:
            failed.append(f"{name}: {detail}")
            print(f"[fail] {name} {detail}")

    stack = LayerStack()
    ok("empty start", len(stack) == 0 and stack.ids() == [])

    ok("add a", stack.add("a"))
    ok("add b on top", stack.add("b"))
    ok("add c on top", stack.add("c"))
    ok("order newest on top", stack.ids() == ["c", "b", "a"], str(stack.ids()))
    ok("duplicate add rejected", stack.add("b") is False)
    ok("empty id rejected", stack.add("") is False)

    z = stack.z_indices()
    ok(
        "z top highest",
        z["c"] > z["b"] > z["a"],
        str(z),
    )
    ok(
        "z formula",
        z["c"] == ANALYSIS_Z_BASE + 3 * ANALYSIS_Z_STEP
        and z["a"] == ANALYSIS_Z_BASE + 1 * ANALYSIS_Z_STEP,
        str(z),
    )

    ok("move down top", stack.move_down("c") is True)
    ok("after move down", stack.ids() == ["b", "c", "a"], str(stack.ids()))
    ok("move up c", stack.move_up("c") is True)
    ok("restored top", stack.ids() == ["c", "b", "a"], str(stack.ids()))

    ok("move up already top", stack.move_up("c") is False)
    ok("move down already bottom", stack.move_down("a") is False)
    ok("move missing", stack.move_up("nope") is False)

    ok("move_to b top", stack.move_to("b", 0) is True)
    ok("drag b to top", stack.ids() == ["b", "c", "a"], str(stack.ids()))
    ok("move_to a middle", stack.move_to("a", 1) is True)
    ok("a in middle", stack.ids() == ["b", "a", "c"], str(stack.ids()))
    ok("move_to clamp bottom", stack.move_to("a", 99) is True)
    ok("a at bottom", stack.ids() == ["b", "c", "a"], str(stack.ids()))
    ok("move_to same index", stack.move_to("b", 0) is False)

    snap = stack.snapshot()
    ok("snapshot len", len(snap) == 3)
    ok("snapshot z desc", snap[0].z_index > snap[1].z_index > snap[2].z_index)

    ok("remove c", stack.remove("c") is True)
    ok("after remove", stack.ids() == ["b", "a"], str(stack.ids()))
    ok("remove missing", stack.remove("c") is False)
    ok("contains b", "b" in stack)
    ok("not contains c", "c" not in stack)

    z2 = stack.z_indices()
    ok(
        "z recompute after delete",
        z2["b"] == ANALYSIS_Z_BASE + 2 * ANALYSIS_Z_STEP
        and z2["a"] == ANALYSIS_Z_BASE + ANALYSIS_Z_STEP,
        str(z2),
    )

    bottom = LayerStack()
    ok("add on bottom", bottom.add("x", on_top=False) and bottom.add("y", on_top=False))
    ok("bottom order", bottom.ids() == ["x", "y"], str(bottom.ids()))

    settings = Settings(database_url="postgresql://u:p@localhost:5432/gisdb")
    ok("safe temp name", is_safe_layer_name("temp_ab12cd34ef56aa00"))
    ok("catalog name", is_catalog_layer_name("AL_D010_26_20250704"))
    ok("temp is not catalog", not is_catalog_layer_name("temp_ab12cd34ef56aa00"))
    ok("catalog rejects injection", not is_catalog_layer_name("buildings;drop"))
    raised = False
    try:
        delete_published_layer(settings, "AL_D010_26_20250704")
    except ValueError:
        raised = True
    ok("delete rejects source table", raised)
    raised2 = False
    try:
        delete_published_layer(settings, "temp_;drop")
    except ValueError:
        raised2 = True
    ok("delete rejects injection", raised2)
    ok("session hex", is_safe_session_id("ab" * 16))
    ok("session reject sql", not is_safe_session_id("'; drop table"))
    ok("session empty", not is_safe_session_id(""))
    ok("session none", not is_safe_session_id(None))
    bad_sess = False
    try:
        cleanup_session_layers(settings, "not-a-session")
    except ValueError:
        bad_sess = True
    ok("cleanup rejects bad session", bad_sess)
    ok(
        "trim bad session empty",
        trim_session_layers(settings, "nope", keep=8) == [],
    )
    main_js = (
        Path(__file__).resolve().parents[1]
        / "llm2sql"
        / "webapp"
        / "static"
        / "js"
        / "map"
        / "main.js"
    ).read_text(encoding="utf-8")
    ok("js max analysis", "MAX_ANALYSIS_LAYERS = 8" in main_js)
    ok("js clear analysis", "function clearAnalysis" in main_js)

    js = Path(__file__).resolve().parents[1] / "llm2sql" / "webapp" / "static" / "js" / "map" / "stack.js"
    src = js.read_text(encoding="utf-8")
    ok("js z base matches", "export const ANALYSIS_Z_BASE = 100" in src)
    ok("js z step matches", "export const ANALYSIS_Z_STEP = 10" in src)
    ok("js has moveTo", "moveTo(layerId, index)" in src)
    ok("js has moveUp", "moveUp(layerId)" in src)
    styles = (
        Path(__file__).resolve().parents[1]
        / "llm2sql"
        / "webapp"
        / "static"
        / "js"
        / "map"
        / "styles.js"
    ).read_text(encoding="utf-8")
    ok("sld polygon", "PolygonSymbolizer" in styles)
    ok("applyTheme updateParams", "updateParams" in styles)
    ok("geomKind helper", "export function geomKind" in styles)
    ok("polygon sld skips centroid points", 'kind === "polygon"' in styles)
    from txt2sql.map.labels import MetaIndex, infer_label_field, normalize_field_key, table_name_candidates

    cands = table_name_candidates("AL_D010_26_20250704")
    ok("candidates include full", "AL_D010_26_20250704" in cands)
    ok("candidates strip date", "AL_D010" in cands or any(x.startswith("AL_D010") for x in cands))
    ok("normalize dotted", normalize_field_key("AL_D010_26_20250704.A4") == "A4")
    ok("normalize gml", normalize_field_key("korDB:A4") == "A4")
    idx = MetaIndex(
        tables={"AL_D010_26_20250704": "GIS건물통합정보"},
        columns={"AL_D010_26_20250704": {"A4": "법정동명", "A12": "건물면적"}},
    )
    ok("table title ko", idx.table_title("AL_D010_26_20250704") == "GIS건물통합정보")
    ok("field A4 ko", idx.field_label("A4", table="AL_D010_26_20250704") == "법정동명")
    mapped = idx.fields_for("AL_D010_26_20250704", ["AL_D010_26_20250704.A4", "a12"])
    ok("gfi prefix A4", mapped.get("AL_D010_26_20250704.A4") == "법정동명")
    ok("gfi lower a12", mapped.get("a12") == "건물면적")
    ok("temp not resolved", idx.resolve_table("temp_ab12cd34ef56aa00") is None)
    ok("fallback count", idx.field_label("cnt") == "건수")
    ok(
        "label field building",
        infer_label_field(["A0", "A4", "A24", "A14"]) == "A24",
    )
    ok("label field dong", infer_label_field(["ADM_CD", "ADM_NM"]) == "ADM_NM")
    ok("label field empty", infer_label_field(["A0", "A12"]) is None)

    core_js = (
        Path(__file__).resolve().parents[1]
        / "llm2sql"
        / "webapp"
        / "static"
        / "js"
        / "map"
        / "core.js"
    ).read_text(encoding="utf-8")
    ok("analysis uses ImageWMS", "ol.source.ImageWMS" in core_js)
    ok("kordb stays TileWMS", "ol.source.TileWMS" in core_js)
    ok("sld text symbol", "TextSymbolizer" in styles)

    from txt2sql.map.geoserver import parse_latlon_bbox

    good = parse_latlon_bbox(
        {
            "featureType": {
                "latLonBoundingBox": {
                    "minx": 129.0,
                    "miny": 35.1,
                    "maxx": 129.2,
                    "maxy": 35.3,
                    "crs": "EPSG:4326",
                }
            }
        }
    )
    ok(
        "parse geoserver bbox",
        good == [129.0, 35.1, 129.2, 35.3],
        str(good),
    )
    ok(
        "reject empty bbox",
        parse_latlon_bbox(
            {"featureType": {"latLonBoundingBox": {"minx": -1, "miny": -1, "maxx": 0, "maxy": 0}}}
        )
        is None,
    )
    main_js = (
        Path(__file__).resolve().parents[1]
        / "llm2sql"
        / "webapp"
        / "static"
        / "js"
        / "map"
        / "main.js"
    ).read_text(encoding="utf-8")
    ok(
        "kordb output fits extent",
        "fitLonLatExtent(state.map, item.info?.extent)" in main_js
        or "fitLonLatExtent(state.map, item.info.extent)" in main_js,
    )

    html = (
        Path(__file__).resolve().parents[1]
        / "llm2sql"
        / "webapp"
        / "static"
        / "map.html"
    ).read_text(encoding="utf-8")
    list_at = html.find('id="analysis-layers-list"')
    clear_at = html.find('id="clear-analysis-btn"')
    ok("map has site head", 'class="site-head"' in html)
    ok("map has site foot", 'class="site-foot"' in html)
    ok(
        "clear analysis below list",
        list_at != -1 and clear_at > list_at,
        f"list={list_at} clear={clear_at}",
    )
    data_html = (
        Path(__file__).resolve().parents[1]
        / "llm2sql"
        / "webapp"
        / "static"
        / "data.html"
    ).read_text(encoding="utf-8")
    ok("data page menu", "데이터 관리" in data_html and 'href="/data/upload"' in data_html)

    print(f"\npassed={passed} failed={len(failed)}")
    for item in failed:
        print(" -", item)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
