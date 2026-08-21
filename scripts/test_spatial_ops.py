"""행정동·기초구역·건물 공간 연산 스모크 테스트."""

from __future__ import annotations

import sys
from typing import Any

from llm2sql.config import load_settings
from llm2sql.db import connect, execute_query
from llm2sql.intent_router import try_route

CASES: list[dict[str, Any]] = [
    {
        "id": "bldg_dong_count",
        "q": "구서1동 안에 있는 건물 건수는?",
        "intent": "building_in_dong_spatial",
        "sql_all": ["ST_Intersects", "BND_ADM_DONG", "COUNT"],
        "run": True,
    },
    {
        "id": "bldg_dong_list",
        "q": "구서1동 안에 있는 건물 목록을 보여줘",
        "intent": "building_in_dong_spatial_list",
        "sql_all": ["ST_Intersects", "BND_ADM_DONG"],
        "run": True,
    },
    {
        "id": "bldg_dong_cross",
        "q": "센서스 기반 행정구역 구서1동과 교차하는 건물은 몇 채야?",
        "intent": "building_in_dong_spatial",
        "sql_all": ["ST_Intersects", "BND_ADM_DONG"],
        "sql_none": ["행정구"],
        "run": True,
    },
    {
        "id": "bldg_dong_buffer",
        "q": "구서동 주변 100m안에 있는 건물은?",
        "intent": "place_buffer_list",
        "sql_all": ["ST_DWithin", "BND_ADM_DONG", "geography"],
        "run": True,
    },
    {
        "id": "bldg_dong_outside",
        "q": "구서1동 경계 밖 100m 이내 건물 건수는?",
        "intent": "place_buffer_outside_count",
        "sql_all": ["ST_DWithin", "NOT ST_Intersects"],
        "run": True,
    },
    {
        "id": "bldg_bas_gu",
        "q": "금정구 기초구역 안에 있는 건물 건수는?",
        "intent": "spatial_bldg_bas_count",
        "sql_all": ["ST_Intersects", "TL_KODIS_BAS", "AL_D010"],
        "run": True,
    },
    {
        "id": "bldg_bas_cross",
        "q": "도로명주소 기초구역과 교차하는 금정구 건물은 몇 채야?",
        "intent": "spatial_bldg_bas_count",
        "sql_all": ["ST_Intersects", "TL_KODIS_BAS", "금정구"],
        "sql_none": ["기초구"],
        "run": True,
    },
    {
        "id": "bldg_bas_list",
        "q": "해운대구 기초구역 안에 있는 건물 목록",
        "intent": "spatial_bldg_bas_list",
        "sql_all": ["ST_Intersects", "TL_KODIS_BAS", "해운대구"],
        "run": True,
    },
    {
        "id": "bldg_bas_id",
        "q": "기초구역번호 46237 안에 있는 건물 건수는?",
        "intent": "spatial_bldg_bas_count",
        "sql_all": ["ST_Intersects", "46237"],
        "run": True,
    },
    {
        "id": "bas_dong_count",
        "q": "구서1동과 교차하는 기초구역은 몇 개야?",
        "intent": "spatial_bas_dong_count",
        "sql_all": ["ST_Intersects", "BND_ADM_DONG", "TL_KODIS_BAS"],
        "run": True,
    },
    {
        "id": "bas_dong_list",
        "q": "구서1동과 겹치는 기초구역 목록을 보여줘",
        "intent": "spatial_bas_dong_list",
        "sql_all": ["ST_Intersects", "BAS_ID"],
        "run": True,
    },
    {
        "id": "bas_dong_within",
        "q": "구서1동 안에 완전히 들어가는 기초구역은 몇 개야?",
        "intent": "spatial_bas_dong_count",
        "sql_all": ["ST_Within", "구서1동"],
        "run": True,
    },
    {
        "id": "bas_dong_touch",
        "q": "구서1동과 인접한 기초구역은?",
        "intent": "spatial_bas_dong_list",
        "sql_all": ["ST_Intersects", "ST_Within", "구서1동"],
        "run": True,
    },
    {
        "id": "bas_dong_buffer",
        "q": "구서1동 주변 100m 이내 기초구역 개수는?",
        "intent": "spatial_bas_dong_buffer_count",
        "sql_all": ["ST_DWithin", "TL_KODIS_BAS"],
        "run": True,
    },
    {
        "id": "bas_bnd_gu",
        "q": "센서스 기반 행정구역과 교차하는 도로명주소 기초구역 중 금정구는 몇 개야?",
        "intent": "spatial_bas_bnd_gu_count",
        "sql_all": ["ST_Intersects", "BND_ADM_DONG", "금정구"],
        "sql_none": ["행정구"],
        "run": True,
    },
    {
        "id": "dong_touch",
        "q": "구서1동과 인접한 행정동은?",
        "intent": "spatial_dong_touch_list",
        "sql_all": ["ST_Intersects", "BND_ADM_DONG"],
        "sql_none": ["ILIKE '%구서1동%'"],
        "run": True,
    },
    {
        "id": "legal_admin_members",
        "q": "연산동 내에 행정동은 무엇이 있어?",
        "intent": "legal_dong_admin_members",
        "sql_all": ["BND_ADM_DONG", "연산", "ADM_NM"],
        "sql_none": ["ILIKE '%연산동%'"],
        "run": True,
    },
    {
        "id": "bas_nearest",
        "q": "구서1동에서 가장 가까운 기초구역은?",
        "intent": "spatial_bas_dong_nearest",
        "sql_all": ["<->", "TL_KODIS_BAS"],
        "run": True,
    },
    {
        "id": "point_buffer",
        "q": "좌표(129.08, 35.16)에서 500미터 이내 건물 건수",
        "intent": "buffer_count",
        "sql_all": ["ST_DWithin", "ST_MakePoint"],
        "run": True,
    },
    {
        "id": "dong_inside_reg",
        "q": "수영동 안에 있는 건물 건수는?",
        "intent": "building_in_dong_spatial",
        "sql_all": ["ST_Intersects", "BND_ADM_DONG"],
        "run": True,
    },
    {
        "id": "bas_attr_count",
        "q": "해운대구 기초구역 개수는?",
        "intent": "bas_count",
        "sql_all": ["TL_KODIS_BAS", "해운대구"],
        "sql_none": ["ST_"],
        "run": True,
    },
    {
        "id": "legal_share_bldg",
        "q": "구서동에 있는 건물이 구서1동에 몇%, 구서2동에 몇%있는가?",
        "intent": "legal_dong_admin_share",
        "sql_all": ["ST_Intersects", "구서1동", "구서2동", "pct", "GROUP BY"],
        "sql_none": ["building_place_count", "퍼센트씩"],
        "run": True,
    },
    {
        "id": "legal_share_apt",
        "q": "구서동에 있는 아파트는 구서1동과 구서2동에 몇 퍼센트씩 있는가?",
        "intent": "legal_dong_admin_share",
        "sql_all": ["공동주택", "구서1동", "구서2동", "pct"],
        "sql_none": ["ILIKE '%퍼센트"],
        "run": True,
    },
]


