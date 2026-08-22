"""복합 자연어 질의 30문항 스모크.

용도+수치+구조+공간+순위가 한 질문에 겹치는 경우를 대상으로 한다.
SEMANTIC_PLAN_MODE=hybrid 로 라우터 미적중 시 SQP를 탄다.
지도 발행은 끄고 채팅 경로만 본다.
"""

from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from llm2sql import Llm2SqlEngine, SessionContext
from llm2sql.config import load_settings

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).with_name("_out_compound30.json")
TIMEOUT_S = 90


@dataclass(frozen=True)
class Case:
    id: str
    cat: str
    q: str
    session: str | None = None
    sql_all: tuple[str, ...] = ()
    sql_none: tuple[str, ...] = ()
    forbid_routes: tuple[str, ...] = ()
    want_list: bool = False
    allow_clarify: bool = False


CASES: list[Case] = [
    Case(
        "C01",
        "필터복합",
        "해운대구 아파트 중 높이 70m 이상이고 연면적 10000㎡ 이상인 건물 이름과 높이",
        sql_all=("AL_D010", "A16", "A14", "A9"),
        want_list=True,
    ),
    Case(
        "C02",
        "필터복합",
        "금정구에서 연면적 5000㎡ 이상이고 15층 이상인 철근콘크리트 건물",
        sql_all=("AL_D010", "A14", "A26"),
        want_list=True,
    ),
    Case(
        "C03",
        "순위복합",
        "동래구 철근콘크리트 공동주택 중 높이가 높은 10개",
        sql_all=("AL_D010", "ORDER BY", "LIMIT 10", "A16"),
        forbid_routes=("building_structure_list",),
        want_list=True,
    ),
    Case(
        "C04",
        "건수복합",
        "해운대구 공동주택 중 건축면적이 1000㎡ 이상인 건물 수",
        sql_all=("AL_D010", "COUNT", "A12"),
    ),
    Case(
        "C05",
        "공간경계",
        "연산동 안에 있는 공동주택 중 연면적 상위 10개",
        sql_all=("AL_D010", "BND_ADM", "ST_Intersects"),
    ),
    Case(
        "C06",
        "공간거리",
        "구서동 주변 500m 이내에 있는 공동주택 중 높이 40m 이상",
        sql_all=("AL_D010", "ST_DWithin"),
    ),
    Case(
        "C07",
        "필터복합",
        "수영구 아파트 중 지상 20층 이상이고 높이 60m 이상인 건물",
        sql_all=("AL_D010", "A26", "A16"),
        want_list=True,
    ),
    Case(
        "C08",
        "건수복합",
        "사하구 창고시설 중 연면적 3000㎡ 이상인 건물은 몇 채야?",
        sql_all=("AL_D010", "COUNT", "A14"),
    ),
    Case(
        "C09",
        "순위복합",
        "부산진구 업무시설 중 높이가 높은 순 15개",
        sql_all=("AL_D010", "ORDER BY", "LIMIT 15"),
    ),
    Case(
        "C10",
        "필터복합",
        "연제구 학교 중 대지면적 2000㎡ 이상인 건물 이름과 대지면적",
        sql_all=("AL_D010", "A15"),
        want_list=True,
    ),
    Case(
        "C11",
        "필터복합",
        "해운대구 아파트 중 높이 80m 이상이고 연면적 8000㎡ 이상인 건물",
        sql_all=("AL_D010", "A16", "A14"),
        want_list=True,
    ),
    Case(
        "C12",
        "필터복합",
        "금정구 철근콘크리트 구조 건물 중 15층 이상인 것",
        sql_all=("AL_D010", "A11", "A26"),
        forbid_routes=("building_structure_list",),
    ),
    Case(
        "C13",
        "집계",
        "해운대구 공동주택 평균 높이",
        sql_all=("AL_D010", "AVG", "A16"),
    ),
    Case(
        "C14",
        "분포",
        "해운대구 건물 용도별 개수",
        sql_all=("AL_D010", "A9"),
    ),
    Case(
        "C15",
        "건수복합",
        "기장군 단독주택 중 건축면적 200㎡ 이상인 건물 수",
        sql_all=("AL_D010", "COUNT", "A12"),
    ),
    Case(
        "C16",
        "필터복합",
        "강서구 공장 중 연면적 5000㎡ 이상인 건물 이름과 연면적",
        sql_all=("AL_D010", "A14"),
        want_list=True,
    ),
    Case(
        "C17",
        "공간경계",
        "연산동 안에 있는 건물 중 높이 50m 이상",
        sql_all=("BND_ADM", "ST_Intersects", "A16"),
    ),
    Case(
        "C18",
        "공간거리",
        "구서동 주변 300m 이내 아파트는 몇 채야?",
        sql_all=("ST_DWithin", "COUNT"),
    ),
    Case(
        "C19",
        "필터복합",
        "남구 공동주택 중 연면적 3000㎡ 이상이고 지상 10층 이상인 건물",
        sql_all=("AL_D010", "A14", "A26"),
        want_list=True,
    ),
    Case(
        "C20",
        "순위복합",
        "해운대구 철근콘크리트 아파트 중 연면적이 큰 8개",
        sql_all=("AL_D010", "A14", "LIMIT 8"),
    ),
    Case(
        "C21",
        "필터복합",
        "동래구 교육연구시설 중 높이 20m 이상인 건물 수",
        sql_all=("AL_D010", "COUNT", "A16"),
    ),
    Case(
        "C22",
        "공간경계",
        "연산동 안에 있는 공동주택 중 높이 40m 이상이고 연면적 2000㎡ 이상",
        sql_all=("ST_Intersects", "A16", "A14"),
    ),
    Case(
        "C23",
        "후속",
        "해운대구 아파트 중 연면적이 큰 20개 보여줘",
        session="s1",
        sql_all=("AL_D010", "A14"),
    ),
    Case(
        "C24",
        "후속",
        "그중 높이 80m 이상만",
        session="s1",
        forbid_routes=("chart_help",),
    ),
    Case(
        "C25",
        "후속",
        "금정구 공동주택 중 높이가 높은 15개",
        session="s2",
        sql_all=("AL_D010", "A16"),
    ),
    Case(
        "C26",
        "후속",
        "10개만 보여줘",
        session="s2",
        forbid_routes=("d198_attr_list",),
    ),
    Case(
        "C27",
        "후속",
        "사하구에서 연면적 2000㎡ 이상인 창고",
        session="s3",
        sql_all=("AL_D010", "A14"),
    ),
    Case(
        "C28",
        "후속",
        "건물명과 지번도 같이",
        session="s3",
        sql_all=("AL_D010", "A14", "창고시설"),
        want_list=True,
    ),
    Case(
        "C29",
        "모호",
        "해운대구에서 면적이 가장 큰 건물 5개",
        allow_clarify=True,
    ),
    Case(
        "C30",
        "미지원공간",
        "구서역 주변 500m 이내에 있는 공동주택",
        allow_clarify=True,
    ),
]


