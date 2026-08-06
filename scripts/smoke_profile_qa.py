from llm2sql.config import load_settings
from llm2sql.pipeline import ask
from llm2sql.meta_qa import is_metadata_question
from llm2sql.profile_qa import is_profile_question

s = load_settings()
cases = [
    "현재 사용가능한 데이터는 몇개야?",
    "구서동 아파트의 특징은?",
    "해운대구 단독주택 특성 요약해줘",
]
for q in cases:
    print("=" * 60)
    print("Q:", q)
    print("meta", is_metadata_question(q), "profile", is_profile_question(q))
    r = ask(q, s)
    print("route:", r.get("route"), "ok:", r.get("ok"))
    print(r.get("answer"))
    print("ms:", (r.get("steps") or [{}])[-1].get("elapsed_ms"))