def _check_sql(sql: str, case: dict[str, Any]) -> str | None:
    for token in case.get("sql_all") or []:
        if token.lower() not in sql.lower() and token not in sql:
            return f"SQL에 '{token}' 없음"
    for token in case.get("sql_none") or []:
        if token in sql:
            return f"SQL에 금지 토큰 '{token}'"
    return None


def main() -> int:
    failed: list[str] = []
    passed = 0
    settings = load_settings()

    print("=== 1) 라우트 매칭 ===\n")
    routed_sql: dict[str, str] = {}
    for case in CASES:
        q = case["q"]
        routed = try_route(q)
        intent = None if routed is None else routed.intent
        sql = "" if routed is None else routed.sql
        routed_sql[case["id"]] = sql
        ok = intent == case["intent"]
        detail = _check_sql(sql, case) if ok else f"intent={intent}"
        if ok and detail is None:
            passed += 1
            print(f"[OK] {case['id']}: {intent}")
        else:
            failed.append(f"{case['id']}: {q}\n    {detail or intent}\n    {sql[:240]}")
            print(f"[FAIL] {case['id']}: {detail or intent}")

    print("\n=== 2) SQL 실행 스모크 ===\n")
    with connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '60000'")
        for case in CASES:
            if not case.get("run"):
                continue
            sql = routed_sql.get(case["id"]) or ""
            if not sql or case["id"] in {f.split(":")[0] for f in failed}:
                continue
            try:
                rows = execute_query(conn, sql, default_limit=20)
                n = len(rows)
                preview = ""
                if rows:
                    row0 = rows[0]
                    keys = [k for k in row0 if k in {"cnt", "ADM_NM", "BAS_ID", "A4", "A24", "dist_m"}]
                    preview = str({k: row0[k] for k in keys})[:120]
                print(f"[OK] {case['id']} rows={n} {preview}")
                passed += 1
            except Exception as exc:  # noqa: BLE001
                failed.append(f"{case['id']} 실행: {exc}")
                print(f"[FAIL] {case['id']} 실행: {exc}")

    total = passed + len(failed)
    print(f"\n=== 결과: {passed}/{total} OK ===")
    if failed:
        print("실패:")
        for item in failed:
            print(" -", item)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