def _clip(text: str, n: int = 200) -> str:
    t = (text or "").replace("\n", " / ")
    return t if len(t) <= n else t[: n - 3] + "..."


def _ask(engine: Llm2SqlEngine, q: str, session: SessionContext | None):
    return engine.ask(q, session=session, include_map=False)


def _sql_ok(sql: str, case: Case) -> list[str]:
    reasons: list[str] = []
    if not sql:
        if case.sql_all and not case.allow_clarify:
            reasons.append("SQL 없음")
        return reasons
    upper = sql.upper()
    if not (upper.lstrip().startswith("SELECT") or upper.lstrip().startswith("WITH")):
        reasons.append("SELECT/WITH 아님")
    for word in ("INSERT", "UPDATE", "DELETE", "DROP"):
        if word in upper:
            reasons.append(f"금지키워드 {word}")
    blob = sql.upper().replace(" ", "")
    for token in case.sql_all:
        needle = token.upper().replace(" ", "")
        if needle not in blob and token not in sql:
            reasons.append(f"SQL에 {token} 없음")
    for token in case.sql_none:
        if token.upper() in upper:
            reasons.append(f"SQL에 {token} 있으면 안 됨")
    return reasons


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    settings = load_settings().with_overrides(semantic_plan_mode="hybrid")
    sessions: dict[str, SessionContext] = {}
    rows: list[dict[str, Any]] = []
    passed = 0
    t0 = time.perf_counter()
    engine = Llm2SqlEngine.from_settings(settings)
    try:
        print("=== 복합질문 30 스모크 (SEMANTIC_PLAN_MODE=hybrid, map=off) ===\n")
        for i, case in enumerate(CASES, 1):
            session = (
                sessions.setdefault(case.session, SessionContext())
                if case.session
                else None
            )
            t1 = time.perf_counter()
            timed_out = False
            error = None
            r = None
            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    fut = pool.submit(_ask, engine, case.q, session)
                    r = fut.result(timeout=TIMEOUT_S)
            except FuturesTimeout:
                timed_out = True
                error = f"timeout>{TIMEOUT_S}s"
                try:
                    engine.close()
                except Exception:
                    pass
                engine = Llm2SqlEngine.from_settings(settings)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"[:300]
                try:
                    engine.close()
                except Exception:
                    pass
                engine = Llm2SqlEngine.from_settings(settings)
            ms = int((time.perf_counter() - t1) * 1000)
            reasons: list[str] = []
            if timed_out:
                reasons.append(error or "timeout")
            elif r is None:
                reasons.append(error or "무응답")
            else:
                ans = str(r.answer or "").strip()
                if not r.ok or not ans:
                    reasons.append("응답 실패")
                route = str(r.route or "")
                if route in {"d198_value_bins", "d198_year_stats", "building_name_lookup"}:
                    reasons.append(f"금지 route={route}")
                if route in case.forbid_routes:
                    reasons.append(f"금지 route={route}")
                if "INSERT" in str(r.sql or "").upper():
                    reasons.append("쓰기 SQL")
                sql_text = str(r.sql or "")
                if case.want_list and re.search(r"COUNT\s*\(\s*\*\s*\)\s+AS\s+cnt", sql_text, re.I):
                    reasons.append("목록인데 COUNT만 실행")
                clarify = route.startswith("clarify") or route == "semantic_plan_clarify"
                if case.allow_clarify and clarify:
                    reasons = [x for x in reasons if x != "응답 실패"]
                    if ans:
                        reasons = []
                elif not clarify:
                    reasons.extend(_sql_ok(str(r.sql or ""), case))
                elif case.sql_all and not case.allow_clarify:
                    reasons.append(f"clarify로 이탈 route={route}")
            ok = not reasons
            if ok:
                passed += 1
            rec = {
                "id": case.id,
                "cat": case.cat,
                "q": case.q,
                "ok": ok,
                "reasons": reasons,
                "route": None if r is None else r.route,
                "error": error or (None if r is None else r.error),
                "latency_ms": ms,
                "answer": _clip("" if r is None else (r.answer or "")),
                "sql": _clip("" if r is None else str(r.sql or ""), 240),
                "row_count": 0 if r is None else (r.row_count or 0),
                "timed_out": timed_out,
                "session": case.session,
            }
            rows.append(rec)
            status = "OK" if ok else "FAIL"
            print(f"[{case.id}] {status}  {case.cat}  {ms}ms  route={rec['route']}")
            print(f"  Q: {case.q}")
            print(f"  A: {rec['answer'][:160]}")
            if reasons:
                print(f"  why: {'; '.join(reasons)}")
            if rec["error"]:
                print(f"  err: {rec['error']}")
            print()
            OUT.write_text(
                json.dumps(
                    {
                        "when": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "mode": "hybrid",
                        "elapsed_s": round(time.perf_counter() - t0, 1),
                        "total": len(CASES),
                        "ran": i,
                        "ok": passed,
                        "fail": i - passed,
                        "rows": rows,
                        "partial": i < len(CASES),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
    finally:
        try:
            engine.close()
        except Exception:
            pass

    total = len(CASES)
    elapsed = round(time.perf_counter() - t0, 1)
    print(f"=== 결과: {passed}/{total} OK  ({elapsed}s) ===")
    failed = [row for row in rows if not row["ok"]]
    if failed:
        print("실패:")
        for row in failed:
            print(f" - {row['id']} {row['q']}: {'; '.join(row['reasons'])}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
