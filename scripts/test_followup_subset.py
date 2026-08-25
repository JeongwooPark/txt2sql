"""후속 질문이 직전 구·필터를 유지하는지 검증."""

from __future__ import annotations

import re
import sys

from txt2sql.config import load_settings
from txt2sql.db import connect
from txt2sql.followup_qa import try_subset_followup
from txt2sql.intent_router import try_route
from txt2sql.pipeline import _expand_followup_question, ask
from txt2sql.session import SessionContext


def main() -> int:
    settings = load_settings()
    q1 = "금정구 아파트 중에 허가일자가 2020년 이후인 건물은 몇 채야?"
    q2 = "그 중에 가장 최근에 지어진 건물은?"
    failed: list[str] = []

    print("=== 후속 질문 구 유지 테스트 ===\n")
    session = SessionContext()
    with connect(settings.database_url) as conn:
        r1 = try_route(q1, conn=conn)
        if r1 is None or "AL_D198_26410" not in r1.sql or "금정구" not in r1.sql:
            failed.append(f"1차 라우트 실패: {None if r1 is None else r1.sql}")
            print("[1] FAIL  금정구 1차")
        else:
            print("[1] OK   ", r1.intent)
            session.update_from_result(
                q1,
                {
                    "ok": True,
                    "route": r1.intent,
                    "sql": r1.sql,
                    "answer": "3",
                    "rows": [{"cnt": 3}],
                    "tables": ["AL_D198_26410_20250115"],
                },
            )
            print("     place=", session.place, "table=", session.table)

        expanded = _expand_followup_question(q2, session)
        print("[2] expand:", expanded)
        if "금정구" not in expanded:
            failed.append(f"후속 병합에 금정구 없음: {expanded}")

        subset = try_subset_followup(q2, session)
        if subset is None:
            subset = try_subset_followup(expanded, session)
        if subset is None:
            failed.append("subset 라우트 없음")
            print("[3] FAIL  subset")
        else:
            sql = subset.sql
            print("[3] OK   ", subset.intent)
            print(sql)
            if "AL_D198_26410" not in sql:
                failed.append("후속 테이블이 금정이 아님")
            if "동래구" in sql:
                failed.append("후속에 동래구가 들어감")
            if "금정구" not in sql:
                failed.append("후속에 금정구 필터 없음")
            if "A33" not in sql:
                failed.append("허가일자 조건 유실")
            if "아파트" not in sql:
                failed.append("아파트 조건 유실")
            if "ORDER BY" not in sql.upper():
                failed.append("최근 정렬 없음")

    result_session = SessionContext()
    result = ask(q1, settings, session=result_session)
    print("[4] ask1 route", result.get("route"), "ok", result.get("ok"))
    result2 = ask(q2, settings, session=result_session)
    sql2 = str(result2.get("sql") or "")
    print("[5] ask2 route", result2.get("route"))
    print("     sql:", sql2[:300])
    print("     ans:", (result2.get("answer") or "")[:220])
    if "AL_D198_26410" not in sql2:
        failed.append(f"ask 후속 테이블 오류: {sql2[:200]}")
    if "동래구" in sql2:
        failed.append("ask 후속에 동래구")
    if "금정구" not in sql2:
        failed.append("ask 후속에 금정구 없음")

    # 직전 결과가 D010 빈 건설일 1건이어도, 후속은 D198 사용승인일로 재조회
    bad_sql = (
        'SELECT "A4" AS 법정동명, "A24" AS 건물명, MAX("A13") AS 최신건설일\n'
        'FROM "AL_D010_26_20250704"\n'
        "WHERE \"A4\" LIKE '%금정구%' AND \"A9\" = '공동주택'\n"
        'GROUP BY "A4", "A24"\n'
        'ORDER BY MAX("A13") DESC\n'
        "LIMIT 1;"
    )
    q_first = "금정구에서 가장 최근에 지어진 아파트는?"
    q_exc = "건설일이 없는 것은 제외하고 그 중에서 가장 최근에 지어진 아파트를 찾아줘"
    q_full = (
        "금정구에서 건설일이 없는 것은 제외하고 "
        "그 중에서 가장 최근에 지어진 아파트를 찾아줘"
    )
    sess2 = SessionContext()
    sess2.update_from_result(
        q_first,
        {
            "ok": True,
            "route": "llm",
            "sql": bad_sql,
            "answer": "진흥목화아파트 최신건설일=없음",
            "rows": [
                {
                    "법정동명": "부산광역시 금정구 남산동",
                    "건물명": "진흥목화아파트",
                    "최신건설일": None,
                }
            ],
            "tables": ["AL_D010_26_20250704"],
        },
    )
    expanded_exc = _expand_followup_question(q_exc, sess2)
    print("[6] expand 건설일제외:", expanded_exc)
    if "금정구" not in expanded_exc:
        failed.append(f"건설일 후속 병합에 금정구 없음: {expanded_exc}")
    subset_exc = try_subset_followup(q_exc, sess2) or try_subset_followup(
        expanded_exc, sess2
    )
    sql_exc = "" if subset_exc is None else subset_exc.sql
    print("[7] subset 건설일제외", None if subset_exc is None else subset_exc.intent)
    if subset_exc is None:
        failed.append("건설일 제외 후속 라우트 없음")
    else:
        print(sql_exc)
        if "AL_D198_26410" not in sql_exc:
            failed.append("건설일 제외 후속이 D198 금정이 아님")
        if "AL_D010" in sql_exc:
            failed.append("건설일 제외 후속이 D010을 유지")
        if "GROUP BY" in sql_exc.upper():
            failed.append("건설일 제외 후속에 GROUP BY 잔존")
        if '"A34"' not in sql_exc:
            failed.append("건설일 제외 후속에 A34 없음")

    r_full = try_route(q_full)
    sql_full = "" if r_full is None else r_full.sql
    print("[8] 단독 건설일제외", None if r_full is None else r_full.intent)
    if r_full is None or "AL_D198_26410" not in sql_full or '"A34"' not in sql_full:
        failed.append(f"단독 건설일 제외 실패: {sql_full[:240]}")

    ask_sess = SessionContext()
    ask_sess.update_from_result(
        q_first,
        {
            "ok": True,
            "route": "llm",
            "sql": bad_sql,
            "answer": "진흥목화아파트",
            "rows": [{"건물명": "진흥목화아파트", "A24": "진흥목화아파트", "A4": "금정구 남산동"}],
            "tables": ["AL_D010_26_20250704"],
        },
    )
    result3 = ask(q_exc, settings, session=ask_sess)
    sql3 = str(result3.get("sql") or "")
    print("[9] ask 건설일제외 route", result3.get("route"))
    print("     sql:", sql3[:280])
    if "AL_D198_26410" not in sql3:
        failed.append(f"ask 건설일 제외 테이블 오류: {sql3[:200]}")
    if result3.get("route") == "followup_detail":
        failed.append("ask 건설일 제외가 followup_detail로 처리됨")
    if "없음" in str(result3.get("answer") or "") and "A34" not in sql3:
        failed.append("건설일 없는 건물만 다시 반환")

    q_top3 = "최근 3개를 출력해줘"
    rank_sql = (
        'SELECT "A0", "A4", "A13", "A25", "A27", "A34"\n'
        'FROM "AL_D198_26410_20250115"\n'
        "WHERE \"A4\" LIKE '%금정구%' AND \"A27\" ILIKE '%아파트%'\n"
        '  AND "A34" ~ \'^[0-9]{4}-[0-9]{2}-[0-9]{2}$\'\n'
        'ORDER BY "A34" DESC NULLS LAST\n'
        "LIMIT 1;"
    )
    sess3 = SessionContext()
    sess3.update_from_result(
        q_full,
        {
            "ok": True,
            "route": "d198_attr_rank",
            "sql": rank_sql,
            "answer": "휴림 아르페",
            "rows": [{"A13": "휴림 아르페", "A34": "2023-03-22", "A4": "금정구"}],
            "tables": ["AL_D198_26410_20250115"],
        },
    )
    subset3 = try_subset_followup(q_top3, sess3)
    sql_top = "" if subset3 is None else subset3.sql
    print("[10] 최근3개", None if subset3 is None else subset3.intent)
    if subset3 is None:
        failed.append("최근 3개 후속 라우트 없음")
    else:
        print(sql_top)
        if "LIMIT 3" not in sql_top.replace(" ", "").upper().replace("LIMIT3", "LIMIT 3") and "LIMIT 3" not in sql_top:
            if not re.search(r"LIMIT\s+3", sql_top, flags=re.I):
                failed.append(f"LIMIT 3 아님: {sql_top[-80:]}")
        if "AL_D198_26410" not in sql_top:
            failed.append("최근 3개가 금정 D198이 아님")
        if '"A34"' not in sql_top:
            failed.append("최근 3개에 A34 없음")
        if subset3.intent == "clarify_unknown_term":
            failed.append("최근 3개가 clarify로 처리됨")

    ask_top = SessionContext()
    ask_top.update_from_result(
        q_full,
        {
            "ok": True,
            "route": "d198_attr_rank",
            "sql": rank_sql,
            "answer": "휴림 아르페",
            "rows": [{"A13": "휴림 아르페", "A34": "2023-03-22"}],
            "tables": ["AL_D198_26410_20250115"],
        },
    )
    result4 = ask(q_top3, settings, session=ask_top)
    sql4 = str(result4.get("sql") or "")
    print("[11] ask 최근3개 route", result4.get("route"))
    print("     sql:", sql4[-120:])
    print("     ans:", (result4.get("answer") or "")[:220])
    if result4.get("route") in {"clarify_unknown_term", "followup_detail"}:
        failed.append(f"ask 최근 3개가 {result4.get('route')}")
    if not re.search(r"LIMIT\s+3", sql4, flags=re.I):
        failed.append(f"ask 최근 3개 LIMIT 아님: {sql4[-80:]}")
    if "AL_D198_26410" not in sql4:
        failed.append("ask 최근 3개 테이블 오류")
    tables4 = result4.get("tables") or []
    if "AL_D198_26260_20250115" in tables4 and "금정" in q_full:
        failed.append(f"동래 테이블이 같이 표시됨: {tables4}")
    if str(result4.get("answer") or "").startswith("안내:"):
        failed.append("금정구 질의에 안내 머리말")

    # 5건 목록 후 '각각의 사용승인일'은 건수를 3으로 줄이지 않는다
    from txt2sql.followup_qa import is_list_attr_followup
    from txt2sql.intent_router import _extract_top_n

    if _extract_top_n("최근 3개를 출력해줘 중에서 5개는", default=1) != 5:
        failed.append("여러 N이 있으면 마지막 값을 써야 함")

    five_sql = (
        'SELECT "A13", "A34" FROM "AL_D198_26410_20250115"\n'
        "WHERE \"A4\" LIKE '%금정구%' AND \"A27\" ILIKE '%아파트%'\n"
        'ORDER BY "A34" DESC NULLS LAST\n'
        "LIMIT 5;"
    )
    five_rows = [
        {"A13": "휴림 아르페", "A34": "2023-03-22", "A4": "금정구"},
        {"A13": "헤리티지 우석", "A34": "2023-02-13", "A4": "금정구"},
        {"A13": "구서 다움 파크", "A34": "2022-07-06", "A4": "금정구"},
        {"A13": "금정 더 유엘 프리미어", "A34": "2022-06-01", "A4": "금정구"},
        {"A13": "구서역 포르투나", "A34": "2022-05-01", "A4": "금정구"},
    ]
    sess5 = SessionContext()
    sess5.update_from_result(
        "금정구에서 건설일이 없는 것은 제외하고 가장 최근에 지어진 아파트 3개",
        {
            "ok": True,
            "route": "d198_attr_list",
            "sql": five_sql.replace("LIMIT 5", "LIMIT 3"),
            "answer": "3곳",
            "rows": five_rows[:3],
            "tables": ["AL_D198_26410_20250115"],
        },
    )
    sess5.update_from_result(
        "5개는/",
        {
            "ok": True,
            "route": "d198_attr_list",
            "sql": five_sql,
            "answer": "5곳",
            "rows": five_rows,
            "tables": ["AL_D198_26410_20250115"],
        },
    )
    if "3개" in (sess5.last_full_question or ""):
        failed.append(f"5개 후속 후에도 full에 3개: {sess5.last_full_question}")
    if "5개" not in (sess5.last_full_question or ""):
        failed.append(f"5개로 갱신되지 않음: {sess5.last_full_question}")

    q_dates = "각각의 사용승인일도 출력해줘"
    if not is_list_attr_followup(q_dates, sess5):
        failed.append("사용승인일 후속을 목록 속성 추가로 못 봄")
    expanded_dates = _expand_followup_question(q_dates, sess5)
    if expanded_dates != q_dates:
        failed.append(f"사용승인일 후속이 병합됨: {expanded_dates}")
    if try_subset_followup(q_dates, sess5) is not None:
        failed.append("사용승인일 후속이 subset 재조회로 처리됨")

    result5 = ask(q_dates, settings, session=sess5)
    sql5 = str(result5.get("sql") or "")
    ans5 = str(result5.get("answer") or "")
    rows5 = result5.get("rows") or []
    print("[12] 사용승인일 후속 route", result5.get("route"), "n=", len(rows5))
    print("     ans:", ans5[:280])
    if len(rows5) != 5:
        failed.append(f"5건이 아니라 {len(rows5)}건으로 줄었음")
    if re.search(r"LIMIT\s+3", sql5, flags=re.I):
        failed.append(f"후속이 LIMIT 3으로 재조회됨: {sql5[-80:]}")
    for name in ("휴림 아르페", "금정 더 유엘 프리미어", "구서역 포르투나"):
        if name not in ans5:
            failed.append(f"후속 답에 {name} 없음")
    if "2023년 3월 22일" not in ans5:
        failed.append("후속 답에 사용승인일 없음")
    if "3개" in ans5:
        failed.append(f"후속 답이 3개로 말함: {ans5[:160]}")

    if failed:
        print("\n실패:")
        for item in failed:
            print(" -", item)
        print(f"=== FAIL {len(failed)} ===")
        return 1
    print("\n=== 결과: OK ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
