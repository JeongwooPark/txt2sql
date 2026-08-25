"""NL100 엔진 실패·오라우트 회귀: 안내, 건수, 오래된 연수 확인, SQL 가드."""

from __future__ import annotations

from txt2sql.clarify_qa import check_ambiguity
from txt2sql.domain import is_vague_age_threshold, looks_like_building_name_lookup
from txt2sql.guide_qa import try_guide
from txt2sql.intent_router import _wants_count, fix_common_sql_mistakes, try_route
from txt2sql.sql_validator import diagnose_sql


def main() -> int:
    failed: list[str] = []

    g1 = try_guide("너는 무슨 일을 해?")
    if g1 is None or g1.intent != "guide_help":
        failed.append(f"N001 안내 미탐: {g1}")

    g3 = try_guide("어떤 질문을 하면 돼?")
    if g3 is None or g3.intent != "guide_help":
        failed.append(f"N003 안내 미탐: {g3}")

    q18 = "문현동에는 건물이 얼마나 있어?"
    if looks_like_building_name_lookup(q18):
        failed.append("N018이 건물명 조회로 남음")
    if not _wants_count(q18):
        failed.append("N018 건수 힌트 미탐")
    routed18 = try_route(q18)
    if routed18 is None or routed18.intent not in {
        "building_place_count",
        "building_in_dong_spatial",
    }:
        failed.append(f"N018 라우트: {routed18}")

    q78 = "다대동 예쁜 건물"
    if looks_like_building_name_lookup(q78):
        failed.append("N078이 건물명 조회로 남음")

    q99 = "남산동에서 오래된 단독주택은 몇 채야?"
    if not is_vague_age_threshold(q99):
        failed.append("N099 주관 연수 미탐")
    if looks_like_building_name_lookup(q99):
        failed.append("N099이 건물명 조회로 남음")
    if is_vague_age_threshold("금정구에서 가장 오래된 단독주택은?"):
        failed.append("가장 오래된 순위 질의가 주관 연수로 오탐")

    bad_sql = (
        'SELECT COUNT(*) AS cnt\n'
        'FROM "AL_D010_26_20250704"\n'
        "WHERE \"A4\" LIKE '%남산동%'\n"
        "  AND \"A9\" = '단독주택'\n"
        "  AND \"A13\" < CURRENT_DATE;"
    )
    diag = diagnose_sql(q99, bad_sql) or ""
    if "text < date" not in diag and "A34" not in diag:
        failed.append(f"진단 미탐: {diag!r}")
    fixed = fix_common_sql_mistakes(bad_sql, q99)
    if '::date' not in fixed and "A34" not in fixed:
        failed.append(f"교정 미적용: {fixed}")

    # check_ambiguity는 연수 확인을 place 조회보다 먼저 한다 (conn 불필요 경로)
    class _Dummy:
        pass

    clar = check_ambiguity(_Dummy(), q99)  # type: ignore[arg-type]
    if clar is None or clar.intent != "clarify_vague":
        failed.append(f"N099 clarify: {clar}")
    elif "30년" not in clar.answer:
        failed.append("N099 안내 예에 30년 없음")

    if failed:
        print("FAIL")
        for item in failed:
            print(" -", item)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
