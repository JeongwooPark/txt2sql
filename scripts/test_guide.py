"""기능·도움말 질문이 SQL 조회로 오인되지 않는지 검증."""

from __future__ import annotations

from txt2sql.guide_qa import try_guide
from txt2sql.intent_classifier import predict_intent_rules


def main() -> int:
    failed: list[str] = []

    help_qs = (
        "할 수 있는 것을 말해",
        "할수있는것을말해",
        "할 수 잇는 것은",
        "할수잇는것은",
        "할 수 있는 것은",
        "뭘 할 수 있어?",
        "무엇을 할 수 있어",
        "기능 알려줘",
        "가능한 게 뭐야",
        "뭐가 가능해",
        "너는 무슨 일을 해?",
        "어떤 질문을 하면 돼?",
    )
    for q in help_qs:
        guide = try_guide(q)
        if guide is None or guide.intent != "guide_help":
            failed.append(f"도움말 미탐: {q!r} → {guide}")
            continue
        if "가능한 기능" not in guide.answer:
            failed.append(f"기능 안내 본문 없음: {q!r}")
        rules = predict_intent_rules(q)
        if rules.intent != "guide":
            failed.append(f"규칙 의도: {q!r} → {rules.intent}")

    # 도메인 질의는 도움말로 가로채지 않는다.
    data_q = "구서동에서 조회할 수 있는 아파트는?"
    if try_guide(data_q) is not None:
        failed.append(f"도메인 질의가 안내로 감: {data_q!r}")

    catalog_q = "사용가능한 데이터는 몇개야?"
    guide_cat = try_guide(catalog_q)
    if guide_cat is not None:
        failed.append(f"카탈로그 질의가 안내로 감: {guide_cat}")

    if failed:
        print("FAIL")
        for item in failed:
            print(" -", item)
        return 1
    print("OK")
    for q in help_qs:
        print(q, "→", try_guide(q).intent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
