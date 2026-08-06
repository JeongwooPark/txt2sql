"""5라운드 × 서로 다른 10문항 GT 벤치마크.

각 라운드마다 질문 문장을 바꾸고, SQL 실행 결과 스칼라를 정답과 비교한다.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm2sql.config import load_settings
from llm2sql.db import connect
from llm2sql.pipeline import ask

# 라운드마다 문장·정답이 다름 (금 SQL로 검증)
ROUNDS: list[list[dict[str, Any]]] = [
    # ---- Round 1 ----
    [
        {
            "id": "r1_01",
            "question": "사상구 단독주택은 몇 채야?",
            "expected": 8246,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%사상구%' AND "A9"='단독주택'""",
        },
        {
            "id": "r1_02",
            "question": "남구에서 용도가 공장인 건물 개수는?",
            "expected": 161,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%남구%' AND "A9"='공장'""",
        },
        {
            "id": "r1_03",
            "question": "우2동 안에 있는 건물 건수는?",
            "expected": 2246,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704" b
JOIN "BND_ADM_DONG_PG" d ON ST_Intersects(b.geometry,d.geometry)
WHERE d."ADM_NM"='우2동'""",
        },
        {
            "id": "r1_04",
            "question": "기장군 기초구역은 몇 개야?",
            "expected": 85,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "TL_KODIS_BAS_26_202507"
WHERE "SIG_KOR_NM"='기장군'""",
        },
        {
            "id": "r1_05",
            "question": "북구에서 건물 높이가 40미터 이상인 건물은 몇 개야?",
            "expected": 566,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%북구%' AND "A16">=40""",
        },
        {
            "id": "r1_06",
            "question": "영도구에서 지상층이 8층 이상인 건물 수는?",
            "expected": 284,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%영도구%' AND "A26">=8""",
        },
        {
            "id": "r1_07",
            "question": "강서구 기초구역과 교차하는 산업단지는 몇 개야?",
            "expected": 17,
            "gold_sql": """SELECT COUNT(DISTINCT i."A0")::int AS v FROM "AL_D060_00_20250804" i
JOIN "TL_KODIS_BAS_26_202507" t ON ST_Intersects(i.geometry,t.geometry)
WHERE t."SIG_KOR_NM"='강서구'""",
        },
        {
            "id": "r1_08",
            "question": "산업단지 중 원천시도시군구코드가 26으로 시작하는 것은 몇 개야?",
            "expected": 130,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D060_00_20250804" WHERE "A4" LIKE '26%'""",
        },
        {
            "id": "r1_09",
            "question": "연제구 연면적 상위 1개 건물의 연면적 값은?",
            "expected": 131571.75,
            "gold_sql": """SELECT "A14"::float AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%연제구%' ORDER BY "A14" DESC NULLS LAST LIMIT 1""",
            "tolerance": 0.01,
        },
        {
            "id": "r1_10",
            "question": "좌표 129.075, 35.179 근처 200미터 이내 건물 건수",
            "expected": 130,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704" b
WHERE ST_DWithin(b.geometry::geography,
ST_SetSRID(ST_MakePoint(129.075,35.179),4326)::geography, 200)""",
        },
    ],
    # ---- Round 2 (문장 변경) ----
    [
        {
            "id": "r2_01",
            "question": "동래구에 있는 공동주택 채수를 알려줘",
            "expected": 2406,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%동래구%' AND "A9"='공동주택'""",
        },
        {
            "id": "r2_02",
            "question": "사상구 창고시설 건물 개수가 궁금해",
            "expected": 528,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%사상구%' AND "A9"='창고시설'""",
        },
        {
            "id": "r2_03",
            "question": "감전동 내부의 건물 건수를 구해줘",
            "expected": 5234,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704" b
JOIN "BND_ADM_DONG_PG" d ON ST_Intersects(b.geometry,d.geometry)
WHERE d."ADM_NM"='감전동'""",
        },
        {
            "id": "r2_04",
            "question": "수영구의 기초구역 개수는 얼마야?",
            "expected": 119,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "TL_KODIS_BAS_26_202507"
WHERE "SIG_KOR_NM"='수영구'""",
        },
        {
            "id": "r2_05",
            "question": "부산진구 건물 중 높이 60미터 이상은 몇 개?",
            "expected": 332,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%부산진구%' AND "A16">=60""",
        },
        {
            "id": "r2_06",
            "question": "해운대구 지상 15층 이상 건물 건수 알려줘",
            "expected": 961,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%해운대구%' AND "A26">=15""",
        },
        {
            "id": "r2_07",
            "question": "사하구 교육연구시설은 몇 동이야?",
            "expected": 263,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%사하구%' AND "A9"='교육연구시설'""",
        },
        {
            "id": "r2_08",
            "question": "금정구에서 연면적 2000 이상인 건물 수는?",
            "expected": 1068,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%금정구%' AND "A14">=2000""",
        },
        {
            "id": "r2_09",
            "question": "수영구 기초구역을 면적 큰 순 1개만, 면적값",
            "expected": 0.496155,
            "gold_sql": """SELECT "BAS_AR"::float AS v FROM "TL_KODIS_BAS_26_202507"
WHERE "SIG_KOR_NM"='수영구' ORDER BY "BAS_AR" DESC NULLS LAST LIMIT 1""",
            "tolerance": 1e-6,
        },
        {
            "id": "r2_10",
            "question": "좌1동 안에 건물 몇 개 있어?",
            "expected": 545,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704" b
JOIN "BND_ADM_DONG_PG" d ON ST_Intersects(b.geometry,d.geometry)
WHERE d."ADM_NM" LIKE '%좌1동%'""",
        },
    ],
    # ---- Round 3 ----
    [
        {
            "id": "r3_01",
            "question": "연제구 공동주택 건수를 세어줘",
            "expected": 1824,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%연제구%' AND "A9"='공동주택'""",
        },
        {
            "id": "r3_02",
            "question": "금정구 주요용도명 종류는 몇 가지야?",
            "expected": 28,
            "gold_sql": """SELECT COUNT(DISTINCT "A25")::int AS v FROM "AL_D198_26410_20250115"
WHERE "A4" LIKE '%금정구%' AND "A25" IS NOT NULL""",
        },
        {
            "id": "r3_03",
            "question": "학장동 경계 안 건물 건수",
            "expected": 4489,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704" b
JOIN "BND_ADM_DONG_PG" d ON ST_Intersects(b.geometry,d.geometry)
WHERE d."ADM_NM"='학장동'""",
        },
        {
            "id": "r3_04",
            "question": "중구 기초구역 개수 알려줘",
            "expected": 85,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "TL_KODIS_BAS_26_202507"
WHERE "SIG_KOR_NM"='중구'""",
        },
        {
            "id": "r3_05",
            "question": "사하구 높이 50미터 이상 건물 개수",
            "expected": 288,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%사하구%' AND "A16">=50""",
        },
        {
            "id": "r3_06",
            "question": "사상구 지상층 10층 이상 건물은?",
            "expected": 201,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%사상구%' AND "A26">=10""",
        },
        {
            "id": "r3_07",
            "question": "해운대구 기초구역과 교차하는 산업단지 개수",
            "expected": 5,
            "gold_sql": """SELECT COUNT(DISTINCT i."A0")::int AS v FROM "AL_D060_00_20250804" i
JOIN "TL_KODIS_BAS_26_202507" t ON ST_Intersects(i.geometry,t.geometry)
WHERE t."SIG_KOR_NM"='해운대구'""",
        },
        {
            "id": "r3_08",
            "question": "부산진구 공장 건물 몇 개?",
            "expected": 150,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%부산진구%' AND "A9"='공장'""",
        },
        {
            "id": "r3_09",
            "question": "금정구 연면적 상위 3개 중 가장 큰 연면적",
            "expected": None,  # filled at verify from gold
            "gold_sql": """SELECT "A14"::float AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%금정구%' ORDER BY "A14" DESC NULLS LAST LIMIT 1""",
            "tolerance": 0.01,
        },
        {
            "id": "r3_10",
            "question": "점(129.08 35.16)에서 500미터 이내 건물 수",
            "expected": None,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704" b
WHERE ST_DWithin(b.geometry::geography,
ST_SetSRID(ST_MakePoint(129.08,35.16),4326)::geography, 500)""",
        },
    ],
    # ---- Round 4 ----
    [
        {
            "id": "r4_01",
            "question": "북구 단독주택 채수 구해줘",
            "expected": None,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%북구%' AND "A9"='단독주택'""",
        },
        {
            "id": "r4_02",
            "question": "기장군에서 공동주택은 몇 채?",
            "expected": None,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%기장군%' AND "A9"='공동주택'""",
        },
        {
            "id": "r4_03",
            "question": "남산동 안에 있는 건물 건수 알려줘",
            "expected": 4028,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704" b
JOIN "BND_ADM_DONG_PG" d ON ST_Intersects(b.geometry,d.geometry)
WHERE d."ADM_NM"='남산동'""",
        },
        {
            "id": "r4_04",
            "question": "연제구 기초구역 개수는?",
            "expected": 116,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "TL_KODIS_BAS_26_202507"
WHERE "SIG_KOR_NM"='연제구'""",
        },
        {
            "id": "r4_05",
            "question": "동래구 높이 30미터 이상 건물 건수",
            "expected": None,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%동래구%' AND "A16">=30""",
        },
        {
            "id": "r4_06",
            "question": "금정구 지상층 5층 이상 건물 개수",
            "expected": None,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%금정구%' AND "A26">=5""",
        },
        {
            "id": "r4_07",
            "question": "사상구 기초구역과 교차하는 산업단지 수",
            "expected": 2,
            "gold_sql": """SELECT COUNT(DISTINCT i."A0")::int AS v FROM "AL_D060_00_20250804" i
JOIN "TL_KODIS_BAS_26_202507" t ON ST_Intersects(i.geometry,t.geometry)
WHERE t."SIG_KOR_NM"='사상구'""",
        },
        {
            "id": "r4_08",
            "question": "남구 연면적 상위 5개 중 1등의 연면적",
            "expected": None,
            "gold_sql": """SELECT "A14"::float AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%남구%' ORDER BY "A14" DESC NULLS LAST LIMIT 1""",
            "tolerance": 0.01,
        },
        {
            "id": "r4_09",
            "question": "동래구 건물의 주요용도명 종류 수",
            "expected": 29,
            "gold_sql": """SELECT COUNT(DISTINCT "A25")::int AS v FROM "AL_D198_26260_20250115"
WHERE "A4" LIKE '%동래구%' AND "A25" IS NOT NULL""",
        },
        {
            "id": "r4_10",
            "question": "코드가 26으로 시작하는 산업단지 건수",
            "expected": 130,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D060_00_20250804" WHERE "A4" LIKE '26%'""",
        },
    ],
    # ---- Round 5 ----
    [
        {
            "id": "r5_01",
            "question": "해운대구 단독주택은 몇 채인가?",
            "expected": None,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%해운대구%' AND "A9"='단독주택'""",
        },
        {
            "id": "r5_02",
            "question": "영도구 공장 건물 개수를 조회해줘",
            "expected": None,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%영도구%' AND "A9"='공장'""",
        },
        {
            "id": "r5_03",
            "question": "범천2동 안쪽 건물 건수는 얼마야?",
            "expected": 4647,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704" b
JOIN "BND_ADM_DONG_PG" d ON ST_Intersects(b.geometry,d.geometry)
WHERE d."ADM_NM"='범천2동'""",
        },
        {
            "id": "r5_04",
            "question": "강서구 기초구역은 총 몇 개?",
            "expected": 74,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "TL_KODIS_BAS_26_202507"
WHERE "SIG_KOR_NM"='강서구'""",
        },
        {
            "id": "r5_05",
            "question": "수영구에서 높이 45미터 넘는 건물 수",
            "expected": 175,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%수영구%' AND "A16">45""",
        },
        {
            "id": "r5_06",
            "question": "연제구 지상 12층 이상 건물 건수",
            "expected": None,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%연제구%' AND "A26">=12""",
        },
        {
            "id": "r5_07",
            "question": "금정구 기초구역과 교차하는 산업단지 몇 개?",
            "expected": 1,
            "gold_sql": """SELECT COUNT(DISTINCT i."A0")::int AS v FROM "AL_D060_00_20250804" i
JOIN "TL_KODIS_BAS_26_202507" t ON ST_Intersects(i.geometry,t.geometry)
WHERE t."SIG_KOR_NM"='금정구'""",
        },
        {
            "id": "r5_08",
            "question": "사하구 연면적 가장 큰 건물 연면적",
            "expected": None,
            "gold_sql": """SELECT "A14"::float AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%사하구%' ORDER BY "A14" DESC NULLS LAST LIMIT 1""",
            "tolerance": 0.01,
        },
        {
            "id": "r5_09",
            "question": "북구 창고시설 건물은 몇 개?",
            "expected": None,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%북구%' AND "A9"='창고시설'""",
        },
        {
            "id": "r5_10",
            "question": "129.1, 35.2 좌표 기준 400미터 이내 건물 건수",
            "expected": None,
            "gold_sql": """SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704" b
WHERE ST_DWithin(b.geometry::geography,
ST_SetSRID(ST_MakePoint(129.1,35.2),4326)::geography, 400)""",
        },
    ],
]


