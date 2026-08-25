"""용도별건물공간정보(AL_D198) 전 속성 인식·라우트·SQL 실행 테스트."""

from __future__ import annotations

import sys
from typing import Any

from txt2sql.config import load_settings
from txt2sql.d198_attrs import D198_ATTRS, D198Attr, parse_d198_question
from txt2sql.db import connect, execute_query
from txt2sql.intent_router import try_route

DONGRAE = "AL_D198_26260_20250115"
PREFIX = "용도별건물에서 동래구"


def _question_for(attr: D198Attr) -> str:
    col = attr.col
    if attr.kind == "numeric":
        sample = {
            "A17": 200,
            "A18": 80,
            "A19": 200,
            "A20": 100,
            "A21": 40,
            "A30": 10,
            "A31": 3,
            "A32": 1,
        }[col]
        unit = {"A30": "미터", "A31": "층", "A32": "층"}.get(col, "")
        return f"{PREFIX}에서 {attr.label}이 {sample}{unit} 이상인 건물은 몇 채야?"
    if attr.kind == "date":
        if col == "A35":
            return f"{PREFIX}에서 {attr.label}가 있는 건물은 몇 채야?"
        year = 2020 if col == "A33" else 2000
        rel = "이후" if col == "A33" else "이전"
        return f"{PREFIX}에서 {attr.label}가 {year}년 {rel}인 건물은 몇 채야?"
    if attr.values:
        alias, _stored = attr.values[0]
        if alias.isdigit():
            return f"{PREFIX}에서 {attr.label}가 {alias}인 건물은 몇 채야?"
        return f"{PREFIX}에서 {alias}인 건물은 몇 채야?"
    if col == "A4":
        return f"{PREFIX} 온천동 건물은 몇 채야?"
    if col == "A7":
        return f"{PREFIX}에서 지번이 있는 건물은 몇 채야?"
    if col == "A13":
        return f"{PREFIX}에서 건물명이 있는 건물은 몇 채야?"
    if col == "A14":
        return f"{PREFIX}에서 건물동명이 있는 건물은 몇 채야?"
    if attr.kind in {"id", "code"}:
        return f"{PREFIX}에서 {attr.label}가 있는 건물은 몇 채야?"
    return f"{PREFIX}에서 {attr.label}가 있는 건물은 몇 채야?"


def _expect_col_in_sql(attr: D198Attr, sql: str) -> bool:
    if f'"{attr.col}"' in sql:
        return True
    # 코드/이름 쌍은 짝 컬럼으로 필터될 수 있음
    pairs = {
        "A5": "A6",
        "A6": "A5",
        "A9": "A10",
        "A10": "A9",
        "A11": "A12",
        "A12": "A11",
        "A15": "A16",
        "A16": "A15",
        "A22": "A23",
        "A23": "A22",
        "A24": "A25",
        "A25": "A24",
        "A26": "A27",
        "A27": "A26",
        "A28": "A29",
        "A29": "A28",
    }
    alt = pairs.get(attr.col)
    return bool(alt and f'"{alt}"' in sql)


