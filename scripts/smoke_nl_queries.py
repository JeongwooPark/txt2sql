"""자연어 질의 스모크 테스트 (대표 시나리오).

기존 가이드·순위·임계값 질의에 더해, 연도 단위 후속·면적 구간 집계를 포함한다.
"""

from __future__ import annotations

import re
import sys

from llm2sql import Llm2SqlEngine, SessionContext

# (질문, 세션키|None, 기대 route 접두/정확값|None)
# 세션키 rank/year/area 는 같은 대화로 이어진다.
CASES: list[tuple[str, str | None] | tuple[str, str | None, str | None]] = [
    ("기능 알려줘", None),
    ("현재 사용가능한 데이터는 몇개야?", None),
    ("A4 컬럼 의미가 뭐야?", None),
    ("송정동 건물 몇 채야?", None),
    ("구서동에서 제일 좋은 아파트는?", None),
    ("구서동 아파트의 특징은?", None),
    ("구서동에서 건물면적이 가장 큰 아파트는?", "rank", "building_rank_"),
    ("그 아파트의 이름은?", "rank", ("followup_", "d010_attr_rank", "building_rank_")),
    ("지번은?", "rank", ("followup_", "d010_attr_")),
    ("해운대구 건물 몇 채야?", None),
    ("오늘 날씨 어때?", None, "guide_"),
    ("해운대구에서 건물 높이가 50미터 이상인 건물은 몇 개야?", None),
    ("해운대구에서 건물 높이가 50미터 이하인 건물은 몇 개야?", None),
    ("해운대구에서 건물 높이가 50미터 미만인 건물은 몇 개야?", None),
    ("해운대구에서 건물 높이가 50미터 초과인 건물은 몇 개야?", None),
    ("금정구에서 지상층이 10층 이상인 건물은 몇 개야?", None),
    ("금정구에서 지상층이 10층 이하인 건물은 몇 개야?", None),
    ("금정구에서 지상층이 10층 미만인 건물은 몇 개야?", None),
    ("금정구에서 지상층이 10층 초과인 건물은 몇 개야?", None),
    ("금정구에서 연면적 2000 이상인 건물 수는?", None),
    ("금정구에서 연면적 2000 이하인 건물 수는?", None),
    ("금정구에서 연면적 2000 미만인 건물 수는?", None),
    ("금정구에서 연면적 2000 초과인 건물 수는?", None),
    ("구서동 건축물 중에 면적이 10000이상인것은?", None),
    ("구서동 건축물 중에 면적이 10000이하인 것", None),
    ("구서동 건축물 중에 면적이 10000미만인 것", None),
    ("구서동 건축물 중에 면적이 10000초과인 것", None),
    ("해운대구에서 건물 높이가 50미터 이하인 것", None),
    ("금정구에서 지상층이 10층 미만인 것", None),
    ("장전동의 콘크리트 구조물은?", None),
    ("장전동의 산지에 있는 건물은?", None),
    ("용도별건물에서 동래구 건폐율이 50 이상인 건물은 몇 채야?", None),
    ("동래구 집합건축물은 몇 채야?", None),
    ("금정구 각년도별 아파트 건립 수는?", "year", "d198_year_stats"),
    ("5년 단위로 출력하라", "year", "d198_year_stats"),
    ("10년 단위로 출력하라", "year", "d198_year_stats"),
    ("삼년 단위로 출력하라", "year", "d198_year_stats"),
    ("이십년 단위로 출력하라", "year", "d198_year_stats"),
    ("5년씩 출력하라", "year", "d198_year_stats"),
    ("면적 크기 단위별로 출력하라", "year", "d198_value_bins"),
    ("금정구 아파트 연면적 크기별 수는?", "area", "d198_value_bins"),
    ("100㎡ 단위로 출력하라", "area", "d198_value_bins"),
    ("금정구 아파트 높이 5m 단위별 수는?", None, "d198_value_bins"),
    ("구서동의 면적별 아파트의 숫자를 구하라", "guseo_area", "d198_value_bins"),
    ("2000단위로 묶어라", "guseo_area", "d198_value_bins"),
]


