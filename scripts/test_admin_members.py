"""법정동 안에 어떤 행정동이 있는지 목록 질의."""

from __future__ import annotations

from txt2sql.intent_router import try_route
from txt2sql.spatial_router import _looks_like_admin_members

Q = "연산동 내에 행정동은 무엇이 있어?"


def main() -> int:
    failed: list[str] = []
    if not _looks_like_admin_members(Q):
        failed.append("연산동 질의가 목록 의도로 안 잡힘")
    if _looks_like_admin_members("구서1동과 인접한 행정동은?"):
        failed.append("인접 질의가 구성 목록으로 새김")
    if _looks_like_admin_members("행정동 구서1동 공동주택은 몇 채야?"):
        failed.append("건수 질의가 구성 목록으로 새김")

    routed = try_route(Q)
    if routed is None or routed.intent != "legal_dong_admin_members":
        failed.append(f"route={None if routed is None else routed.intent}")
    elif "ILIKE '%연산동%'" in (routed.sql or ""):
        failed.append("ILIKE 오탐 SQL")
    elif "^연산[0-9]+동$" not in (routed.sql or "") and "연산1동" not in (routed.sql or ""):
        failed.append(f"번호 행정동 패턴 없음:\n{routed.sql}")

    guseo = try_route("구서동에 속한 행정동 목록")
    if guseo is None or guseo.intent != "legal_dong_admin_members":
        failed.append(f"구서동 목록 route={None if guseo is None else guseo.intent}")

    if failed:
        print("FAIL")
        for item in failed:
            print(" -", item)
        return 1
    print("OK")
    print(routed.intent)
    print(routed.sql)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
