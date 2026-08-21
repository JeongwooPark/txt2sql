"""번호 행정동 프로필은 법정동 A4가 아니라 경계 교차로 집계한다."""

from __future__ import annotations

from llm2sql.profile_qa import _profile_from_where, _use_admin_boundary


def main() -> int:
    failed: list[str] = []

    if not _use_admin_boundary("구서1동") or not _use_admin_boundary("구서2동"):
        failed.append("구서1·2동이 행정동으로 안 잡힘")
    if _use_admin_boundary("구서동"):
        failed.append("구서동이 행정동으로 오탐")

    p1, from1, where1, admin1 = _profile_from_where(
        place="구서1동", usage="공동주택"
    )
    if not admin1:
        failed.append("구서1동 admin flag 없음")
    if "ST_Intersects" not in from1 or "BND_ADM_DONG_PG" not in from1:
        failed.append(f"구서1동 FROM 경계 교차 없음:\n{from1}")
    if "A4" in where1:
        failed.append(f"구서1동이 A4 필터를 씀:\n{where1}")
    if "구서1동" not in where1 or 'b."A9" = \'공동주택\'' not in where1:
        failed.append(f"구서1동 WHERE:\n{where1}")
    if p1 != "b.":
        failed.append(f"구서1동 prefix={p1}")

    _p0, from0, where0, admin0 = _profile_from_where(
        place="구서동", usage="공동주택"
    )
    if admin0:
        failed.append("구서동이 경계 조인을 씀")
    if "BND_ADM_DONG_PG" in from0 or "ST_Intersects" in from0:
        failed.append(f"구서동 FROM가 행정동 조인:\n{from0}")
    if "구서동" not in where0 or '"A9" = \'공동주택\'' not in where0:
        failed.append(f"구서동 WHERE:\n{where0}")

    if failed:
        print("FAIL")
        for item in failed:
            print(" -", item)
        return 1
    print("OK")
    print("구서1동 WHERE", where1)
    print("구서동 WHERE", where0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
