from llm2sql.config import load_settings
from llm2sql.pipeline import ask
from llm2sql.session import SessionContext

s = load_settings()
session = SessionContext()

steps = [
    "구서동에서 제일 좋은 아파트는?",
    "구서동에서 건물면적이 가장 큰 아파트는?",
    "그 아파트의 이름은?",
    "지번은?",
    "높이는?",
]
for q in steps:
    print("=" * 60)
    print("Q:", q)
    r = ask(q, s, session=session)
    print("route:", r.get("route"))
    print(r.get("answer"))
    print("focus A0:", (session.focus_row or {}).get("A0"))
    print("ms:", (r.get("steps") or [{}])[-1].get("elapsed_ms"))