def extract_scalar(rows: list[dict[str, Any]]) -> float | int | None:
    if not rows:
        return None
    row = rows[0]
    # 면적/수치 컬럼 우선
    for key in ("v", "cnt", "BAS_AR", "A14", "count", "CNT"):
        if key in row and isinstance(row[key], (int, float)):
            return row[key]
    for value in row.values():
        if isinstance(value, bool):
            continue
        if isinstance(value, float):
            return value
        if isinstance(value, int):
            return value
        if isinstance(value, str) and re.fullmatch(r"-?\d+(\.\d+)?", value.strip()):
            return float(value) if "." in value else int(value)
    return None


def values_equal(got: Any, expected: Any, tolerance: float | None) -> bool:
    if got is None or expected is None:
        return False
    if tolerance is not None:
        try:
            return abs(float(got) - float(expected)) <= tolerance
        except (TypeError, ValueError):
            return False
    return got == expected


def fill_expected_from_db(conn) -> None:
    for cases in ROUNDS:
        for case in cases:
            v = conn.execute(case["gold_sql"]).fetchone()["v"]
            case["expected"] = v


def classify_issue(question: str, sql: str | None, got: Any, expected: Any) -> str:
    if not sql:
        return "exec_error"
    s = sql.upper()
    if "A3" in sql and "LIKE" in s and re.search(r"[가-힣]+구", question):
        return "wrong_col_A3"
    if "AL_D198" in s and "AL_D010" not in s and "금정" not in question and "동래" not in question:
        if "건물" in question or "주택" in question:
            return "wrong_table_D198"
    if any(k in question for k in ("안에", "내부", "안쪽", "경계 안")) and "ST_INTERSECTS" not in s:
        return "missing_spatial"
    if "미터" in question and ("ST_DWITHIN" not in s or "GEOGRAPHY" not in s):
        return "bad_buffer"
    if "기초구역" in question and "산업단지" in question and "TL_KODIS" not in s:
        return "bad_ind_bas_join"
    if got is not None and expected is not None and got != expected:
        return "value_mismatch"
    return "other"


