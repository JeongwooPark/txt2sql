"""지도 SQL wrap · 적격성 · GeoServer 실패 시 채팅 유지."""

from __future__ import annotations

from llm2sql.config import Settings
from llm2sql.geoserver import GeoServerClient
from llm2sql.map_publish import is_safe_layer_name, publish_query_layer
from llm2sql.map_sql import (
    boundary_sql,
    ensure_geometry_select,
    has_geometry_select,
    is_aggregate_sql,
    is_map_route,
    plan_map_sql,
)
from llm2sql.spatial_templates import (
    building_in_dong_count_sql,
    building_in_dong_list_sql,
    scoped_count_sql,
    scoped_list_sql,
)
from llm2sql.types import AskResult


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

    ok("skip guide", not is_map_route("guide"))
    ok("skip meta", not is_map_route("meta"))
    ok("skip chart", not is_map_route("chart_render"))
    ok("skip clarify", not is_map_route("clarify_place"))
    ok("allow list", is_map_route("building_area_topn"))
    ok("allow count", is_map_route("building_place_count"))
    ok("allow empty route", is_map_route(None))

    count_sql = building_in_dong_count_sql("구서1동")
    ok("count is aggregate", is_aggregate_sql(count_sql), count_sql[:80])
    ok("count has no geom select", not has_geometry_select(count_sql))

    list_sql = building_in_dong_list_sql("구서1동", limit=50)
    ok("list not aggregate", not is_aggregate_sql(list_sql), list_sql[:80])
    wrapped = ensure_geometry_select(list_sql, map_limit=2000)
    ok("wrap list", wrapped is not None and "as geometry" in wrapped.lower(), str(wrapped)[:120])
    ok("keep list limit 50", wrapped is not None and "LIMIT 50" in wrapped.upper().replace("\n", " "))

    kind, scoped = scoped_list_sql("구서동", None, limit=20)
    wrapped_s = ensure_geometry_select(scoped, map_limit=2000)
    ok(
        "wrap scoped list",
        wrapped_s is not None and "geometry AS geometry" in wrapped_s,
        str(wrapped_s)[:160],
    )

    already = 'SELECT b."A0", b.geometry FROM "AL_D010_26_20250704" b LIMIT 10;'
    again = ensure_geometry_select(already, map_limit=2000)
    ok(
        "no double geom",
        again is not None and again.lower().count("as geometry") <= 1,
        str(again),
    )

    kind_c, cnt = scoped_count_sql("해운대구", None)
    plan_c = plan_map_sql(
        question="해운대구 건물 몇 채야?",
        sql=cnt,
        route="building_place_count",
        ok=True,
    )
    ok("count plan is boundary", plan_c is not None and plan_c.kind == "boundary")
    ok(
        "count plan union or adm",
        plan_c is not None
        and ("ST_Union" in plan_c.sql or "ADM_NM" in plan_c.sql),
        str(plan_c.sql if plan_c else ""),
    )

    plan_l = plan_map_sql(
        question="구서동에서 건물면적이 가장 큰 아파트는?",
        sql=list_sql,
        route="building_area_topn",
        ok=True,
        map_limit=2000,
    )
    ok("list plan is features", plan_l is not None and plan_l.kind == "features")
    ok(
        "list plan injects geom",
        plan_l is not None and "geometry" in plan_l.sql.lower(),
    )

    plan_skip = plan_map_sql(
        question="기능 알려줘",
        sql=None,
        route="guide",
        ok=True,
    )
    ok("guide no map", plan_skip is None)

    plan_fail = plan_map_sql(
        question="구서동 아파트",
        sql=list_sql,
        route="building_area_topn",
        ok=False,
    )
    ok("failed query no map", plan_fail is None)

    bnd = boundary_sql("해운대구 건물 몇 채야?")
    ok("haeundae boundary", bnd is not None and "26350" in (bnd or ""))
    bnd_d = boundary_sql("구서동 건물 몇 채야?")
    ok("guseo boundary", bnd_d is not None and "구서" in (bnd_d or ""))

    ok("safe layer", is_safe_layer_name("temp_ab12cd34ef56aa00"))
    ok("unsafe layer drop", not is_safe_layer_name("buildings"))
    ok("unsafe quotes", not is_safe_layer_name("temp_; drop table"))

    settings = Settings(
        database_url="postgresql://u:p@localhost:5432/gisdb",
        geoserver_url="",
    )
    mapped = publish_query_layer(
        settings,
        question="해운대구 건물 몇 채야?",
        sql=cnt,
        route="building_place_count",
        ok=True,
    )
    ok("no geoserver url → None", mapped is None)

    settings_gs = settings.with_overrides(
        geoserver_url="http://127.0.0.1:9/geoserver"
    )
    mapped_down = publish_query_layer(
        settings_gs,
        question="해운대구 건물 몇 채야?",
        sql=cnt,
        route="building_place_count",
        ok=True,
    )
    ok(
        "gs down keeps chat payload",
        isinstance(mapped_down, dict)
        and mapped_down.get("available") is False
        and mapped_down.get("error"),
        str(mapped_down),
    )

    client = GeoServerClient(settings)
    ok("client disabled without url", not client.enabled)

    result = AskResult(ok=True, answer="3채입니다", sql=cnt, route="building_place_count")
    dumped = result.to_dict()
    ok("askresult omits empty map", "map" not in dumped)
    result2 = AskResult(
        ok=True,
        answer="3채입니다",
        map={"available": False, "error": "down"},
    )
    ok("askresult keeps map", result2.to_dict().get("map", {}).get("error") == "down")

    print(f"\npassed={passed} failed={len(failed)}")
    for item in failed:
        print(" -", item)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
