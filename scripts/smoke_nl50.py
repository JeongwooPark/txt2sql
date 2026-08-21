"""신규 50문항 자연어 스모크 — 지명 사전·공간·임계·안내·후속 반영.

기존 smoke_gazetteer_nl / smoke_nl_queries 와 질의문을 겹치지 않게 새로 구성했다.
기대 건수는 2026-08-21 D010·행정동 경계 집계.
"""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from llm2sql import Llm2SqlEngine, SessionContext
from llm2sql.domain import extract_gu, extract_place, extract_places
from llm2sql.gazetteer import uses_admin_boundary
from llm2sql.guide_qa import try_guide
from llm2sql.intent_router import try_route


@dataclass
class Case:
    id: str
    cat: str
    q: str
    expect_answer: str
    session: str | None = None
    places: list[str] = field(default_factory=list)
    gu: str | None = None
    admin_only: bool | None = None
    forbid: list[str] = field(default_factory=list)
    filter: str | None = None
    route: str | tuple[str, ...] | None = None
    cnt: int | None = None
    ans_all: list[str] = field(default_factory=list)
    ans_none: list[str] = field(default_factory=list)
    min_cnt: int | None = None


def _infer_filter(sql: str) -> str:
    if not sql:
        return "none"
    u = sql.upper()
    if "ADM_NM" in u or "BND_ADM_DONG" in u:
        return "admin"
    if '"A4"' in sql or "A4" in sql:
        return "a4"
    return "other"


def _route_ok(got: str | None, expect: str | tuple[str, ...] | None) -> bool:
    if not expect:
        return True
    options = expect if isinstance(expect, tuple) else (expect,)
    got_s = str(got or "")
    return any(got_s == e or got_s.startswith(e) for e in options)


def _num_in_text(n: int, text: str) -> bool:
    raw = str(n)
    comma = f"{n:,}"
    compact = re.sub(r"[\s,]", "", text)
    return raw in text or comma in text or raw in compact