def run(out_path: Path) -> dict[str, Any]:
    settings = load_settings()
    with connect(settings.database_url) as conn:
        fill_expected_from_db(conn)

    all_reports: list[dict[str, Any]] = []
    round_summaries: list[dict[str, Any]] = []

    for ri, cases in enumerate(ROUNDS, start=1):
        print(f"\n######## ROUND {ri}/5 ########", flush=True)
        reports = []
        for case in cases:
            print(f"\n--- {case['id']}: {case['question']} ---", flush=True)
            print(f"EXPECTED: {case['expected']}", flush=True)
            t0 = time.time()
            result = None
            error = None
            try:
                result = ask(case["question"], settings)
                print("SQL:", result["sql"])
                print("route:", result.get("route"))
                print("rows:", result["row_count"], (result["rows"] or [])[:2])
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                print("ERROR:", error)

            got = extract_scalar(result["rows"]) if result else None
            tol = case.get("tolerance")
            ok = error is None and values_equal(got, case["expected"], tol)
            issue = (
                "pass"
                if ok
                else classify_issue(
                    case["question"],
                    None if not result else result.get("sql"),
                    got,
                    case["expected"],
                )
            )
            if error:
                issue = "exec_error"
            rep = {
                "round": ri,
                "id": case["id"],
                "question": case["question"],
                "expected": case["expected"],
                "got": got,
                "pass": ok,
                "issue": issue if not ok else "pass",
                "sql": None if not result else result.get("sql"),
                "route": None if not result else result.get("route"),
                "error": error,
                "elapsed_sec": round(time.time() - t0, 1),
            }
            reports.append(rep)
            all_reports.append(rep)
            print(f"PASS={ok} got={got} issue={rep['issue']}", flush=True)

        passed = sum(1 for r in reports if r["pass"])
        round_summaries.append({"round": ri, "passed": passed, "total": len(reports)})
        payload = build_summary(round_summaries, all_reports)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"ROUND {ri} SCORE: {passed}/{len(reports)}", flush=True)

    return build_summary(round_summaries, all_reports)


