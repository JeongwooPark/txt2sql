"""라우터 미지용어 → 닫힌 어휘 매핑·보완질문."""

from __future__ import annotations

import sys

from llm2sql.clarify_qa import unknown_term_guidance, _unknown_terms
from llm2sql.router_lexicon import (
    all_router_terms,
    apply_router_mappings,
    map_unknown_to_router,
)


class _BoomClient:
    def chat(self, **_kwargs):
        raise AssertionError("결정적 매핑은 LLM을 호출하면 안 됩니다")


def main() -> int:
    failed: list[str] = []
    passed = 0

    terms = set(all_router_terms())
    for need in ("연면적", "면적별", "사용승인일", "아파트", "지상층"):
        if need not in terms:
            failed.append(f"라우터 어휘에 {need} 없음")
        else:
            passed += 1

    syn = map_unknown_to_router(
        "금정구 구서동의 평수별 아파트의 숫자를 구하라",
        ["평수별"],
        client=_BoomClient(),
    )
    if syn.mappings != (("평수별", "면적별"),) or "면적별" not in syn.question:
        failed.append(f"평수별 매핑 실패: {syn}")
    elif syn.unmapped:
        failed.append(f"평수별이 unmapped: {syn.unmapped}")
    else:
        passed += 1
        print("[map] OK  평수별 → 면적별")

    unknown_sale = _unknown_terms("금정구 아파트 매매가 상위", place=None, gu="금정구")
    if "매매가" not in unknown_sale:
        failed.append(f"매매가 미지용어 미검출: {unknown_sale}")
    else:
        passed += 1
        print("[detect] OK  매매가 미지용어")

    syn2 = map_unknown_to_router(
        "구서동 아파트 매매가 상위",
        ["매매가"],
        client=_BoomClient(),
    )
    if syn2.mappings or "매매가" not in syn2.unmapped:
        failed.append(f"매매가는 unmapped여야 함: {syn2}")
    else:
        passed += 1
        print("[unmap] OK  매매가 미대응")

    guide = unknown_term_guidance(["매매가"])
    if "대응하지" not in guide or "연면적" not in guide:
        failed.append("보완질문 문구 부족")
    else:
        passed += 1
        print("[guide] OK  보완질문")

    syn3 = map_unknown_to_router(
        "금정구 사용승인연도별 아파트 수",
        ["사용승인연도별"],
        client=_BoomClient(),
    )
    if "연도별" not in syn3.question or syn3.unmapped:
        failed.append(f"사용승인연도별 매핑 실패: {syn3}")
    else:
        passed += 1
        print("[year] OK  사용승인연도별 → 연도별")

    rewritten = apply_router_mappings("규모별로 보여줘", [("규모별", "크기별")])
    if rewritten != "크기별로 보여줘":
        failed.append(f"치환 실패: {rewritten}")
    else:
        passed += 1
        print("[apply] OK  규모별 → 크기별")

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
