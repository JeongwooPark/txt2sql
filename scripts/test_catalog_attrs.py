"""GIS건물통합·산업단지·행정구역·기초구역 전 속성 인식·라우트·SQL 실행 테스트."""

from __future__ import annotations

import sys
from typing import Any

from txt2sql.catalog_attrs import Attr, Dataset, all_attrs, parse_dataset
from txt2sql.catalog_attrs import BAS, BND, D010, D060
from txt2sql.config import load_settings
from txt2sql.db import connect, execute_query
from txt2sql.intent_router import try_route

PREFIX: dict[str, str] = {
    "d010": "GIS건물통합정보에서 해운대구",
    "d060": "산업단지_전국에서 부산",
    "bnd": "행정구역에서 해운대구",
    "bas": "도로명주소 기초구역에서 해운대구",
}

_NUMERIC_SAMPLE: dict[tuple[str, str], tuple[str, str]] = {
    ("d010", "A12"): ("50", ""),
    ("d010", "A14"): ("100", ""),
    ("d010", "A15"): ("100", ""),
    ("d010", "A16"): ("10", "미터"),
    ("d010", "A17"): ("30", ""),
    ("d010", "A18"): ("100", ""),
    ("d010", "A26"): ("5", "층"),
    ("d010", "A27"): ("1", "층"),
    ("bas", "BAS_AR"): ("10000", ""),
}


def _unit_q(ds: Dataset) -> str:
    return "채야" if ds.unit_count == "채" else "개야"


def _question_for(ds: Dataset, attr: Attr) -> str:
    prefix = PREFIX[ds.key]
    how = _unit_q(ds)
    if attr.kind == "numeric":
        sample, unit = _NUMERIC_SAMPLE[(ds.key, attr.col)]
        return f"{prefix}에서 {attr.label}이 {sample}{unit} 이상인 것은 몇 {how}?"
    if attr.kind == "date":
        year = 2020 if ds.key == "d010" else 2024
        if ds.key == "d060":
            year = 2012
        return f"{prefix}에서 {attr.label}가 {year}년 이후인 것은 몇 {how}?"
    if attr.values:
        alias, _stored = attr.values[0]
        if alias.isdigit() or alias in {"Y", "N"}:
            return f"{prefix}에서 {attr.label}가 {alias}인 것은 몇 {how}?"
        return f"{prefix}에서 {alias}인 것은 몇 {how}?"
    return f"{prefix}에서 {attr.label}가 있는 것은 몇 {how}?"


def _lookup_question(conn: Any, ds: Dataset, attr: Attr) -> str | None:
    if attr.kind == "numeric":
        return None
    row = conn.execute(
        f'''
        SELECT "{attr.col}" AS v
        FROM "{ds.table}"
        WHERE "{attr.col}" IS NOT NULL
          AND TRIM("{attr.col}"::text) <> ''
        LIMIT 1
        '''
    ).fetchone()
    if not row or row["v"] in (None, ""):
        return None
    value = str(row["v"]).strip()
    if len(value) > 40:
        value = value[:40]
    return f"{PREFIX[ds.key]}에서 {attr.label}가 {value}인 것"


def _ok_route(ds: Dataset, attr: Attr, routed: Any) -> list[str]:
    reasons: list[str] = []
    if routed is None:
        return ["라우트 없음"]
    if ds.table not in routed.sql:
        reasons.append(f"테이블 아님 ({ds.table})")
    if f'"{attr.col}"' not in routed.sql:
        reasons.append(f"SQL에 {attr.col} 없음")
    if not str(routed.intent).startswith(ds.intent_prefix):
        reasons.append(f"intent={routed.intent}")
    return reasons


