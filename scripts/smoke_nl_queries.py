"""자연어 질의 스모크 테스트 (대표 시나리오)."""

from __future__ import annotations

from llm2sql import Llm2SqlEngine, SessionContext

CASES = [
    ("기능 알려줘", None),
    ("현재 사용가능한 데이터는 몇개야?", None),
    ("A4 컬럼 의미가 뭐야?", None),
    ("송정동 건물 몇 채야?", None),
    ("구서동에서 제일 좋은 아파트는?", None),
    ("구서동 아파트의 특징은?", None),
    ("구서동에서 건물면적이 가장 큰 아파트는?", "rank"),
    ("그 아파트의 이름은?", "rank"),
    ("지번은?", "rank"),
    ("해운대구 건물 몇 채야?", None),
    ("오늘 날씨 어때?", None),
]


def main() -> None:
    sessions: dict[str, SessionContext] = {}
    passed = 0
    with Llm2SqlEngine.from_env() as engine:
        print("=== 자연어 질의 테스트 ===\n")
        for i, (q, sid) in enumerate(CASES, 1):
            session = sessions.setdefault(sid, SessionContext()) if sid else None
            r = engine.ask(q, session=session)
            ok = r.ok and bool(r.answer)
            if ok:
                passed += 1
            status = "OK" if ok else "FAIL"
            ans = (r.answer or "").replace("\n", " / ")
            if len(ans) > 180:
                ans = ans[:177] + "..."
            print(f"[{i:02d}] {status}  route={r.route}")
            print(f"  Q: {q}")
            print(f"  A: {ans}")
            if r.error:
                print(f"  err: {r.error}")
            print()
    print(f"=== 결과: {passed}/{len(CASES)} OK ===")


if __name__ == "__main__":
    main()