CASES: list[Case] = [
    # --- 안내·메타 ---
    Case(
        "Q01",
        "안내",
        "무엇을 할 수 있어?",
        "기능·역할 안내",
        route="guide_help",
        ans_all=["역할"],
        ans_none=["연산동"],
    ),
    Case(
        "Q02",
        "안내",
        "안녕하세요",
        "인사 + 짧은 사용법",
        route="guide_greeting",
        ans_all=["안녕"],
    ),
    Case(
        "Q03",
        "안내",
        "비트코인 시세 알려줘",
        "범위 외 안내",
        route="guide_out_of_scope",
        ans_all=["범위"],
    ),
    Case(
        "Q04",
        "안내",
        "할 수 잇는 것은",
        "오타 보정 후 기능 안내",
        route="guide_help",
        ans_all=["역할"],
    ),
    Case(
        "Q05",
        "메타",
        "어떤 데이터가 있어?",
        "보유 데이터셋 목록",
        ans_all=["건물"],
        ans_none=["날씨"],
    ),
    Case(
        "Q06",
        "메타",
        "법정동명은 어떤 속성이야?",
        "A4=법정동명 설명",
        ans_all=["A4"],
    ),
    # --- 법정동 ---
    Case(
        "Q07",
        "법정동",
        "연산동 건물이 몇 채야?",
        "15,258채 (A4)",
        places=["연산동"],
        admin_only=False,
        filter="a4",
        route="building_place_count",
        cnt=15258,
    ),
    Case(
        "Q08",
        "법정동",
        "부곡동 건물은 몇 채야?",
        "6,027채 (A4)",
        places=["부곡동"],
        filter="a4",
        route="building_place_count",
        cnt=6027,
    ),
    Case(
        "Q09",
        "법정동",
        "온천동 건물 수는?",
        "8,006채 (A4)",
        places=["온천동"],
        filter="a4",
        cnt=8006,
    ),
    Case(
        "Q10",
        "법정동",
        "연산동 공동주택은 몇 채야?",
        "1,318채 (A4·공동주택)",
        places=["연산동"],
        filter="a4",
        route="building_usage_count",
        cnt=1318,
    ),
    Case(
        "Q11",
        "법정동",
        "명장동에 있는 건물은 몇 개야?",
        "3,805채 (A4)",
        places=["명장동"],
        filter="a4",
        cnt=3805,
    ),
    Case(
        "Q12",
        "법정동",
        "괴정동 건물 몇 채야?",
        "8,376채 (A4)",
        places=["괴정동"],
        filter="a4",
        cnt=8376,
    ),
    # --- 행정동 ---
    Case(
        "Q13",
        "행정동",
        "장전1동 건물 몇 채야?",
        "2,216채 (행정 경계, 『안에』 없음)",
        places=["장전1동"],
        admin_only=True,
        filter="admin",
        route="building_in_dong_spatial",
        cnt=2216,
    ),
    Case(
        "Q14",
        "행정동",
        "연산1동 안에 있는 건물 건수는?",
        "1,399채 (ST_Intersects)",
        places=["연산1동"],
        admin_only=True,
        filter="admin",
        route="building_in_dong_spatial",
        cnt=1399,
    ),
    Case(
        "Q15",
        "행정동",
        "장전1동 아파트는 몇 채야?",
        "402채 (공동주택·행정 경계)",
        places=["장전1동"],
        admin_only=True,
        filter="admin",
        route="building_admin_dong_usage_count",
        cnt=402,
    ),
    Case(
        "Q16",
        "행정동",
        "재송2동 건물 몇 채야?",
        "1,624채 (행정 경계)",
        places=["재송2동"],
        admin_only=True,
        filter="admin",
        cnt=1624,
    ),
    Case(
        "Q17",
        "행정동",
        "온천1동 안에 있는 건물은 몇 채야?",
        "2,584채",
        places=["온천1동"],
        admin_only=True,
        filter="admin",
        cnt=2584,
    ),
    # --- 구군 ---
    Case(
        "Q18",
        "구군",
        "수영구 건물 몇 채야?",
        "17,768채",
        places=["수영구"],
        gu="수영구",
        filter="a4",
        cnt=17768,
    ),
    Case(
        "Q19",
        "구군",
        "사상구 공장은 몇 채야?",
        "4,791채",
        places=["사상구"],
        gu="사상구",
        route="building_usage_count",
        cnt=4791,
        ans_all=["공장"],
    ),
    Case(
        "Q20",
        "구군",
        "사하구 건물은 얼마나 되나요?",
        "41,271채",
        places=["사하구"],
        gu="사하구",
        cnt=41271,
    ),
    Case(
        "Q21",
        "구군",
        "연제구 단독주택은 몇 채야?",
        "9,051채",
        places=["연제구"],
        gu="연제구",
        cnt=9051,
    ),
    # --- 읍·가 ---
    Case(
        "Q22",
        "읍·가",
        "일광읍 건물 몇 채야?",
        "9,505채 (행정 읍)",
        places=["일광읍"],
        admin_only=True,
        filter="admin",
        cnt=9505,
    ),
    Case(
        "Q23",
        "읍·가",
        "일광읍 아파트는 몇 채야?",
        "84채 (공동주택·행정 읍)",
        places=["일광읍"],
        admin_only=True,
        filter="admin",
        cnt=84,
    ),
    Case(
        "Q24",
        "읍·가",
        "남포동1가 건물 수는?",
        "99채 (법정 가)",
        places=["남포동1가"],
        admin_only=False,
        filter="a4",
        cnt=99,
    ),
    Case(
        "Q25",
        "읍·가",
        "충무동1가에 있는 건물은 몇 채야?",
        "381채",
        places=["충무동1가"],
        filter="a4",
        cnt=381,
    ),
    Case(
        "Q26",
        "읍·가",
        "재송동 건물 몇 채야?",
        "3,928채 (법정동)",
        places=["재송동"],
        filter="a4",
        cnt=3928,
    ),
    # --- 오탐·건물명 ---
    Case(
        "Q27",
        "오탐방지",
        "공동주택이 몇 채야?",
        "『공동』을 동으로 쓰지 않음",
        places=[],
        forbid=["공동"],
    ),
    Case(
        "Q28",
        "오탐방지",
        "구서역 포르투나의 시공년도는?",
        "사용승인일 2022년",
        places=[],
        forbid=["구서역"],
        route="building_name_lookup",
        ans_all=["포르투나", "2022"],
        ans_none=["구서역을 법정동"],
    ),
    Case(
        "Q29",
        "오탐방지",
        "오늘 연산동 날씨 어때?",
        "지명이 있어도 날씨는 범위 외",
        places=["연산동"],
        route="guide_out_of_scope",
        ans_all=["범위"],
        ans_none=["15,258", "15258"],
    ),
    Case(
        "Q30",
        "오탐방지",
        "원리원칙을 설명해 줘",
        "짧은 리(원리) 오탐 없음",
        places=[],
        forbid=["원리"],
    ),
    # --- 임계 ---
    Case(
        "Q31",
        "임계",
        "수영구에서 건물 높이가 40미터 이상인 건물은 몇 개야?",
        "224동",
        gu="수영구",
        route="building_height_count",
        cnt=224,
    ),
    Case(
        "Q32",
        "임계",
        "연제구에서 지상층이 15층 이상인 건물은 몇 개야?",
        "311동",
        gu="연제구",
        route="building_floor_count",
        cnt=311,
    ),
    Case(
        "Q33",
        "임계",
        "연산동에서 연면적 100평 이상인 건물은 몇 채야?",
        "2,746채 (100평=법정환산 ㎡)",
        places=["연산동"],
        filter="a4",
        route="building_area_threshold_count",
        cnt=2746,
    ),
    Case(
        "Q34",
        "임계",
        "장전1동에서 연면적 100평 이상인 건물은?",
        "행정동 임계, 0건이 아님",
        places=["장전1동"],
        admin_only=True,
        filter="admin",
        route="building_area_threshold_",
        min_cnt=1,
    ),
    Case(
        "Q35",
        "임계",
        "연제구에서 연면적 2000 이상인 건물 수는?",
        "837동",
        gu="연제구",
        route="building_area_threshold_count",
        cnt=837,
    ),
    # --- 공간 ---
    Case(
        "Q36",
        "공간",
        "연산1동과 교차하는 기초구역은 몇 개야?",
        "기초구역 ∩ 행정동 COUNT",
        places=["연산1동"],
        filter="admin",
        route="spatial_bas_dong_count",
        min_cnt=1,
    ),
    Case(
        "Q37",
        "공간",
        "사상구 기초구역 개수는?",
        "속성 COUNT (ST_ 없음)",
        gu="사상구",
        route="bas_count",
        min_cnt=1,
        ans_none=["ST_"],
    ),
    Case(
        "Q38",
        "공간",
        "장전1동 주변 50m 안에 있는 건물 건수는?",
        "행정동 버퍼 COUNT",
        places=["장전1동"],
        filter="admin",
        route="place_buffer_count",
        min_cnt=1,
    ),
    Case(
        "Q39",
        "공간",
        "좌표(129.08, 35.16)에서 300미터 이내 건물 건수",
        "점 버퍼 COUNT",
        route="buffer_count",
        min_cnt=1,
    ),
    Case(
        "Q40",
        "공간",
        "연산동에 있는 건물이 연산1동과 연산2동에 몇 퍼센트씩 있는가?",
        "법정동→행정동 분배",
        places=["연산동", "연산1동", "연산2동"],
        route="legal_dong_admin_share",
        ans_all=["연산1동", "%"],
    ),
    # --- 프로필·순위·후속 ---
    Case(
        "Q41",
        "프로필",
        "부곡동 아파트의 특징은?",
        "부곡동 공동주택 요약",
        places=["부곡동"],
        route="building_profile",
        ans_all=["부곡동"],
    ),
    Case(
        "Q42",
        "프로필",
        "장전1동이랑 장전2동 아파트 비교해줘",
        "두 행정동 공동주택 비교",
        places=["장전1동", "장전2동"],
        admin_only=True,
        route="building_profile_compare",
        ans_all=["장전"],
    ),
    Case(
        "Q43",
        "순위",
        "사상구에서 연면적이 가장 큰 공장은?",
        "사상구 공장 연면적 1위",
        session="rank",
        gu="사상구",
        route="building_rank_",
        ans_none=["찾지 못했"],
    ),
    Case(
        "Q44",
        "후속",
        "지번은?",
        "직전 공장의 지번",
        session="rank",
        route=("followup_", "d010_attr_"),
        ans_none=["찾지 못했"],
    ),
    Case(
        "Q45",
        "연도",
        "동래구 각년도별 아파트 건립 수는?",
        "동래 D198 연도 집계",
        session="year",
        gu="동래구",
        route="d198_year_stats",
        min_cnt=1,
        ans_all=["동래"],
    ),
    Case(
        "Q46",
        "연도",
        "5년 단위로 출력하라",
        "같은 범위 5년 구간",
        session="year",
        route="d198_year_stats",
        ans_all=["동래"],
    ),
    Case(
        "Q47",
        "구간",
        "동래구 아파트 연면적 크기별 수는?",
        "동래 연면적 구간 동수",
        gu="동래구",
        route="d198_value_bins",
        ans_all=["동"],
    ),
    # --- 산업·구조 ---
    Case(
        "Q48",
        "산업단지",
        "사상구 산업단지 안에 있는 건물은 몇 채야?",
        "사상구 ∩ 산업단지 건물 수",
        gu="사상구",
        route="buildings_in_industrial",
        min_cnt=1,
    ),
    Case(
        "Q49",
        "구조",
        "부곡동의 콘크리트 구조물은?",
        "부곡동 A11 콘크리트 목록/건수",
        places=["부곡동"],
        filter="a4",
        route="building_structure_",
        ans_none=["찾지 못했"],
    ),
    Case(
        "Q50",
        "안내",
        "제한이 뭐야?",
        "지원 범위·제한 안내",
        route="guide_limits",
        ans_all=["제한"],
    ),
]


