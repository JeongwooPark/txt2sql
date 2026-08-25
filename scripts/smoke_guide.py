from txt2sql.config import load_settings
from txt2sql.pipeline import ask

s = load_settings()
cases = [
    ("기능 알려줘", "guide_help"),
    ("제한이 뭐야?", "guide_limits"),
    ("안녕하세요", "guide_greeting"),
    ("오늘 날씨 어때?", "guide_out_of_scope"),
    ("파이썬 코드 짜줘", "guide_out_of_scope"),
    ("현재 사용가능한 데이터는 몇개야?", "meta_catalog_count"),
    ("구서동 아파트의 특징은?", "building_profile"),
]
for q, expect in cases:
    r = ask(q, s)
    ok = r.get("route") == expect
    print(("PASS" if ok else "FAIL"), q, "->", r.get("route"), f"(expect {expect})")
    if not ok:
        print((r.get("answer") or "")[:200])