def build_summary(
    round_summaries: list[dict[str, Any]],
    all_reports: list[dict[str, Any]],
) -> dict[str, Any]:
    fails = [r for r in all_reports if not r["pass"]]
    issue_counts = Counter(r["issue"] for r in fails)
    by_round_issue = {}
    for r in fails:
        by_round_issue.setdefault(r["round"], Counter())[r["issue"]] += 1

    directions: list[str] = []
    if issue_counts.get("wrong_col_A3"):
        directions.append("구/동 한글 필터 시 A3→A4 강제 및 라우터 커버리지 확대")
    if issue_counts.get("wrong_table_D198"):
        directions.append("구 단위 건물 질의는 AL_D010 고정 라우팅 강화")
    if issue_counts.get("missing_spatial"):
        directions.append("'안/내부/안쪽/경계 안' 표현을 공간 템플릿에 추가")
    if issue_counts.get("bad_buffer"):
        directions.append("좌표+미터 패턴 규칙 라우터 추가 (ST_DWithin geography)")
    if issue_counts.get("bad_ind_bas_join"):
        directions.append("기초구역∩산업단지 문장 변형 패턴 확장")
    if issue_counts.get("value_mismatch"):
        directions.append("동의어/문장변형으로 라우터 미매칭 시 LLM 검증 피드백 강화")
    if issue_counts.get("exec_error"):
        directions.append("식별자 인용·문법 오류 재생성 루프 강화")
    if not directions:
        directions.append("실패가 적어 라우터 문장변형 커버와 LLM few-shot만 소폭 보강")

    total_pass = sum(1 for r in all_reports if r["pass"])
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "overall_pass_rate": round(total_pass / len(all_reports), 3) if all_reports else 0,
        "overall_passed": total_pass,
        "overall_total": len(all_reports),
        "round_scores": round_summaries,
        "issue_counts": dict(issue_counts),
        "fail_cases": [
            {
                "id": f["id"],
                "round": f["round"],
                "question": f["question"],
                "expected": f["expected"],
                "got": f["got"],
                "issue": f["issue"],
                "sql": f["sql"],
                "route": f["route"],
                "error": f["error"],
            }
            for f in fails
        ],
        "recommended_directions": directions,
        "all_reports": all_reports,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="benchmark_5x10_results.json")
    args = parser.parse_args()
    out = Path(args.out)
    summary = run(out)
    print("\n=== OVERALL ===")
    print(
        json.dumps(
            {
                "overall_pass_rate": summary["overall_pass_rate"],
                "round_scores": summary["round_scores"],
                "issue_counts": summary["issue_counts"],
                "fail_count": len(summary["fail_cases"]),
                "recommended_directions": summary["recommended_directions"],
                "fail_cases": summary["fail_cases"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print("saved:", out)


if __name__ == "__main__":
    main()
