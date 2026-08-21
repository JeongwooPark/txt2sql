"""법정동 경계 버퍼(ST_DWithin) 라우트."""

from __future__ import annotations

import sys

from llm2sql.domain import looks_like_building_name_lookup
from llm2sql.intent_router import try_route
from llm2sql.sql_validator import diagnose_sql


def main() -> int:
    failed: list[str] = []
    passed = 0

    q_list = "구서동 주변 100m안에 있는 건물은?"
    routed = try_route(q_list)
    if routed is None or routed.intent != "place_buffer_list":
        failed.append(f"목록 라우트: {None if routed is None else routed.intent}")
    elif "ST_DWithin" not in routed.sql or "BND_ADM_DONG_PG" not in routed.sql:
        failed.append(f"목록 SQL 공간함수 없음:\n{routed.sql}")
    elif "A24" in routed.sql and "주변" in routed.sql and "ILIKE" in routed.sql:
        failed.append("건물명 ILIKE '%주변%' 오탐")
    elif "100" not in routed.sql.split("ST_DWithin", 1)[-1]:
        failed.append(f"100m 미반영:\n{routed.sql}")
    else:
        passed += 1
        print("[list] OK ", routed.intent)

    diag = diagnose_sql(q_list, routed.sql if routed else "")
    if diag:
        failed.append(f"목록 diagnose: {diag}")
    else:
        passed += 1
        print("[diag] OK  목록 SQL")

    if looks_like_building_name_lookup(q_list):
        failed.append("목록 질의가 건물명 조회로 분류됨")
    else:
        passed += 1
        print("[name] OK  건물명 오탐 없음")

    q_count = "구서동 주변 100m 이내 건물은 몇 채야?"
    routed_c = try_route(q_count)
    if routed_c is None or routed_c.intent != "place_buffer_count":
        failed.append(f"건수 라우트: {None if routed_c is None else routed_c.intent}")
    elif "COUNT" not in routed_c.sql.upper():
        failed.append(f"건수 SQL COUNT 없음:\n{routed_c.sql}")
    else:
        passed += 1
        print("[count] OK ", routed_c.intent)

    q_km = "장전1동 반경 0.1km 안 건물 건수"
    routed_km = try_route(q_km)
    if routed_km is None or routed_km.intent != "place_buffer_count":
        failed.append(f"0.1km 라우트: {None if routed_km is None else routed_km.intent}")
    elif ", 100" not in routed_km.sql and "\n    100\n" not in routed_km.sql:
        failed.append(f"0.1km→100m 미반영:\n{getattr(routed_km, 'sql', '')}")
    elif "장전1동" not in (routed_km.sql if routed_km else "") or "[0-9]+동" in (
        routed_km.sql if routed_km else ""
    ):
        failed.append(f"행정동 정확 매칭 실패:\n{getattr(routed_km, 'sql', '')}")
    else:
        passed += 1
        print("[km] OK  0.1km → 100m, 장전1동 정확 매칭")

    q_inside = "수영동 안에 있는 건물 건수는?"
    routed_in = try_route(q_inside)
    if routed_in is None or routed_in.intent != "building_in_dong_spatial":
        failed.append(
            f"동 내부: {None if routed_in is None else routed_in.intent}"
        )
    else:
        passed += 1
        print("[inside] OK ", routed_in.intent)

    q_pt = "좌표(129.08, 35.16)에서 500미터 이내 건물 건수"
    routed_pt = try_route(q_pt)
    if routed_pt is None or routed_pt.intent != "buffer_count":
        failed.append(f"좌표 버퍼: {None if routed_pt is None else routed_pt.intent}")
    else:
        passed += 1
        print("[point] OK ", routed_pt.intent)

    q_h = "구서동에서 건물 높이가 50미터 이상인 건물은 몇 개야?"
    routed_h = try_route(q_h)
    if routed_h is not None and routed_h.intent.startswith("place_buffer"):
        failed.append(f"높이 임계가 지명 버퍼로 오탐: {routed_h.intent}")
    else:
        passed += 1
        print("[height] OK  버퍼 오탐 없음")

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
