"""지도 SQL wrap · 적격성 · GeoServer 실패 시 채팅 유지."""

from __future__ import annotations

from llm2sql.config import Settings
from llm2sql.map import (
    GeoServerClient,
    attach_map,
    is_safe_layer_name,
    publish_query_layer,
)
from llm2sql.map.sql import (
    boundary_sql,
    count_to_feature_sql,
    ensure_geometry_select,
    has_geometry_select,
    is_aggregate_sql,
    is_map_route,
    map_scope_key,
    pad_lonlat_extent,
    plan_map_sql,
)
from llm2sql.spatial_templates import (
    building_in_dong_count_sql,
    building_in_dong_list_sql,
    scoped_count_sql,
    scoped_list_sql,
)
from llm2sql.session import SessionContext
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
    ok("allow building name lookup", is_map_route("building_name_lookup"))
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

    unaliased = (
        'SELECT "A24", "A14"\n'
        'FROM "AL_D010_26_20250704"\n'
        'WHERE "A8" ILIKE \'%구서%\'\n'
        'ORDER BY "A14" DESC NULLS LAST\n'
        "LIMIT 1"
    )
    wrapped_u = ensure_geometry_select(unaliased, map_limit=2000)
    ok(
        "unaliased FROM does not treat WHERE as table",
        wrapped_u is not None
        and '"WHERE"' not in wrapped_u
        and '"AL_D010_26_20250704".geometry' in wrapped_u,
        str(wrapped_u)[:240],
    )
    join_on = (
        'SELECT b."A0" FROM "AL_D010_26_20250704" b\n'
        'JOIN "BND_ADM_DONG_PG" ON b."A8" = "BND_ADM_DONG_PG"."ADM_NM"'
    )
    wrapped_j = ensure_geometry_select(join_on, map_limit=2000)
    ok(
        "JOIN without alias does not treat ON as table",
        wrapped_j is not None and '"ON"' not in wrapped_j,
        str(wrapped_j)[:240],
    )

    already = 'SELECT b."A0", b.geometry FROM "AL_D010_26_20250704" b LIMIT 10;'
    again = ensure_geometry_select(already, map_limit=2000)
    ok(
        "no double geom",
        again is not None and again.lower().count("as geometry") <= 1,
        str(again),
    )

    lookup_sql = """
SELECT * FROM (
  SELECT DISTINCT ON ("A4", "A5", "A24") *
  FROM (
SELECT "A0"::text AS "A0", "A4"::text AS "A4", "A5"::text AS "A5", "A9"::text AS "A9", "A11"::text AS "A11", "A12"::float8 AS "A12", "A13"::text AS "A13", "A14"::float8 AS "A14", "A16"::float8 AS "A16", "A19"::text AS "A19", "A24"::text AS "A24", "A25"::text AS "A25", "A26"::float8 AS "A26"
FROM "AL_D010_26_20250704"
WHERE "A24" ILIKE '%구서역%' AND "A24" ILIKE '%포르투나%'
UNION ALL
SELECT "A0"::text AS "A0", "A4"::text AS "A4", "A7"::text AS "A5", "A25"::text AS "A9", "A23"::text AS "A11", "A18"::float8 AS "A12", "A34"::text AS "A13", "A19"::float8 AS "A14", "A30"::float8 AS "A16", "A0"::text AS "A19", "A13"::text AS "A24", "A25"::text AS "A25", "A31"::float8 AS "A26"
FROM "AL_D198_26260_20250115"
WHERE "A13" ILIKE '%구서역%' AND "A13" ILIKE '%포르투나%'
  ) AS named_hits
  ORDER BY "A4", "A5", "A24", "A14" DESC NULLS LAST
) AS named_dedup
ORDER BY "A24" NULLS LAST, "A14" DESC NULLS LAST
LIMIT 20;
""".strip()
    ok(
        "lookup nested star is not geom",
        not has_geometry_select(lookup_sql),
    )
    ok("lookup not aggregate", not is_aggregate_sql(lookup_sql))
    wrapped_lookup = ensure_geometry_select(lookup_sql, map_limit=2000)
    ok(
        "lookup wrap joins D010 geom",
        wrapped_lookup is not None
        and "AL_D010_26_20250704" in wrapped_lookup
        and "as geometry" in wrapped_lookup.lower()
        and "left join" in wrapped_lookup.lower(),
        str(wrapped_lookup)[:240],
    )
    ok(
        "lookup wrap keeps inner limit",
        wrapped_lookup is not None and "LIMIT 20" in wrapped_lookup.upper(),
        str(wrapped_lookup)[-80:] if wrapped_lookup else "",
    )
    plan_lookup = plan_map_sql(
        question="구서역포르투나를 찾아라",
        sql=lookup_sql,
        route="building_name_lookup",
        ok=True,
    )
    ok(
        "lookup plan is features",
        plan_lookup is not None and plan_lookup.kind == "features",
        str(plan_lookup),
    )
    ok(
        "lookup plan has geometry join",
        plan_lookup is not None and "src.geometry" in plan_lookup.sql,
        str(plan_lookup.sql if plan_lookup else "")[:200],
    )

    star_direct = 'SELECT * FROM "AL_D010_26_20250704" WHERE "A24" ILIKE \'%포르투나%\' LIMIT 5'
    ok("direct star from D010 is geom", has_geometry_select(star_direct))

    kind_c, cnt = scoped_count_sql("해운대구", None)
    plan_c = plan_map_sql(
        question="해운대구 건물 몇 채야?",
        sql=cnt,
        route="building_place_count",
        ok=True,
    )
    ok("count plan is features", plan_c is not None and plan_c.kind == "features")
    ok(
        "count plan has building geom",
        plan_c is not None
        and "geometry AS geometry" in plan_c.sql
        and "AL_D010" in plan_c.sql,
        str(plan_c.sql if plan_c else ""),
    )

    usage_count = (
        'SELECT COUNT(*) AS cnt\n'
        'FROM "AL_D010_26_20250704" b\n'
        'JOIN "BND_ADM_DONG_PG" d\n'
        "  ON ST_Intersects(b.geometry, d.geometry)\n"
        "WHERE d.\"ADM_NM\" = '구서1동' AND d.\"ADM_CD\" LIKE '21%' "
        "AND b.\"A9\" = '공동주택';"
    )
    ok("usage count is aggregate", is_aggregate_sql(usage_count))
    feat = count_to_feature_sql(usage_count, map_limit=2000)
    ok(
        "usage count → apartments",
        feat is not None
        and 'b."A9"' in feat
        and "공동주택" in feat
        and "구서1동" in feat
        and "b.geometry AS geometry" in feat
        and "COUNT(*)" not in feat.upper(),
        str(feat)[:240],
    )
    plan_u = plan_map_sql(
        question="구서1동의 아파트는?",
        sql=usage_count,
        route="building_admin_dong_usage_count",
        ok=True,
    )
    ok(
        "usage count plan is apartments",
        plan_u is not None
        and plan_u.kind == "features"
        and "공동주택" in plan_u.sql
        and "ST_Union" not in plan_u.sql,
        str(plan_u.sql if plan_u else "")[:200],
    )

    profile_one = (
        "SELECT COUNT(*) AS cnt, ROUND(AVG(b.\"A14\")::numeric, 1) AS avg_area\n"
        'FROM "AL_D010_26_20250704" b\n'
        'JOIN "BND_ADM_DONG_PG" d\n'
        "  ON ST_Intersects(b.geometry, d.geometry)\n"
        "WHERE d.\"ADM_NM\" = '구서1동' AND d.\"ADM_CD\" LIKE '21%' "
        "AND b.\"A9\" = '단독주택'"
    )
    ok(
        "profile agg → houses",
        count_to_feature_sql(profile_one) is not None
        and "단독주택" in (count_to_feature_sql(profile_one) or ""),
    )
    compare_sql = (
        profile_one
        + ";\n"
        + profile_one.replace("구서1동", "구서2동")
    )
    feat_cmp = count_to_feature_sql(compare_sql, map_limit=2000)
    ok(
        "compare union both dongs",
        feat_cmp is not None
        and "UNION ALL" in (feat_cmp or "")
        and "구서1동" in (feat_cmp or "")
        and "구서2동" in (feat_cmp or "")
        and "단독주택" in (feat_cmp or "")
        and "ST_Union" not in (feat_cmp or ""),
        str(feat_cmp)[:300],
    )
    plan_cmp = plan_map_sql(
        question="구서1동과 구서2동의 단독주택의 특성을 비교하라.",
        sql=compare_sql,
        route="building_profile_compare",
        ok=True,
    )
    ok(
        "compare plan is features not first-dong boundary",
        plan_cmp is not None
        and plan_cmp.kind == "features"
        and "구서2동" in plan_cmp.sql
        and "ADM_NM" in plan_cmp.sql,
        str(plan_cmp.sql if plan_cmp else "")[:240],
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

    industrial_count = (
        'SELECT COUNT(*) AS cnt\n'
        'FROM "AL_D010_26_20250704" b\n'
        "WHERE EXISTS (SELECT 1 FROM \"AL_D060_00_20250804\" i "
        "WHERE ST_Intersects(b.geometry, i.geometry)) "
        "AND b.\"A4\" LIKE '%사하구%';"
    )
    industrial_profile = (
        'SELECT COUNT(*) AS cnt, ROUND(AVG(b."A14")::numeric, 1) AS avg_area\n'
        'FROM "AL_D010_26_20250704" b\n'
        "WHERE EXISTS (SELECT 1 FROM \"AL_D060_00_20250804\" i "
        "WHERE ST_Intersects(b.geometry, i.geometry)) "
        "AND b.\"A4\" LIKE '%사하구%'"
    )
    plan_ind = plan_map_sql(
        question="사하구 산업단지 내 있는 건물은?",
        sql=industrial_count,
        route="buildings_in_industrial",
        ok=True,
    )
    plan_prof = plan_map_sql(
        question="해당 건물들의 특성은?",
        sql=industrial_profile,
        route="building_profile",
        ok=True,
    )
    ok("industrial count plan features", plan_ind is not None and plan_ind.kind == "features")
    ok("profile plan features", plan_prof is not None and plan_prof.kind == "features")
    ok(
        "profile same map scope as count",
        plan_ind is not None
        and plan_prof is not None
        and map_scope_key(plan_ind.sql) == map_scope_key(plan_prof.sql)
        and bool(map_scope_key(plan_ind.sql)),
        f"{map_scope_key(plan_ind.sql if plan_ind else '')[:180]} | {map_scope_key(plan_prof.sql if plan_prof else '')[:180]}",
    )
    other_count = industrial_count.replace("사하구", "금정구")
    plan_other = plan_map_sql(
        question="금정구 산업단지 내 있는 건물은?",
        sql=other_count,
        route="buildings_in_industrial",
        ok=True,
    )
    ok(
        "other gu different map scope",
        plan_ind is not None
        and plan_other is not None
        and map_scope_key(plan_ind.sql) != map_scope_key(plan_other.sql),
    )

    reuse_settings = Settings(
        database_url="postgresql://u:p@localhost:5432/gisdb",
        geoserver_url="",
    )
    sess = SessionContext()
    sess.last_map_scope = map_scope_key(plan_ind.sql if plan_ind else "")
    sess.last_map_payload = {
        "available": True,
        "layer": "temp_aaaaaaaaaaaaaaaa",
        "title": "사하구 산업단지 내 있는 건물은?",
    }
    reused = attach_map(
        {
            "ok": True,
            "sql": industrial_profile,
            "route": "building_profile",
        },
        reuse_settings,
        "해당 건물들의 특성은?",
        None,
        session=sess,
    )
    ok(
        "followup profile reuses layer",
        bool((reused.get("map") or {}).get("reused"))
        and (reused.get("map") or {}).get("layer") == "temp_aaaaaaaaaaaaaaaa",
        str(reused.get("map")),
    )

    bnd = boundary_sql("해운대구 건물 몇 채야?")
    ok("haeundae boundary", bnd is not None and "26350" in (bnd or ""))
    bnd_d = boundary_sql("구서동 건물 몇 채야?")
    ok("guseo boundary", bnd_d is not None and "구서" in (bnd_d or ""))

    tiny = pad_lonlat_extent([129.091, 35.247, 129.0912, 35.2472])
    ok("pad tiny span", tiny is not None and tiny[2] - tiny[0] >= 0.003)
    ok("pad adds margin", tiny is not None and tiny[0] < 129.091)
    none_ext = pad_lonlat_extent(None)
    ok("pad none", none_ext is None)

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