def _lookup_question(conn: Any, attr: D198Attr) -> str | None:
    """실제 값으로 동등 조회 문항을 만든다 (id/code/text)."""
    if attr.kind == "numeric":
        return None
    row = conn.execute(
        f'''
        SELECT "{attr.col}" AS v
        FROM "{DONGRAE}"
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
    return f"{PREFIX}에서 {attr.label}가 {value}인 건물"


def main() -> int:
    settings = load_settings()
    failed: list[str] = []
    passed = 0
    cases = list(D198_ATTRS)

    print("=== 용도별건물공간정보 속성 질의 테스트 ===\n")
    with connect(settings.database_url) as conn:
        # 1) D010 회귀: 산지는 여전히 건물통합정보
        q_reg = "장전동의 산지에 있는 건물은?"
        routed = try_route(q_reg, conn=conn)
        ok_reg = (
            routed is not None
            and routed.intent == "building_special_land_list"
            and "AL_D010" in routed.sql
        )
        status = "OK" if ok_reg else "FAIL"
        print(f"[reg] {status}  D010 산지 유지")
        if ok_reg:
            passed += 1
        else:
            failed.append(
                f"regression {q_reg} → {None if routed is None else routed.intent}"
            )

        for attr in cases:
            q = _question_for(attr)
            parsed = parse_d198_question(q)
            routed = try_route(q, conn=conn)
            reasons: list[str] = []
            if parsed is None:
                reasons.append("미인식")
            if routed is None:
                reasons.append("라우트 없음")
            else:
                if "AL_D198" not in routed.sql:
                    reasons.append("D198 테이블 아님")
                if not _expect_col_in_sql(attr, routed.sql):
                    reasons.append(f"SQL에 {attr.col} 없음")
                try:
                    rows = execute_query(conn, routed.sql)
                except Exception as exc:  # noqa: BLE001
                    reasons.append(f"실행오류 {exc}")
                    rows = None
                else:
                    if rows is None:
                        reasons.append("실행 결과 없음")

            ok = not reasons
            status = "OK" if ok else "FAIL"
            print(f"[{attr.col:3}] {status}  {attr.label}")
            print(f"       Q: {q}")
            if routed:
                print(f"       intent={routed.intent}")
            if reasons:
                print(f"       {'; '.join(reasons)}")
                failed.append(f"{attr.col} {attr.label}: {'; '.join(reasons)}")
            else:
                passed += 1

            # id/code/text는 실제 값 lookup도 한 번 더
            if attr.kind in {"id", "code", "text"} and attr.col not in {"A4"}:
                lq = _lookup_question(conn, attr)
                if not lq:
                    continue
                routed2 = try_route(lq, conn=conn)
                ok2 = (
                    routed2 is not None
                    and "AL_D198" in routed2.sql
                    and _expect_col_in_sql(attr, routed2.sql)
                )
                if ok2:
                    try:
                        execute_query(conn, routed2.sql)
                    except Exception as exc:  # noqa: BLE001
                        ok2 = False
                        failed.append(f"{attr.col} lookup 실행오류 {exc}")
                if ok2:
                    passed += 1
                    print(f"       lookup OK")
                else:
                    failed.append(f"{attr.col} lookup 실패: {lq}")
                    print(f"       lookup FAIL  Q: {lq}")

        # 2) 금정구 전용 문항 한 건
        q_gj = "용도별건물에서 금정구 건폐율이 50 이상인 건물은 몇 채야?"
        r_gj = try_route(q_gj, conn=conn)
        ok_gj = (
            r_gj is not None
            and "AL_D198_26410" in r_gj.sql
            and '"A21"' in r_gj.sql
        )
        if ok_gj:
            execute_query(conn, r_gj.sql)
            passed += 1
            print("[gj ] OK  금정구 건폐율")
        else:
            failed.append("금정구 건폐율")
            print("[gj ] FAIL  금정구 건폐율")

        # 3) 데이터셋 없이 전용 값
        q_ex = "동래구 집합건축물은 몇 채야?"
        r_ex = try_route(q_ex, conn=conn)
        ok_ex = (
            r_ex is not None
            and "AL_D198" in r_ex.sql
            and ("A10" in r_ex.sql or "집합건축물" in r_ex.sql)
        )
        if ok_ex:
            execute_query(conn, r_ex.sql)
            passed += 1
            print("[ex ] OK  집합건축물(데이터셋명 없이)")
        else:
            failed.append("집합건축물 exclusive")
            print("[ex ] FAIL  집합건축물 exclusive")

        # 4) 달력 연도 '2020년 이후 지어진' ≠ 경과년수 2020년
        q_cal = "금정구에서 2020년 이후에 지어진 아파트는?"
        r_cal = try_route(q_cal, conn=conn)
        sql_cal = "" if r_cal is None else r_cal.sql
        ok_cal = (
            r_cal is not None
            and "AL_D198_26410" in sql_cal
            and "INTERVAL" not in sql_cal.upper()
            and "2020-01-01" in sql_cal
            and '"A34"' in sql_cal
        )
        if ok_cal:
            rows_cal = execute_query(conn, sql_cal)
            if not rows_cal:
                ok_cal = False
                failed.append("2020년 이후 지어진 아파트 실행 결과 없음")
            else:
                passed += 1
                print("[cal] OK  금정구 2020년 이후 지어진 아파트")
                print(f"       intent={r_cal.intent}")
        if not ok_cal and "2020년 이후 지어진 아파트 실행 결과 없음" not in failed:
            failed.append("2020년 이후 지어진 아파트")
            print("[cal] FAIL  금정구 2020년 이후 지어진 아파트")
            if r_cal is not None:
                print(f"       intent={r_cal.intent}")
                print(sql_cal)

        # 5) 가장 최근에 지어진 → D198 A34, D010 A13 집계 금지
        q_rec = "금정구에서 가장 최근에 지어진 아파트는?"
        r_rec = try_route(q_rec, conn=conn)
        sql_rec = "" if r_rec is None else r_rec.sql
        ok_rec = (
            r_rec is not None
            and r_rec.intent == "d198_attr_rank"
            and "AL_D198_26410" in sql_rec
            and "AL_D010" not in sql_rec
            and "GROUP BY" not in sql_rec.upper()
            and '"A34"' in sql_rec
            and "DESC" in sql_rec.upper()
        )
        if ok_rec:
            rows_rec = execute_query(conn, sql_rec)
            if not rows_rec or not rows_rec[0].get("A34"):
                ok_rec = False
                failed.append("가장 최근 지어진 아파트 날짜 없음")
            else:
                passed += 1
                print("[rec] OK  금정구 가장 최근 지어진 아파트")
                print(f"       {rows_rec[0].get('A13')} {rows_rec[0].get('A34')}")
        if not ok_rec and "가장 최근 지어진 아파트 날짜 없음" not in failed:
            failed.append("가장 최근 지어진 아파트")
            print("[rec] FAIL  금정구 가장 최근 지어진 아파트")
            if r_rec is not None:
                print(f"       intent={r_rec.intent}")
                print(sql_rec)

        q_exd = (
            "금정구에서 건설일이 없는 것은 제외하고 "
            "그 중에서 가장 최근에 지어진 아파트를 찾아줘"
        )
        r_exd = try_route(q_exd, conn=conn)
        sql_exd = "" if r_exd is None else r_exd.sql
        ok_exd = (
            r_exd is not None
            and "AL_D198_26410" in sql_exd
            and "AL_D010" not in sql_exd
            and "INTERVAL" not in sql_exd.upper()
            and "GROUP BY" not in sql_exd.upper()
            and '"A34"' in sql_exd
        )
        if ok_exd:
            rows_exd = execute_query(conn, sql_exd)
            if not rows_exd or not rows_exd[0].get("A34"):
                ok_exd = False
                failed.append("건설일 제외 단독 질의 날짜 없음")
            else:
                passed += 1
                print("[exd] OK  건설일 제외 단독")
                print(f"       {rows_exd[0].get('A13')} {rows_exd[0].get('A34')}")
        if not ok_exd and "건설일 제외 단독 질의 날짜 없음" not in failed:
            failed.append("건설일 제외 단독")
            print("[exd] FAIL  건설일 제외 단독")
            if r_exd is not None:
                print(sql_exd)

        from txt2sql.answer import format_success_template
        from txt2sql.d198_attrs import parse_year_stats

        q_year = "각년도별 아파트 건립 수는?"
        spec_y = parse_year_stats(q_year)
        r_year = try_route(q_year, conn=conn)
        sql_year = "" if r_year is None else r_year.sql
        ok_year = (
            spec_y is not None
            and spec_y.mode == "year"
            and r_year is not None
            and r_year.intent == "d198_year_stats"
            and "GROUP BY" in sql_year.upper()
            and '"A34"' in sql_year
            and "아파트" in sql_year
            and "AL_D010" not in sql_year
        )
        if ok_year:
            rows_year = execute_query(conn, sql_year)
            if not rows_year:
                ok_year = False
                failed.append("연도별 아파트 건립 결과 없음")
            else:
                passed += 1
                print("[yr] OK  각년도별 아파트 건립")
                print(f"       years={len(rows_year)} first={rows_year[0]}")
        if not ok_year and "연도별 아파트 건립 결과 없음" not in failed:
            failed.append("각년도별 아파트 건립")
            print("[yr] FAIL")
            if r_year is not None:
                print(sql_year)

        q_dec = (
            "70년대, 80년대, 90년대, 2000년대, 2010년대, 2020년대의 "
            "단독추택 건립 수는?"
        )
        spec_d = parse_year_stats(q_dec)
        r_dec = try_route(q_dec, conn=conn)
        sql_dec = "" if r_dec is None else r_dec.sql
        ok_dec = (
            spec_d is not None
            and spec_d.mode == "decade"
            and spec_d.decades == (1970, 1980, 1990, 2000, 2010, 2020)
            and r_dec is not None
            and r_dec.intent == "d198_year_stats"
            and "단독주택" in sql_dec
            and "decade" in sql_dec
            and "1970" in sql_dec
        )
        if ok_dec:
            rows_dec = execute_query(conn, sql_dec)
            ans_dec = format_success_template(
                q_dec,
                sql=sql_dec,
                rows=rows_dec,
                row_count=len(rows_dec),
                route="d198_year_stats",
            )
            if "1970년대" not in ans_dec or "2020년대" not in ans_dec:
                ok_dec = False
                failed.append("연대별 답변 형식")
            else:
                passed += 1
                print("[dec] OK  연대별 단독주택 건립")
                print("      ", ans_dec.replace("\n", " | ")[:220])
        if not ok_dec and "연대별 답변 형식" not in failed:
            failed.append("연대별 단독주택 건립")
            print("[dec] FAIL")
            if r_dec is not None:
                print(sql_dec)

        from txt2sql.d198_attrs import (
            is_year_grain_followup,
            parse_year_stats,
            rows_as_decade_counts,
            wrap_year_sql_as_decade,
            year_stats_grain,
        )
        from txt2sql.pipeline import _expand_followup_question, ask
        from txt2sql.session import SessionContext

        year_rows_src = (
            rows_year
            if ok_year
            else [{"year": 2010, "n": 3}, {"year": 2018, "n": 2}]
        )
        ok_grain = True
        q_grain_sp = "10년 단위로 출력하라"
        if year_stats_grain(q_grain_sp) != 10:
            ok_grain = False
            failed.append("공백 있는 10년 단위 grain 실패")
        sess_sp = SessionContext()
        sess_sp.update_from_result(
            "각년도별 아파트 건립 수는?",
            {
                "ok": True,
                "route": "d198_year_stats",
                "sql": sql_year
                or 'SELECT 2010 AS year, 3 AS n FROM "AL_D198_26410_20250115"',
                "answer": "연도별",
                "rows": year_rows_src,
                "tables": ["AL_D198_26410_20250115"],
            },
        )
        sess_sp.last_rows = []
        sess_sp.last_route = "d198_attr_list"
        if not is_year_grain_followup(q_grain_sp, sess_sp):
            ok_grain = False
            failed.append("rows 비어도 10년 단위 후속이어야 함")
        result_sp = ask(q_grain_sp, settings, session=sess_sp)
        sql_sp = str(result_sp.get("sql") or "")
        ans_sp = str(result_sp.get("answer") or "")
        print("[10ys] spaced route", result_sp.get("route"), "n=", len(result_sp.get("rows") or []))
        print("       ", ans_sp.replace("\n", " | ")[:200])
        if result_sp.get("route") != "d198_year_stats":
            ok_grain = False
            failed.append(f"공백 10년 단위 route={result_sp.get('route')}")
        if "서울" in sql_sp or "AL_D010" in sql_sp or "A35" in sql_sp:
            ok_grain = False
            failed.append("공백 10년 단위가 D010 SQL")
        if "년대" not in ans_sp:
            ok_grain = False
            failed.append("공백 10년 단위 답에 년대 없음")

        q_grain = "10년단위로 출력하라"
        merged_grain = "각년도별 아파트 건립 수는? 10년단위로 출력하라"
        spec_g = parse_year_stats(merged_grain)
        if not (
            year_stats_grain(q_grain) == 10
            and spec_g is not None
            and spec_g.mode == "decade"
        ):
            ok_grain = False
            failed.append("10년단위 parse")
        sess_g = SessionContext()
        sess_g.update_from_result(
            "각년도별 아파트 건립 수는?",
            {
                "ok": True,
                "route": "d198_year_stats",
                "sql": sql_year
                or 'SELECT 2010 AS year, 3 AS n FROM "AL_D198_26410_20250115"',
                "answer": "연도별",
                "rows": year_rows_src,
                "tables": ["AL_D198_26410_20250115"],
            },
        )
        if not is_year_grain_followup(q_grain, sess_g):
            ok_grain = False
            failed.append("10년단위 후속 미인식")
        exp_g = _expand_followup_question(q_grain, sess_g)
        if "각년도별" not in exp_g or "10년" not in exp_g:
            ok_grain = False
            failed.append(f"10년단위 병합 실패: {exp_g}")
        wrap = wrap_year_sql_as_decade(sess_g.last_sql or "")
        if "AS decade" not in wrap or "서울" in wrap or "AL_D010" in wrap:
            ok_grain = False
            failed.append("10년 SQL이 D010/서울로 변환됨")
        result_g = ask(q_grain, settings, session=sess_g)
        sql_g = str(result_g.get("sql") or "")
        ans_g = str(result_g.get("answer") or "")
        print("[10y] route", result_g.get("route"), "n=", len(result_g.get("rows") or []))
        print("      ", ans_g.replace("\n", " | ")[:240])
        if result_g.get("route") != "d198_year_stats":
            ok_grain = False
            failed.append(f"10년단위 route={result_g.get('route')}")
        if "서울" in sql_g or "AL_D010" in sql_g:
            ok_grain = False
            failed.append("10년단위 SQL이 서울/D010")
        if "년대" not in ans_g:
            ok_grain = False
            failed.append("10년단위 답에 년대 없음")
        if "A30" in sql_g:
            ok_grain = False
            failed.append("10년단위가 A30 오류 SQL")
        if ok_grain:
            passed += 1
            print("[10y] OK  연도별 → 10년 단위 후속")
        elif "10년단위 후속 미인식" not in failed and "10년단위 SQL이 서울/D010" not in failed:
            failed.append("10년단위 후속")

        from txt2sql.d198_attrs import rows_as_bin_counts, wrap_year_sql_as_bin

        ok_5 = True
        q_5 = "5년 단위로 출력하라"
        merged_5 = "각년도별 아파트 건립 수는? 5년 단위로 출력하라"
        spec_5 = parse_year_stats(merged_5)
        if not (
            year_stats_grain(q_5) == 5
            and year_stats_grain("5년단위로") == 5
            and spec_5 is not None
            and spec_5.mode == "bin"
            and spec_5.bin_years == 5
        ):
            ok_5 = False
            failed.append("5년단위 parse")
        sess_5 = SessionContext()
        sess_5.update_from_result(
            "각년도별 아파트 건립 수는?",
            {
                "ok": True,
                "route": "d198_year_stats",
                "sql": sql_year
                or 'SELECT 2010 AS year, 3 AS n FROM "AL_D198_26410_20250115"',
                "answer": "연도별",
                "rows": year_rows_src,
                "tables": ["AL_D198_26410_20250115"],
            },
        )
        if not is_year_grain_followup(q_5, sess_5):
            ok_5 = False
            failed.append("5년단위 후속 미인식")
        local_5 = rows_as_bin_counts(year_rows_src, 5)
        if not local_5 or "period" not in local_5[0]:
            ok_5 = False
            failed.append("5년 로컬 재집계 실패")
        wrap_5 = wrap_year_sql_as_bin(sess_5.last_sql or "", 5)
        if "AS period" not in wrap_5 or "서울" in wrap_5 or "AL_D010" in wrap_5:
            ok_5 = False
            failed.append("5년 SQL 변환 실패")
        result_5 = ask(q_5, settings, session=sess_5)
        sql_5 = str(result_5.get("sql") or "")
        ans_5 = str(result_5.get("answer") or "")
        print("[5y] route", result_5.get("route"), "n=", len(result_5.get("rows") or []))
        print("     ", ans_5.replace("\n", " | ")[:240])
        if result_5.get("route") != "d198_year_stats":
            ok_5 = False
            failed.append(f"5년단위 route={result_5.get('route')}")
        if "서울" in sql_5 or "AL_D010" in sql_5:
            ok_5 = False
            failed.append("5년단위 SQL이 서울/D010")
        if "~" not in ans_5:
            ok_5 = False
            failed.append("5년단위 답에 구간(~) 없음")
        if ok_5:
            passed += 1
            print("[5y] OK  연도별 → 5년 단위 후속")
        elif "5년단위 후속 미인식" not in failed:
            failed.append("5년단위 후속")

        from txt2sql.d198_attrs import parse_value_bin, year_stats_grain as ygrain

        ok_var = True
        if ygrain("이십년 단위로 출력하라") != 20:
            ok_var = False
            failed.append("이십년 grain이 20이 아님")
        if ygrain("삼년 단위로 출력하라") != 3:
            ok_var = False
            failed.append("삼년 grain 실패")
        if ygrain("5년씩 출력하라") != 5:
            ok_var = False
            failed.append("5년씩 grain 실패")
        gj_base = "금정구 각년도별 아파트 건립 수는?"
        sess_gj = SessionContext()
        r_gj = ask(gj_base, settings, session=sess_gj)
        if r_gj.get("route") != "d198_year_stats" or "26410" not in str(
            r_gj.get("sql") or ""
        ):
            ok_var = False
            failed.append("금정구 연도별 기본 질의")
        for q_f, expect_n, token in (
            ("5년씩 출력하라", 5, "~"),
            ("삼년 단위로 출력하라", 3, "~"),
            ("이십년 단위로 출력하라", 20, "~"),
        ):
            sess_f = SessionContext()
            ask(gj_base, settings, session=sess_f)
            r_f = ask(q_f, settings, session=sess_f)
            sql_f = str(r_f.get("sql") or "")
            ans_f = str(r_f.get("answer") or "")
            print(f"[gj {q_f}] route={r_f.get('route')} n={len(r_f.get('rows') or [])}")
            if r_f.get("route") != "d198_year_stats":
                ok_var = False
                failed.append(f"금정 후속 route {q_f}={r_f.get('route')}")
            if "AL_D010" in sql_f or "서울" in sql_f:
                ok_var = False
                failed.append(f"금정 후속 D010 {q_f}")
            if "금정구" not in ans_f:
                ok_var = False
                failed.append(f"금정 후속 답 범위 {q_f}")
            if token not in ans_f:
                ok_var = False
                failed.append(f"금정 후속 구간표시 {q_f}")
            if f"/ {expect_n})" not in sql_f.replace(" ", "") and (
                f"/ {expect_n})" not in sql_f
            ):
                if f"/ {expect_n}" not in sql_f:
                    ok_var = False
                    failed.append(f"금정 후속 단위 {q_f} sql={sql_f[:80]}")
        if ok_var:
            passed += 1
            print("[gj-y] OK  금정구 N년 단위 후속 예시")
        elif "금정구 연도별 기본 질의" not in failed:
            failed.append("금정구 N년 단위 후속")

        ok_area = True
        q_area = "금정구 아파트 연면적 크기별 수는?"
        spec_a = parse_value_bin(q_area)
        r_area = try_route(q_area, conn=conn)
        sql_area = "" if r_area is None else r_area.sql
        if not (
            spec_a is not None
            and spec_a.col == "A19"
            and spec_a.bin_width == 1000
            and r_area is not None
            and r_area.intent == "d198_value_bins"
            and '"A19"' in sql_area
            and "AL_D010" not in sql_area
        ):
            ok_area = False
            failed.append("연면적 크기별 parse/route")
        result_area = ask(q_area, settings)
        ans_area = str(result_area.get("answer") or "")
        sql_ar = str(result_area.get("sql") or "")
        print("[area] route", result_area.get("route"), "n=", len(result_area.get("rows") or []))
        print("      ", ans_area.replace("\n", " | ")[:240])
        if result_area.get("route") != "d198_value_bins":
            ok_area = False
            failed.append(f"연면적 크기별 route={result_area.get('route')}")
        if "AL_D010" in sql_ar or "크기별" in sql_ar:
            ok_area = False
            failed.append("연면적 크기별이 건물명/D010")
        if "㎡" not in ans_area or "금정구" not in ans_area:
            ok_area = False
            failed.append("연면적 크기별 답 형식")

        sess_a = SessionContext()
        ask(q_area, settings, session=sess_a)
        r_100 = ask("100㎡ 단위로 출력하라", settings, session=sess_a)
        sql_100 = str(r_100.get("sql") or "")
        ans_100 = str(r_100.get("answer") or "")
        print("[100m2] route", r_100.get("route"), "n=", len(r_100.get("rows") or []))
        if r_100.get("route") != "d198_value_bins":
            ok_area = False
            failed.append(f"100㎡ 후속 route={r_100.get('route')}")
        if "/ 100)" not in sql_100.replace(" ", "") and "/ 100" not in sql_100:
            ok_area = False
            failed.append("100㎡ SQL 단위")
        if "AL_D010" in sql_100:
            ok_area = False
            failed.append("100㎡ 후속이 D010")
        if len(r_100.get("rows") or []) <= 34:
            ok_area = False
            failed.append("100㎡ 구간이 1000㎡보다 세밀하지 않음")

        sess_ya = SessionContext()
        ask(gj_base, settings, session=sess_ya)
        r_ya = ask("면적 크기 단위별로 출력하라", settings, session=sess_ya)
        print("[ya] route", r_ya.get("route"), "n=", len(r_ya.get("rows") or []))
        print("    ", str(r_ya.get("answer") or "").replace("\n", " | ")[:200])
        if r_ya.get("route") != "d198_value_bins":
            ok_area = False
            failed.append(f"연도→면적 후속 route={r_ya.get('route')}")
        if "AL_D010" in str(r_ya.get("sql") or ""):
            ok_area = False
            failed.append("연도→면적 후속이 D010")
        if ok_area:
            passed += 1
            print("[area] OK  면적 크기 단위별·후속")
        elif "연면적 크기별 parse/route" not in failed:
            failed.append("면적 크기 단위별")

        from txt2sql.d198_attrs import looks_like_value_bin_question

        ok_bind = True
        q_guseo = "구서동의 면적별 아파트의 숫자를 구하라"
        q_bind = "2000단위로 묶어라"
        if not looks_like_value_bin_question(q_guseo):
            ok_bind = False
            failed.append("면적별 아파트 숫자 미인식")
        if not looks_like_value_bin_question(q_bind):
            ok_bind = False
            failed.append("2000단위로 묶어라 미인식")
        spec_bind = parse_value_bin(f"{q_guseo} {q_bind}")
        if spec_bind is None or spec_bind.bin_width != 2000 or spec_bind.col != "A19":
            ok_bind = False
            failed.append(f"2000 구간 spec={spec_bind}")
        sess_b = SessionContext()
        r_gs = ask(q_guseo, settings, session=sess_b)
        print("[guseo] route", r_gs.get("route"), "n=", len(r_gs.get("rows") or []))
        print("       ", str(r_gs.get("answer") or "").replace("\n", " | ")[:200])
        if r_gs.get("route") != "d198_value_bins":
            ok_bind = False
            failed.append(f"구서동 면적별 route={r_gs.get('route')}")
        if "구서동" not in str(r_gs.get("answer") or ""):
            ok_bind = False
            failed.append("구서동 면적별 답에 장소 없음")
        r_bd = ask(q_bind, settings, session=sess_b)
        sql_bd = str(r_bd.get("sql") or "")
        ans_bd = str(r_bd.get("answer") or "")
        print("[bind] route", r_bd.get("route"), "n=", len(r_bd.get("rows") or []))
        print("      ", ans_bd.replace("\n", " | ")[:220])
        if r_bd.get("route") != "d198_value_bins":
            ok_bind = False
            failed.append(f"묶어라 후속 route={r_bd.get('route')}")
        if "분명하지" in ans_bd or "가까운지" in ans_bd:
            ok_bind = False
            failed.append("묶어라가 모호 확인으로 빠짐")
        if "/ 2000" not in sql_bd:
            ok_bind = False
            failed.append("2000 단위 SQL 아님")
        if "AL_D010" in sql_bd:
            ok_bind = False
            failed.append("묶어라 후속이 D010")
        if ok_bind:
            passed += 1
            print("[bind] OK  구서동 면적별 → 2000단위 묶기")
        elif "면적별 아파트 숫자 미인식" not in failed:
            failed.append("2000단위로 묶어라 후속")

        from txt2sql.router_lexicon import map_unknown_to_router

        ok_syn = True
        q_pyeong = "금정구 구서동의 평수별 아파트의 숫자를 구하라"
        syn = map_unknown_to_router(q_pyeong, ["평수별"])
        if "면적별" not in syn.question or syn.unmapped:
            ok_syn = False
            failed.append(f"평수별 매핑 {syn.question!r} unmapped={syn.unmapped}")
        r_py = ask(q_pyeong, settings)
        print("[pyeong] route", r_py.get("route"), "n=", len(r_py.get("rows") or []))
        print("         ", str(r_py.get("answer") or "").replace("\n", " | ")[:200])
        if r_py.get("route") != "d198_value_bins":
            ok_syn = False
            failed.append(f"평수별 route={r_py.get('route')}")
        if "대응하지" in str(r_py.get("answer") or "") or "분명하지" in str(r_py.get("answer") or ""):
            ok_syn = False
            failed.append("평수별이 보완질문으로 남음")
        if ok_syn:
            passed += 1
            print("[pyeong] OK  평수별 → 면적별 구간")
        else:
            failed.append("평수별 라우터 유사어")

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