def _clip(text: str, n: int = 180) -> str:
    t = (text or "").replace("\n", " / ")
    return t if len(t) <= n else t[: n - 3] + "..."


def main() -> int:
    out_path = Path(__file__).with_name("_out_nl50.json")
    sessions: dict[str, SessionContext] = {}
    rows: list[dict[str, Any]] = []
    t0 = time.perf_counter()
    passed = 0
    failed: list[str] = []

    with Llm2SqlEngine.from_env() as engine:
        print("=== 신규 50문항 자연어 스모크 ===\n")
        for case in CASES:
            reasons: list[str] = []
            places = extract_places(case.q)
            gu = extract_gu(case.q)
            first = extract_place(case.q)
            admin = uses_admin_boundary(first) if first else False
            if case.places and places != case.places:
                reasons.append(f"추출 {places} ≠ {case.places}")
            if case.gu is not None and gu != case.gu:
                reasons.append(f"구 {gu} ≠ {case.gu}")
            if case.admin_only is not None and admin != case.admin_only:
                reasons.append(f"행정전용 {admin} ≠ {case.admin_only}")
            for bad in case.forbid:
                if bad in places:
                    reasons.append(f"오탐 '{bad}'")

            guide = try_guide(case.q)
            routed = try_route(case.q)
            intent = None if routed is None else routed.intent
            sql = "" if routed is None else routed.sql
            if case.filter:
                inferred = _infer_filter(sql)
                if guide is not None and not sql:
                    inferred = "none"
                if case.filter == "gu" and inferred == "a4":
                    pass
                elif inferred != case.filter and not (
                    case.filter == "none" and inferred in {"none", "other"}
                ):
                    if not (case.filter == "none" and guide is not None):
                        reasons.append(f"filter={inferred} (expect {case.filter})")
            if case.route and str(case.q) and not case.session:
                got = intent or (guide.intent if guide else None)
                if str(case.route).startswith("guide_"):
                    if not _route_ok(guide.intent if guide else None, case.route) and not _route_ok(
                        got, case.route
                    ):
                        reasons.append(f"route={got} (expect {case.route})")
                elif not _route_ok(intent, case.route) and not (
                    case.route == "building_profile"
                    or str(case.route).startswith("building_profile")
                ):
                    # 프로필은 try_route가 비어도 엔진에서 처리
                    if not str(case.route).startswith("building_profile"):
                        reasons.append(f"route={intent} (expect {case.route})")
            session = (
                sessions.setdefault(case.session, SessionContext())
                if case.session
                else None
            )
            t1 = time.perf_counter()
            r = engine.ask(case.q, session=session)
            ms = int((time.perf_counter() - t1) * 1000)
            answer = r.answer or ""
            engine_route = r.route
            cnt = None
            if r.rows and "cnt" in r.rows[0]:
                try:
                    cnt = int(r.rows[0]["cnt"])
                except (TypeError, ValueError):
                    cnt = r.rows[0]["cnt"]
            if not r.ok or not str(answer).strip():
                reasons.append("응답 실패")
                if r.error:
                    reasons.append(str(r.error))
            if case.route:
                check_route = engine_route or intent
                if not _route_ok(check_route, case.route):
                    reasons.append(f"engine route={engine_route} (expect {case.route})")
            for tok in case.ans_all:
                if tok not in answer:
                    reasons.append(f"답에 '{tok}' 없음")
            for tok in case.ans_none:
                if tok in answer:
                    reasons.append(f"답에 금지 '{tok}'")
            if case.cnt is not None:
                if cnt is not None and int(cnt) != case.cnt:
                    reasons.append(f"cnt={cnt} ≠ {case.cnt}")
                elif cnt is None and not _num_in_text(case.cnt, answer):
                    reasons.append(f"답에 건수 {case.cnt} 없음")
            if case.min_cnt is not None:
                n = cnt if cnt is not None else (r.row_count or 0)
                if n < case.min_cnt and not any(ch.isdigit() for ch in answer):
                    reasons.append(f"건수 부족 n={n}")

            ok = not reasons
            if ok:
                passed += 1
            else:
                failed.append(f"{case.id} {case.q}: {'; '.join(reasons)}")
            status = "OK" if ok else "FAIL"
            print(f"[{case.id}] {status}  {case.cat}")
            print(f"  Q: {case.q}")
            print(f"  expect: {case.expect_answer}")
            print(f"  extract: {places} gu={gu} admin={admin}")
            print(f"  route: {engine_route or intent} cnt={cnt} {ms}ms")
            print(f"  A: {_clip(answer)}")
            if reasons:
                print(f"  why: {'; '.join(reasons)}")
            print()
            rows.append(
                {
                    "id": case.id,
                    "cat": case.cat,
                    "q": case.q,
                    "expect_answer": case.expect_answer,
                    "ok": ok,
                    "why": reasons,
                    "places": places,
                    "engine_route": engine_route,
                    "intent": intent,
                    "cnt": cnt,
                    "expect_cnt": case.cnt,
                    "answer": _clip(answer, 240),
                    "ms": ms,
                }
            )

    elapsed = time.perf_counter() - t0
    total = len(CASES)
    payload = {
        "when": time.strftime("%Y-%m-%d %H:%M"),
        "elapsed_s": round(elapsed, 1),
        "total": total,
        "ok": passed,
        "fail": total - passed,
        "rows": rows,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"=== 결과: {passed}/{total} OK  {elapsed:.1f}s ===")
    print(f"JSON: {out_path}")
    if failed:
        print("실패:")
        for item in failed:
            print(" -", item)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
