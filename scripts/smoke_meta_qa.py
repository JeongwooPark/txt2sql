from txt2sql.config import load_settings
from txt2sql.pipeline import ask
from txt2sql.meta_qa import is_metadata_question

settings = load_settings()
meta_cases = [
    "어떤 데이터가 있어?",
    "건물 테이블이 뭐야?",
    "A4 컬럼 의미가 뭐야?",
    "법정동명은 어떤 속성이야?",
    "AL_D010의 주요 속성 설명해줘",
]
assert is_metadata_question("어떤 데이터가 있어?")
assert not is_metadata_question("해운대구 건물 몇 채야?")
assert not is_metadata_question("수영구 연면적 상위 5개")

for q in meta_cases:
    print("=" * 60)
    print("Q:", q)
    r = ask(q, settings)
    print("route:", r.get("route"), "ok:", r.get("ok"))
    print(r.get("answer") or "")
    ms = (r.get("steps") or [{}])[-1].get("elapsed_ms")
    print(f"({ms} ms)")
