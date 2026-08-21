"""지명 사전(법정동·행정동·구군·시도) 자연어 질의 스모크.

추출(gazetteer) → 규칙 라우트 SQL → 엔진 응답을 한 세트로 검증한다.
기존 ~동 정규식 오탐과, 행정동/읍면이 A4로 새는 경로를 함께 본다.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from llm2sql import Llm2SqlEngine
from llm2sql.domain import extract_gu, extract_place, extract_places
from llm2sql.gazetteer import (
    KIND_ADMIN,
    KIND_LEGAL,
    KIND_SIDO,
    KIND_SIGUNGU,
    classify_place,
    find_places,
    uses_admin_boundary,
)
from llm2sql.guide_qa import try_guide
from llm2sql.intent_router import try_route
from llm2sql.profile_qa import is_profile_question

KIND_LABEL = {
    KIND_LEGAL: "법정동",
    KIND_ADMIN: "행정동",
    KIND_SIGUNGU: "구군",
    KIND_SIDO: "시도",
}


@dataclass
class Case:
    id: str
    cat: str
    q: str
    places: list[str] = field(default_factory=list)
    gu: str | None = None
    admin_only: bool | None = None
    forbid: list[str] = field(default_factory=list)
    filter: str | None = None  # a4 | admin | gu | none
    sql_all: list[str] = field(default_factory=list)
    sql_none: list[str] = field(default_factory=list)
    route: str | tuple[str, ...] | None = None
    guide: str | None = None
    ask: bool = True
    ans_all: list[str] = field(default_factory=list)
    ans_none: list[str] = field(default_factory=list)
    note: str = ""


CASES: list[Case] = [
    # --- 법정동 ---
    Case(
        "L01",
        "법정동",
        "구서동 건물 몇 채야?",
        places=["구서동"],
        admin_only=False,
        filter="a4",
        sql_all=["구서동", "COUNT"],
        sql_none=["ADM_NM", "구서1동"],
        route="building_place_count",
        note="법정동은 A4 주소 필터",
    ),
    Case(
        "L02",
        "법정동",
        "장전동에 있는 공동주택은 몇 채야?",
        places=["장전동"],
        admin_only=False,
        filter="a4",
        sql_all=["장전동", "공동주택"],
        route="building_usage_count",
    ),
    Case(
        "L03",
        "법정동",
        "송정동 아파트 몇 채 있어?",
        places=["송정동"],
        admin_only=False,
        filter="a4",
        sql_all=["송정동"],
    ),
    Case(
        "L04",
        "법정동",
        "월내리 건물은 몇 채야?",
        places=["월내리"],
        admin_only=False,
        filter="a4",
        note="법정 리. 라우터가 동 접미사만 보면 누락될 수 있음",
    ),
    Case(
        "L05",
        "법정동",
        "서동에 단독주택이 얼마나 되나요?",
        places=["서동"],
        gu=None,
        admin_only=False,
        filter="a4",
        sql_all=["서동"],
        note="짧은 동명도 사전에 있으면 추출",
    ),
    # --- 행정동 ---
    Case(
        "A01",
        "행정동",
        "구서1동 안에 있는 건물 건수는?",
        places=["구서1동"],
        admin_only=True,
        filter="admin",
        sql_all=["ADM_NM", "ST_Intersects", "구서1동"],
        sql_none=['LIKE \'% 구서1동\''],
        route="building_in_dong_spatial",
        note="번호 행정동은 경계 교차",
    ),
    Case(
        "A02",
        "행정동",
        "구서2동 안에 있는 건물은 몇 채야?",
        places=["구서2동"],
        admin_only=True,
        filter="admin",
        sql_all=["ADM_NM", "구서2동"],
        route="building_in_dong_spatial",
    ),
    Case(
        "A03",
        "행정동",
        "구서1동 건물 몇 채야?",
        places=["구서1동"],
        admin_only=True,
        filter="admin",
        note="『안에』 없이도 행정동이면 경계 교차여야 함",
    ),
    Case(
        "A04",
        "행정동",
        "행정동 구서1동 기준으로 공동주택은 몇 채야?",
        places=["구서1동"],
        admin_only=True,
        filter="admin",
        note="『행정동』을 명시해도 구서1동만 잡아야 함",
    ),
    Case(
        "A05",
        "행정동",
        "우1동 안에 있는 건물 목록을 보여줘",
        places=["우1동"],
        admin_only=True,
        filter="admin",
        sql_all=["ADM_NM", "우1동"],
        route="building_in_dong_spatial_list",
    ),
    Case(
        "A06",
        "행정동",
        "광복동 건물 몇 채야?",
        places=["광복동"],
        admin_only=True,
        filter="admin",
        note="광복동은 행정동, 법정은 광복동1가·2가",
    ),
    # --- 겹침 ---
    Case(
        "D01",
        "법정·행정 겹침",
        "감전동 건물 몇 채야?",
        places=["감전동"],
        admin_only=False,
        filter="a4",
        sql_all=["감전동"],
        sql_none=["ADM_NM"],
        route="building_place_count",
        note="둘 다 있으면 법정동 A4",
    ),
    Case(
        "D02",
        "법정·행정 겹침",
        "당리동 공동주택은 몇 채야?",
        places=["당리동"],
        admin_only=False,
        filter="a4",
        sql_all=["당리동"],
    ),
    Case(
        "D03",
        "법정·행정 겹침",
        "초읍동에 건물이 몇 개나 있어?",
        places=["초읍동"],
        admin_only=False,
        filter="a4",
    ),
    # --- 구군 ---
    Case(
        "G01",
        "구군",
        "금정구 건물 몇 채야?",
        places=["금정구"],
        gu="금정구",
        filter="gu",
        sql_all=["금정구", "COUNT"],
        sql_none=["ADM_NM"],
        route="building_place_count",
    ),
    Case(
        "G02",
        "구군",
        "해운대구에서 아파트는 몇 채야?",
        places=["해운대구"],
        gu="해운대구",
        filter="gu",
        sql_all=["해운대구"],
    ),
    Case(
        "G03",
        "구군",
        "기장군 건물은 얼마나 되나요?",
        places=["기장군"],
        gu="기장군",
        filter="gu",
        sql_all=["기장군"],
    ),
    Case(
        "G04",
        "구군",
        "중구에 있는 건물 수는?",
        places=["중구"],
        gu="중구",
        filter="gu",
        sql_all=["중구"],
        note="짧은 구명. 중동과 구분",
    ),
    Case(
        "G05",
        "구군",
        "금정구 구서동 공동주택은 몇 채야?",
        places=["구서동"],
        gu="금정구",
        admin_only=False,
        filter="a4",
        sql_all=["구서동", "금정구"],
    ),
    # --- 시도·오탐 ---
    Case(
        "S01",
        "시도·오탐방지",
        "부산대학교 근처 건물은?",
        places=[],
        forbid=["부산", "부산시", "부산광역시"],
        filter="none",
        note="부산 별칭은 스캔에서 제외",
        ask=True,
    ),
    Case(
        "S02",
        "시도·오탐방지",
        "부산광역시 금정구 건물 몇 채야?",
        places=["금정구"],
        gu="금정구",
        filter="gu",
        sql_all=["금정구"],
        note="시도는 동/구보다 후순위, 구군만 필터",
    ),
    Case(
        "S03",
        "시도·오탐방지",
        "공동주택 몇 채야?",
        places=[],
        forbid=["공동"],
        note="공동주택에서 공동동 오탐 금지",
    ),
    Case(
        "S04",
        "시도·오탐방지",
        "구서역 포르투나의 시공년도는",
        places=[],
        forbid=["구서역"],
        route="building_name_lookup",
        ans_all=["포르투나"],
        ans_none=["구서역을 법정동"],
    ),
    Case(
        "S05",
        "시도·오탐방지",
        "할 수 있는 것을 말해",
        places=[],
        guide="guide_help",
        filter="none",
        route="guide_",
    ),
    Case(
        "S06",
        "시도·오탐방지",
        "오늘 날씨 어때?",
        places=[],
        guide="guide_out_of_scope",
        filter="none",
        route="guide_",
    ),
    Case(
        "S07",
        "시도·오탐방지",
        "원리원칙이 뭐야?",
        places=[],
        forbid=["원리"],
        note="짧은 법정 리(원리) 부분일치 오탐",
        ask=False,
    ),
    Case(
        "S08",
        "시도·오탐방지",
        "고리원자력발전소는 어디에 있어?",
        places=[],
        forbid=["고리"],
        note="법정 리 고리 오탐",
        ask=False,
    ),
    # --- 최장일치 ---
    Case(
        "M01",
        "최장일치",
        "중구 광복동1가 건물 몇 채야?",
        places=["광복동1가"],
        gu="중구",
        admin_only=False,
        filter="a4",
        sql_all=["광복동1가"],
        sql_none=["ADM_NM"],
        note="광복동보다 광복동1가가 길다",
    ),
    Case(
        "M02",
        "최장일치",
        "남포동2가에 있는 건물은 몇 채야?",
        places=["남포동2가"],
        admin_only=False,
        filter="a4",
        sql_all=["남포동2가"],
    ),
    Case(
        "M03",
        "최장일치",
        "해운대구 우동 건물 몇 채야?",
        places=["우동"],
        gu="해운대구",
        admin_only=False,
        filter="a4",
        sql_all=["우동", "해운대구"],
        sql_none=["우1동"],
        note="우동(법정) ≠ 우1동(행정)",
    ),
    Case(
        "M04",
        "최장일치",
        "해운대구 우1동 안에 있는 건물 건수는?",
        places=["우1동"],
        gu="해운대구",
        admin_only=True,
        filter="admin",
        sql_all=["우1동", "ADM_NM"],
    ),
    Case(
        "M05",
        "최장일치",
        "보수동1가 건물 수는?",
        places=["보수동1가"],
        admin_only=False,
        filter="a4",
    ),
    # --- 복합·비교 ---
    Case(
        "C01",
        "복합·비교",
        "구서1동과 구서2동과 구서동 아파트 특징 비교",
        places=["구서1동", "구서2동", "구서동"],
        note="세 동을 종류별로 유지",
    ),
    Case(
        "C02",
        "복합·비교",
        "구서동에 있는 건물이 구서1동에 몇%, 구서2동에 몇%있는가?",
        places=["구서동", "구서1동", "구서2동"],
        filter="admin",
        sql_all=["구서1동", "구서2동", "ST_Intersects"],
        route="legal_dong_admin_share",
    ),
    Case(
        "C03",
        "복합·비교",
        "구서1동이랑 구서2동 아파트 비교해줘",
        places=["구서1동", "구서2동"],
        admin_only=True,
        note="행정동 프로필 비교",
    ),
    Case(
        "C04",
        "복합·비교",
        "금정구 장전동이랑 구서동 건물 수 알려줘",
        places=["장전동", "구서동"],
        gu="금정구",
    ),
    # --- 읍·면 ---
    Case(
        "E01",
        "읍·면",
        "기장읍 건물 몇 채야?",
        places=["기장읍"],
        admin_only=True,
        filter="admin",
        note="읍은 행정구역. ~동 정규식이면 누락",
    ),
    Case(
        "E02",
        "읍·면",
        "철마면 안에 있는 건물 건수는?",
        places=["철마면"],
        admin_only=True,
        filter="admin",
    ),
    Case(
        "E03",
        "읍·면",
        "정관읍 아파트는 몇 채야?",
        places=["정관읍"],
        admin_only=True,
        filter="admin",
    ),
    Case(
        "E04",
        "읍·면",
        "일광읍이랑 장안읍 건물 비교",
        places=["일광읍", "장안읍"],
        admin_only=True,
    ),
    # --- 구어체·신형 ---
    Case(
        "N01",
        "구어체·신형",
        "구서동에 집이 몇 채나 있어?",
        places=["구서동"],
        admin_only=False,
        filter="a4",
    ),
    Case(
        "N02",
        "구어체·신형",
        "금정구에는 건물이 얼마나 돼?",
        places=["금정구"],
        gu="금정구",
        filter="gu",
    ),
    Case(
        "N03",
        "구어체·신형",
        "구서1동에서는 아파트가 몇 동인가요?",
        places=["구서1동"],
        admin_only=True,
        filter="admin",
    ),
    Case(
        "N04",
        "구어체·신형",
        "법정동 구서동 기준으로 건물 수 구해줘",
        places=["구서동"],
        admin_only=False,
        filter="a4",
        forbid=["법정동"],
        note="『법정동』 단어 자체는 지명이 아님",
    ),
    Case(
        "N05",
        "구어체·신형",
        "구서1동 주변 100m 안에 있는 건물은?",
        places=["구서1동"],
        admin_only=True,
        filter="admin",
        sql_all=["ST_DWithin", "구서1동"],
        route="place_buffer_list",
    ),
    Case(
        "N06",
        "구어체·신형",
        "구서동에서 연면적 100평 이상인 건물은 몇 채야?",
        places=["구서동"],
        admin_only=False,
        filter="a4",
        sql_all=["구서동"],
        sql_none=["d198_value_bins"],
    ),
    Case(
        "N07",
        "구어체·신형",
        "구서1동에서 연면적 100평 이상인 건물은?",
        places=["구서1동"],
        admin_only=True,
        filter="admin",
        note="행정동+임계값",
    ),
    Case(
        "N08",
        "구어체·신형",
        "오늘 중동 날씨 어때?",
        places=["중동"],
        admin_only=False,
        note="중동은 해운대 법정동. 날씨+지명이 도메인으로 새는지",
        ask=True,
    ),
    Case(
        "N09",
        "구어체·신형",
        "구 서 1 동 건물 몇 채야?",
        places=[],
        note="띄어 쓴 행정동은 미등록으로 두는 편이 안전",
        ask=False,
    ),
    Case(
        "N10",
        "구어체·신형",
        "해운대구 중동이랑 우동 중에 건물 많은 데는?",
        places=["중동", "우동"],
        gu="해운대구",
        admin_only=False,
    ),
]


def _kinds_label(name: str) -> str:
    kinds = classify_place(name)
    if not kinds:
        return "미등록"
    order = (KIND_LEGAL, KIND_ADMIN, KIND_SIGUNGU, KIND_SIDO)
    return "+".join(KIND_LABEL[k] for k in order if k in kinds)


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


def _sql_issues(sql: str, case: Case) -> list[str]:
    reasons: list[str] = []
    for token in case.sql_all:
        if token.lower() not in sql.lower() and token not in sql:
            reasons.append(f"SQL에 '{token}' 없음")
    for token in case.sql_none:
        if token in sql:
            reasons.append(f"SQL에 금지 '{token}'")
    return reasons


def _check_extract(case: Case) -> tuple[bool, list[str], dict[str, Any]]:
    reasons: list[str] = []
    places = extract_places(case.q)
    gu = extract_gu(case.q)
    hits = find_places(case.q)
    first = extract_place(case.q)
    admin = uses_admin_boundary(first) if first else False

    if places != case.places:
        reasons.append(f"추출 {places} ≠ {case.places}")
    if case.gu is not None and gu != case.gu:
        reasons.append(f"구 {gu} ≠ {case.gu}")
    if case.admin_only is not None and admin != case.admin_only:
        reasons.append(f"행정전용 {admin} ≠ {case.admin_only}")
    for bad in case.forbid:
        if bad in places or any(h.name == bad for h in hits):
            reasons.append(f"오탐 '{bad}'")

    info = {
        "places": places,
        "gu": gu,
        "first": first,
        "admin_only": admin,
        "hits": [
            {"name": h.name, "kinds": sorted(h.kinds), "span": [h.start, h.end]}
            for h in hits
        ],
        "kinds": {p: _kinds_label(p) for p in places},
    }
    return not reasons, reasons, info


def _check_route(case: Case, sql: str, intent: str | None, guide_intent: str | None) -> list[str]:
    reasons: list[str] = []
    if case.guide:
        if guide_intent != case.guide and not (
            case.guide.endswith("_") and str(guide_intent or "").startswith(case.guide)
        ):
            if not (case.route and _route_ok(intent, case.route)):
                reasons.append(f"guide={guide_intent} (expect {case.guide})")
    if case.route:
        got = intent or (f"guide_{guide_intent}" if guide_intent else None)
        # guide route like guide_help comes from try_guide, not try_route
        if str(case.route).startswith("guide_"):
            g = guide_intent or ""
            if not (g.startswith("guide") or str(got or "").startswith("guide_")):
                reasons.append(f"route={got} (expect {case.route})")
        elif not _route_ok(intent, case.route):
            reasons.append(f"route={intent} (expect {case.route})")
    if case.filter:
        inferred = _infer_filter(sql)
        if guide_intent and not sql:
            inferred = "none"
        expected = case.filter
        if expected == "gu" and inferred == "a4":
            pass
        elif expected == "none":
            if inferred in {"a4", "admin"} and not guide_intent:
                reasons.append(f"filter={inferred} (expect none)")
        elif inferred != expected:
            reasons.append(f"filter={inferred} (expect {expected})")
    reasons.extend(_sql_issues(sql, case))
    return reasons


def _clip(text: str, n: int = 160) -> str:
    t = (text or "").replace("\n", " / ")
    return t if len(t) <= n else t[: n - 3] + "..."


def main() -> int:
    out_path = Path(__file__).with_name("_out_gazetteer_nl.json")
    rows: list[dict[str, Any]] = []
    extract_fail = 0
    route_fail = 0
    ask_fail = 0
    asked = 0
    t0 = time.perf_counter()

    engine: Llm2SqlEngine | None = None
    if any(c.ask for c in CASES):
        engine = Llm2SqlEngine.from_env()

    try:
        print("=== 지명 사전 자연어 스모크 ===\n")
        for case in CASES:
            ext_ok, ext_why, ext_info = _check_extract(case)
            guide = try_guide(case.q)
            guide_intent = None if guide is None else guide.intent
            routed = try_route(case.q)
            intent = None if routed is None else routed.intent
            sql = "" if routed is None else routed.sql
            # 프로필 비교는 try_route가 비어도 정상일 수 있음
            if is_profile_question(case.q) and not case.route:
                pass
            route_why = _check_route(case, sql, intent, guide_intent)

            ask_ok = True
            ask_why: list[str] = []
            answer = ""
            engine_route = None
            engine_sql = None
            row_count = None
            cnt = None
            elapsed_ms = None
            if case.ask and engine is not None:
                asked += 1
                t1 = time.perf_counter()
                try:
                    r = engine.ask(case.q)
                except Exception as exc:  # noqa: BLE001
                    ask_ok = False
                    ask_why.append(f"예외 {type(exc).__name__}: {exc}")
                    r = None
                elapsed_ms = int((time.perf_counter() - t1) * 1000)
                if r is not None:
                    answer = r.answer or ""
                    engine_route = r.route
                    engine_sql = r.sql
                    row_count = r.row_count
                    if r.rows and "cnt" in r.rows[0]:
                        try:
                            cnt = int(r.rows[0]["cnt"])
                        except (TypeError, ValueError):
                            cnt = r.rows[0]["cnt"]
                    if not r.ok or not str(answer).strip():
                        ask_ok = False
                        ask_why.append("응답 실패")
                        if r.error:
                            ask_why.append(str(r.error))
                    for token in case.ans_all:
                        if token not in answer:
                            ask_ok = False
                            ask_why.append(f"답에 '{token}' 없음")
                    for token in case.ans_none:
                        if token in answer:
                            ask_ok = False
                            ask_why.append(f"답에 금지 '{token}'")
                    if case.route and str(case.route).startswith("guide_"):
                        if not str(engine_route or "").startswith("guide_"):
                            ask_ok = False
                            ask_why.append(f"engine route={engine_route}")
                    # 행정동 기대인데 0건이면 필터 오용 가능성
                    if (
                        case.filter == "admin"
                        and cnt == 0
                        and case.id in {"A01", "A02", "A03", "M04"}
                    ):
                        ask_ok = False
                        ask_why.append("행정동 건수 0")
                    if case.filter == "a4" and case.id in {"L01", "D01", "G01"} and cnt == 0:
                        ask_ok = False
                        ask_why.append("건수 0")

            if not ext_ok:
                extract_fail += 1
            if route_why:
                route_fail += 1
            if case.ask and not ask_ok:
                ask_fail += 1

            overall = ext_ok and not route_why and (ask_ok if case.ask else True)
            status = "OK" if overall else "FAIL"
            print(f"[{case.id}] {status}  {case.cat}")
            print(f"  Q: {case.q}")
            print(
                f"  extract: {ext_info['places']} kinds={ext_info['kinds']}"
                f" gu={ext_info['gu']} admin={ext_info['admin_only']}"
            )
            print(f"  route: {intent or guide_intent}  filter={_infer_filter(sql)}")
            if ext_why:
                print(f"  extract-why: {'; '.join(ext_why)}")
            if route_why:
                print(f"  route-why: {'; '.join(route_why)}")
            if case.ask:
                print(f"  ask: route={engine_route} cnt={cnt} {elapsed_ms}ms")
                print(f"  A: {_clip(answer)}")
                if ask_why:
                    print(f"  ask-why: {'; '.join(ask_why)}")
            print()

            rows.append(
                {
                    "id": case.id,
                    "cat": case.cat,
                    "q": case.q,
                    "note": case.note,
                    "ok": overall,
                    "extract_ok": ext_ok,
                    "route_ok": not route_why,
                    "ask_ok": ask_ok if case.ask else None,
                    "extract_why": ext_why,
                    "route_why": route_why,
                    "ask_why": ask_why,
                    "places": ext_info["places"],
                    "expect_places": case.places,
                    "kinds": ext_info["kinds"],
                    "gu": ext_info["gu"],
                    "admin_only": ext_info["admin_only"],
                    "hits": ext_info["hits"],
                    "intent": intent,
                    "guide": guide_intent,
                    "sql": sql[:500] if sql else "",
                    "filter": _infer_filter(sql),
                    "expect_filter": case.filter,
                    "engine_route": engine_route,
                    "engine_sql": (engine_sql or "")[:400] if engine_sql else "",
                    "answer": _clip(answer, 220),
                    "cnt": cnt,
                    "row_count": row_count,
                    "ms": elapsed_ms,
                    "asked": case.ask,
                }
            )
    finally:
        if engine is not None:
            engine.close()

    elapsed = time.perf_counter() - t0
    total = len(CASES)
    extract_ok_n = total - extract_fail
    route_ok_n = total - route_fail
    ask_ok_n = asked - ask_fail
    overall_ok = sum(1 for r in rows if r["ok"])

    payload = {
        "when": time.strftime("%Y-%m-%d %H:%M"),
        "elapsed_s": round(elapsed, 1),
        "total": total,
        "overall_ok": overall_ok,
        "extract_ok": extract_ok_n,
        "route_ok": route_ok_n,
        "ask_ok": ask_ok_n,
        "asked": asked,
        "extract_fail": extract_fail,
        "route_fail": route_fail,
        "ask_fail": ask_fail,
        "rows": rows,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"=== 결과: 종합 {overall_ok}/{total}  "
        f"추출 {extract_ok_n}/{total}  라우트 {route_ok_n}/{total}  "
        f"엔진 {ask_ok_n}/{asked}  {elapsed:.1f}s ==="
    )
    print(f"JSON: {out_path}")
    fails = [r for r in rows if not r["ok"]]
    if fails:
        print("실패:")
        for r in fails:
            bits = []
            if not r["extract_ok"]:
                bits.append("추출:" + "; ".join(r["extract_why"]))
            if not r["route_ok"]:
                bits.append("라우트:" + "; ".join(r["route_why"]))
            if r["ask_ok"] is False:
                bits.append("엔진:" + "; ".join(r["ask_why"]))
            print(f" - {r['id']} {r['q']}: {' | '.join(bits)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
