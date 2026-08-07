"""엔진 재사용·후속 질문 스모크."""

from llm2sql import Llm2SqlEngine, SessionContext

with Llm2SqlEngine.from_env() as engine:
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
    assert r3.ok and r3.route == "followup_attr", r3
    assert "건물명" in r3.answer
    print("PASS followup", r3.answer.replace("\n", " / "))

print("engine smoke OK")
