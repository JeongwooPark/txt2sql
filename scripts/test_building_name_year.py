"""건물명+시공년도 조회가 미지용어/카탈로그로 새지 않는지."""

from __future__ import annotations

from txt2sql.answer import _natural_building_name_lookup
from txt2sql.clarify_qa import _unknown_terms
from txt2sql.domain import (
    extract_building_name_candidate,
    looks_like_building_name_lookup,
)
from txt2sql.intent_router import try_route
from txt2sql.router_lexicon import _looks_like_entity_name, map_unknown_to_router


def main() -> int:
    failed: list[str] = []
    qs = (
        "구서역 포르투나의 시공년도는",
        "구서역포르투나 아파트의 시공년도는",
        "구서역포르투나 아파트 정보",
    )
    for q in qs:
        if not looks_like_building_name_lookup(q):
            failed.append(f"건물명 조회로 안 봄: {q!r}")
        name = extract_building_name_candidate(q) or ""
        if "포르투나" not in name:
            failed.append(f"이름 후보에 포르투나 없음: {q!r} → {name!r}")
        if "시공" in name or "승인" in name:
            failed.append(f"이름 후보에 시공/승인 남음: {name!r}")
        routed = try_route(q)
        if routed is None or routed.intent != "building_name_lookup":
            failed.append(f"라우트: {q!r} → {None if routed is None else routed.intent}")
        elif "포르투나" not in routed.sql:
            failed.append(f"SQL에 포르투나 없음: {routed.sql[:240]}")
        elif '"A13"' not in routed.sql:
            failed.append(f"SQL에 사용승인일 없음: {routed.sql[:240]}")
        elif "아파트의" in routed.sql:
            failed.append(f"SQL이 아파트의 를 건물명으로 씀: {routed.sql[:240]}")

    syn = map_unknown_to_router(
        "구서역 포르투나의 시공년도는",
        ["구서역", "포르투나", "시공년도"],
    )
    mapped_src = {src for src, _dst in syn.mappings}
    if "구서역" in mapped_src or "포르투나" in mapped_src:
        failed.append(f"고유명사를 스키마로 매핑: {syn.mappings}")
    if "시공년도" not in mapped_src:
        failed.append(f"시공년도 미매핑: {syn.mappings}")
    if "포르투나" in syn.unmapped or "구서역" in syn.unmapped:
        failed.append(f"고유명사가 unmapped: {syn.unmapped}")
    if _looks_like_entity_name("시공년도"):
        failed.append("시공년도가 고유명사로 분류됨")
    if not _looks_like_entity_name("구서역") or not _looks_like_entity_name("포르투나"):
        failed.append("구서역/포르투나가 고유명사로 안 잡힘")

    unk = _unknown_terms("구서역 포르투나의 시공년도는", place=None, gu=None)
    if looks_like_building_name_lookup("구서역 포르투나의 시공년도는"):
        pass
    elif "포르투나" in unk:
        failed.append(f"clarify 미지용어에 포르투나: {unk}")

    ans = _natural_building_name_lookup(
        "구서역 포르투나의 시공년도는",
        [{"A24": "구서역 포르투나", "A13": "2022-05-01", "A4": "부산광역시 금정구 구서동"}],
    )
    if "2022년" not in ans or "포르투나" not in ans:
        failed.append(f"사용승인일 답변: {ans}")

    if failed:
        print("FAIL")
        for item in failed:
            print(" -", item)
        return 1
    print("OK")
    for q in qs:
        r = try_route(q)
        print(q, "→", r.intent)
    print("answer:", ans)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