def _norm(
    case: tuple,
) -> tuple[str, str | None, str | tuple[str, ...] | None]:
    q = case[0]
    sid = case[1] if len(case) > 1 else None
    expect = case[2] if len(case) > 2 else None
    return q, sid, expect


def _route_matches(route: str | None, expect: str | tuple[str, ...] | None) -> bool:
    if not expect:
        return True
    got = str(route or "")
    options = expect if isinstance(expect, tuple) else (expect,)
    return any(got == e or got.startswith(e) for e in options)


def _forbidden_routes(question: str) -> tuple[str, ...]:
    """임계값·산지 등이 구간 집계/건물명으로 새면 안 된다."""
    q = question.strip()
    banned: list[str] = []
    if re.search(r"(이상|이하|초과|미만|넘는)", q) and "단위" not in q:
        banned.extend(["d198_value_bins", "d198_year_stats", "building_name_lookup"])
    if "산지" in q:
        banned.extend(["d198_value_bins", "d198_year_stats"])
    if re.search(r"(이름|지번)\s*\??$", q):
        banned.extend(["d198_value_bins", "d198_year_stats"])
    return tuple(banned)


def main() -> int:
    sessions: dict[str, SessionContext] = {}
    passed = 0
    failed: list[str] = []
    with Llm2SqlEngine.from_env() as engine:
        print("=== 자연어 질의 스모크 ===\n")
        for i, raw in enumerate(CASES, 1):
            q, sid, expect = _norm(raw)
            session = sessions.setdefault(sid, SessionContext()) if sid else None
            r = engine.ask(q, session=session)
            route = r.route
            ans = r.answer or ""
            reasons: list[str] = []
            if not r.ok or not ans.strip():
                reasons.append("응답 실패")
            if not _route_matches(route, expect):
                reasons.append(f"route={route} (expect {expect})")
            banned = _forbidden_routes(q)
            if route in banned:
                reasons.append(f"금지 route={route}")
            sql = str(getattr(r, "sql", None) or "")
            if sid in {"year", "area"} and ("AL_D010" in sql or "서울" in sql):
                reasons.append("D010/서울로 이탈")
            if (
                sid == "year"
                and expect == "d198_year_stats"
                and "단위" in q
                and "금정구" not in ans
            ):
                reasons.append("후속에 금정구 범위 없음")
            if expect == "d198_value_bins" and "동" not in ans:
                reasons.append("구간 집계 답 형식 이상")
            if expect == "d198_value_bins" and "분명하지" in ans:
                reasons.append("모호 확인으로 빠짐")
            if q == "2000단위로 묶어라" and "/ 2000" not in str(
                getattr(r, "sql", "") or ""
            ):
                reasons.append("2000 단위 SQL 아님")
            if q == "5년씩 출력하라" and (getattr(r, "row_count", 0) or 0) < 6:
                reasons.append(f"5년 구간이 너무 굵음 n={r.row_count}")
            ok = not reasons
            if ok:
                passed += 1
            else:
                failed.append(f"{i:02d} {q}: {'; '.join(reasons)}")
            status = "OK" if ok else "FAIL"
            shown = ans.replace("\n", " / ")
            if len(shown) > 180:
                shown = shown[:177] + "..."
            print(f"[{i:02d}] {status}  route={route}")
            print(f"  Q: {q}")
            print(f"  A: {shown}")
            if reasons:
                print(f"  why: {'; '.join(reasons)}")
            if r.error:
                print(f"  err: {r.error}")
            print()
    total = len(CASES)
    print(f"=== 결과: {passed}/{total} OK ===")
    if failed:
        print("실패:")
        for item in failed:
            print(" -", item)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