def main() -> int:
    settings = load_settings()
    failed: list[str] = []
    passed = 0

    print("=== GIS건물통합·산업단지·행정구역·기초구역 속성 질의 테스트 ===\n")
    with connect(settings.database_url) as conn:
        regressions = [
            (
                "장전동의 산지에 있는 건물은?",
                "building_special_land_list",
                "AL_D010",
            ),
            (
                "구서역포르투나 아파트 정보",
                "building_name_lookup",
                "AL_D010",
            ),
            (
                "구서1동의 구서역포르투나 아파트를 찾아라",
                "building_name_lookup",
                "포르투나",
            ),
            (
                "용도별건물에서 동래구 건폐율이 50 이상인 건물은 몇 채야?",
                "d198_attr_count",
                "AL_D198",
            ),
            (
                "부산 산업단지는 몇 개야?",
                "industrial_count",
                "AL_D060",
            ),
            (
                "해운대구 기초구역은 몇 개야?",
                "bas_count",
                "TL_KODIS_BAS",
            ),
        ]
        for q_reg, intent, table in regressions:
            routed = try_route(q_reg, conn=conn)
            ok = (
                routed is not None
                and routed.intent == intent
                and table in routed.sql
            )
            status = "OK" if ok else "FAIL"
            print(f"[reg] {status}  {intent}")
            if ok:
                passed += 1
            else:
                got = None if routed is None else routed.intent
                failed.append(f"regression {q_reg} → {got}")
                print(f"       got={got}")

        q_find = "구서1동의 구서역포르투나 아파트를 찾아라"
        routed_find = try_route(q_find, conn=conn)
        if routed_find is None or routed_find.intent != "building_name_lookup":
            failed.append(
                f"구서역포르투나 찾기 route={None if routed_find is None else routed_find.intent}"
            )
        elif "찾아라" in routed_find.sql:
            failed.append("찾아라가 건물명 검색어로 들어감")
        elif "구서1동" in routed_find.sql:
            failed.append("행정동 구서1동이 법정동 A4 필터로 쓰임")
        elif "포르투나" not in routed_find.sql or "구서동" not in routed_find.sql:
            failed.append(f"포르투나/구서동 필터 없음: {routed_find.sql[:240]}")
        else:
            passed += 1
            print("[reg] OK  구서1동 포르투나 찾기")

        q_univ = "부산대학교를 찾아라"
        from txt2sql.clarify_qa import check_ambiguity
        from txt2sql.domain import looks_like_building_name_lookup

        if not looks_like_building_name_lookup(q_univ):
            failed.append("부산대학교 찾기가 건물명 조회로 안 잡힘")
        else:
            routed_univ = try_route(q_univ, conn=conn)
            clarify_univ = check_ambiguity(conn, q_univ)
            if clarify_univ is not None:
                failed.append(
                    f"부산대학교 찾기가 보완질문: {clarify_univ.intent} {clarify_univ.ambiguous_terms}"
                )
            elif routed_univ is None or routed_univ.intent != "building_name_lookup":
                failed.append(
                    f"부산대학교 route={None if routed_univ is None else routed_univ.intent}"
                )
            elif "찾아라" in routed_univ.sql:
                failed.append("부산대학교 SQL에 찾아라가 남음")
            elif "부산대학교" not in routed_univ.sql:
                failed.append(f"부산대학교 필터 없음: {routed_univ.sql[:200]}")
            else:
                passed += 1
                print("[reg] OK  부산대학교 찾기")

        for ds, attr in all_attrs():
            q = _question_for(ds, attr)
            parsed = parse_dataset(q, ds)
            routed = try_route(q, conn=conn)
            reasons: list[str] = []
            if parsed is None:
                reasons.append("미인식")
            reasons.extend(_ok_route(ds, attr, routed))
            if routed is not None and not reasons:
                try:
                    rows = execute_query(conn, routed.sql)
                except Exception as exc:  # noqa: BLE001
                    reasons.append(f"실행오류 {exc}")
                else:
                    if rows is None:
                        reasons.append("실행 결과 없음")

            ok = not reasons
            status = "OK" if ok else "FAIL"
            print(f"[{ds.key:4} {attr.col:12}] {status}  {attr.label}")
            print(f"       Q: {q}")
            if routed:
                print(f"       intent={routed.intent}")
            if reasons:
                print(f"       {'; '.join(reasons)}")
                failed.append(
                    f"{ds.key}.{attr.col} {attr.label}: {'; '.join(reasons)}"
                )
            else:
                passed += 1

            if attr.kind in {"id", "code", "text"}:
                lq = _lookup_question(conn, ds, attr)
                if not lq:
                    continue
                routed2 = try_route(lq, conn=conn)
                ok2 = (
                    routed2 is not None
                    and ds.table in routed2.sql
                    and f'"{attr.col}"' in routed2.sql
                )
                if ok2:
                    try:
                        execute_query(conn, routed2.sql)
                    except Exception as exc:  # noqa: BLE001
                        ok2 = False
                        failed.append(f"{ds.key}.{attr.col} lookup 실행오류 {exc}")
                if ok2:
                    passed += 1
                    print("       lookup OK")
                else:
                    failed.append(f"{ds.key}.{attr.col} lookup 실패: {lq}")
                    print(f"       lookup FAIL  Q: {lq}")

        rank_q = "GIS건물통합정보에서 해운대구에서 연면적이 가장 큰 것"
        r_rank = try_route(rank_q, conn=conn)
        ok_rank = (
            r_rank is not None
            and r_rank.intent == "d010_attr_rank"
            and '"A14"' in r_rank.sql
        )
        if ok_rank:
            execute_query(conn, r_rank.sql)
            passed += 1
            print("[rank] OK  GIS건물통합 연면적 최대")
        else:
            failed.append("d010 rank")
            print("[rank] FAIL  GIS건물통합 연면적 최대")

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
