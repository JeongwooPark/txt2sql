"""법정동·행정동·구군 지명 사전이 구분되는지 (전국)."""

from __future__ import annotations

from llm2sql.domain import extract_gu, extract_place, extract_places
from llm2sql.gazetteer import (
    KIND_ADMIN,
    KIND_LEGAL,
    KIND_SIDO,
    KIND_SIGUNGU,
    classify_place,
    uses_admin_boundary,
)
from llm2sql.profile_qa import _use_admin_boundary


def main() -> int:
    failed: list[str] = []

    if KIND_LEGAL not in classify_place("구서동"):
        failed.append("구서동이 법정동이 아님")
    if KIND_ADMIN not in classify_place("구서1동") or KIND_LEGAL in classify_place(
        "구서1동"
    ):
        failed.append("구서1동이 행정동 전용이 아님")
    if KIND_SIGUNGU not in classify_place("금정구"):
        failed.append("금정구가 구군이 아님")
    if classify_place("구서역"):
        failed.append("구서역이 지명 사전에 들어 있음")
    if classify_place("공동"):
        failed.append("공동이 동으로 잡힘")

    if extract_places("구서역 포르투나의 시공년도는"):
        failed.append(f"구서역 질문이 장소로 잡힘: {extract_places('구서역 포르투나의 시공년도는')}")
    if extract_place("공동주택 몇 채야") == "공동":
        failed.append("공동주택에서 공동동 오탐")
    if extract_places("할 수 있는 것을 말해"):
        failed.append("도움말 질문이 장소로 잡힘")

    places = extract_places("구서1동 구서2동 구서동 아파트 특징 비교")
    if places != ["구서1동", "구서2동", "구서동"]:
        failed.append(f"3개 동 추출: {places}")
    if not _use_admin_boundary("구서1동") or _use_admin_boundary("구서동"):
        failed.append("행정/법정 경계 판별 실패")
    if uses_admin_boundary("감전동"):
        failed.append("감전동(법정+행정)이 행정전용으로 잡힘")

    if extract_gu("금정구 구서동 건물") != "금정구":
        failed.append(f"구 추출 실패: {extract_gu('금정구 구서동 건물')}")
    if extract_gu("서울특별시 강남구 건물") != "강남구":
        failed.append(
            f"전국 구 미추출: {extract_gu('서울특별시 강남구 건물')}"
        )
    if extract_place("서울특별시 강남구 건물") != "강남구":
        failed.append(
            f"전국 구 동우선 실패: {extract_place('서울특별시 강남구 건물')}"
        )
    if KIND_SIGUNGU not in classify_place("수원시"):
        failed.append("수원시가 구군이 아님")
    if KIND_SIDO not in classify_place("서울특별시"):
        failed.append("서울특별시가 시도가 아님")

    if "1가" not in (extract_place("중구 광복동1가") or ""):
        failed.append(f"광복동1가 최장일치 실패: {extract_place('중구 광복동1가')}")

    if extract_places("원리원칙이 뭐야?"):
        failed.append(f"원리원칙 오탐: {extract_places('원리원칙이 뭐야?')}")
    if extract_places("고리원자력발전소는 어디에 있어?"):
        failed.append(
            f"고리원자력 오탐: {extract_places('고리원자력발전소는 어디에 있어?')}"
        )
    if extract_place("월내리 건물은 몇 채야?") != "월내리":
        failed.append(f"월내리 미추출: {extract_place('월내리 건물은 몇 채야?')}")
    if extract_place("기장읍 건물 몇 채야?") != "기장읍":
        failed.append(f"기장읍 미추출: {extract_place('기장읍 건물 몇 채야?')}")

    from llm2sql.gazetteer import find_places, load_gazetteer

    # 트라이 최장일치가 선형 스캔과 같은 지명을 내는지
    samples = (
        "연산동 공동주택은 몇 채야?",
        "장전1동이랑 장전2동 아파트 비교해줘",
        "중구 광복동1가 건물 수는?",
        "원리원칙을 설명해 줘",
        "금정구 구서동 건물",
        "일광읍 아파트는 몇 채야?",
    )
    gaz = load_gazetteer()
    for sample in samples:
        linear: list[str] = []
        i = 0
        while i < len(sample):
            best = None
            for name in gaz.names_by_len:
                if sample.startswith(name, i):
                    from llm2sql.gazetteer import _short_ri_ok

                    if _short_ri_ok(sample, i, i + len(name), name):
                        best = name
                        break
            if best is None:
                i += 1
                continue
            linear.append(best)
            i += len(best)
        trie = [h.name for h in find_places(sample)]
        if trie != linear:
            failed.append(f"트라이≠선형 '{sample}': {trie} vs {linear}")

    if failed:
        print("FAIL")
        for item in failed:
            print(" -", item)
        return 1
    print("OK")
    print("구서동", classify_place("구서동"))
    print("구서1동", classify_place("구서1동"))
    print("compare", places)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
