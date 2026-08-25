"""엔진 재사용·후속 질문 스모크."""

from txt2sql import Txt2SqlEngine, SessionContext

with Txt2SqlEngine.from_env() as engine:
    session = SessionContext()
    r1 = engine.ask("기능 알려줘")
    assert r1.ok and r1.route == "guide_help", r1
    print("PASS guide", r1.route)

    r2 = engine.ask(
        "구서동에서 건물면적이 가장 큰 아파트는?", session=session
    )
    assert r2.ok and r2.route == "building_rank_건물면적", (r2.route, r2.answer)
    print("PASS rank", r2.route, "name=", (session.focus_row or {}).get("A24"))

    r3 = engine.ask("그 아파트의 이름은?", session=session)
    assert r3.ok, r3
    assert "협성" in (r3.answer or "") or "건물명" in (r3.answer or ""), r3.answer
    print("PASS followup", r3.route, r3.answer.replace("\n", " / "))

    year_sess = SessionContext()
    ry = engine.ask("금정구 각년도별 아파트 건립 수는?", session=year_sess)
    assert ry.ok and ry.route == "d198_year_stats", (ry.route, ry.answer)
    print("PASS year", ry.route, "rows=", ry.row_count)
    r5 = engine.ask("5년 단위로 출력하라", session=year_sess)
    assert r5.ok and r5.route == "d198_year_stats", (r5.route, r5.answer)
    assert "금정구" in (r5.answer or "")
    print("PASS year-bin", r5.route)
    ra = engine.ask("금정구 아파트 연면적 크기별 수는?")
    assert ra.ok and ra.route == "d198_value_bins", (ra.route, ra.answer)
    assert "㎡" in (ra.answer or "")
    print("PASS area-bin", ra.route, "rows=", ra.row_count)

    r_thr = engine.ask("금정구에서 연면적 2000 이상인 건물 수는?")
    assert r_thr.ok, r_thr
    assert r_thr.route not in {"d198_value_bins", "d198_year_stats"}, r_thr.route
    print("PASS area-threshold", r_thr.route)

print("engine smoke OK")
