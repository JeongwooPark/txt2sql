"""정답(GT) 기반 평가: 10문항 × N회 반복.

각 문항은 검증된 SQL로 구한 스칼라 정답을 가지며,
모델이 생성·실행한 결과 값과 비교한다.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm2sql.config import load_settings
from llm2sql.db import connect
from llm2sql.pipeline import ask

# 정답 SQL은 벤치마크 채점용. 모델에게는 질문만 전달한다.
GT_CASES: list[dict[str, Any]] = [
    {
        "id": "gt01_saha_detached",
        "question": "사하구 단독주택은 몇 채야?",
        "expected": 13623,
        "gold_sql": (
            'SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704" '
            "WHERE \"A4\" LIKE '%사하구%' AND \"A9\" = '단독주택'"
        ),
        "expect_tables_any": ["AL_D010"],
        "tags": ["attr", "count", "usage"],
    },
    {
        "id": "gt02_jin_factory",
        "question": "부산진구에서 용도가 공장인 건물은 몇 개야?",
        "expected": 150,
        "gold_sql": (
            'SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704" '
            "WHERE \"A4\" LIKE '%부산진구%' AND \"A9\" = '공장'"
        ),
        "expect_tables_any": ["AL_D010"],
        "tags": ["attr", "count", "usage"],
    },
    {
        "id": "gt03_u1dong_spatial",
        "question": "우1동 안에 있는 건물 건수는?",
        "expected": 3381,
        "gold_sql": (
            'SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704" b '
            'JOIN "BND_ADM_DONG_PG" d ON ST_Intersects(b.geometry, d.geometry) '
            "WHERE d.\"ADM_NM\" LIKE '%우1동%'"
        ),
        "expect_sql_all": ["ST_Intersects", "BND_ADM_DONG"],
        "tags": ["spatial", "count"],
    },
    {
        "id": "gt04_saha_bas",
        "question": "사하구 기초구역은 몇 개야?",
        "expected": 228,
        "gold_sql": (
            'SELECT COUNT(*)::int AS v FROM "TL_KODIS_BAS_26_202507" '
            "WHERE \"SIG_KOR_NM\" = '사하구'"
        ),
        "expect_tables_any": ["TL_KODIS"],
        "tags": ["attr", "count", "bas"],
    },
    {
        "id": "gt05_haeundae_height",
        "question": "해운대구에서 건물 높이가 50미터 이상인 건물은 몇 개야?",
        "expected": 805,
        "gold_sql": (
            'SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704" '
            'WHERE "A4" LIKE \'%해운대구%\' AND "A16" >= 50'
        ),
        "expect_tables_any": ["AL_D010"],
        "expect_sql_any": ["A16"],
        "tags": ["attr", "count", "height"],
    },
    {
        "id": "gt06_dongrae_usage_kinds",
        "question": "동래구 건물의 주요용도명 종류는 몇 가지야?",
        "expected": 29,
        "gold_sql": (
            'SELECT COUNT(DISTINCT "A25")::int AS v FROM "AL_D198_26260_20250115" '
            "WHERE \"A4\" LIKE '%동래구%' AND \"A25\" IS NOT NULL"
        ),
        "expect_tables_any": ["AL_D198_26260"],
        "tags": ["attr", "count", "distinct", "usage"],
    },
    {
        "id": "gt07_industrial_code26",
        "question": "산업단지 중 원천시도시군구코드가 26으로 시작하는 것은 몇 개야?",
        "expected": 130,
        "gold_sql": (
            'SELECT COUNT(*)::int AS v FROM "AL_D060_00_20250804" '
            "WHERE \"A4\" LIKE '26%'"
        ),
        "expect_tables_any": ["AL_D060"],
        "tags": ["attr", "count", "industrial"],
    },
    {
        "id": "gt08_saha_ind_spatial",
        "question": "사하구 기초구역과 교차하는 산업단지는 몇 개야?",
        "expected": 93,
        "gold_sql": (
            'SELECT COUNT(DISTINCT i."A0")::int AS v '
            'FROM "AL_D060_00_20250804" i '
            'JOIN "TL_KODIS_BAS_26_202507" t ON ST_Intersects(i.geometry, t.geometry) '
            "WHERE t.\"SIG_KOR_NM\" = '사하구'"
        ),
        "expect_sql_all": ["ST_Intersects", "AL_D060", "TL_KODIS"],
        "tags": ["spatial", "count", "industrial"],
    },
    {
        "id": "gt09_geumjeong_floors",
        "question": "금정구에서 지상층이 10층 이상인 건물은 몇 개야?",
        "expected": 546,
        "gold_sql": (
            'SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704" '
            'WHERE "A4" LIKE \'%금정구%\' AND "A26" >= 10'
        ),
        "expect_tables_any": ["AL_D010", "AL_D198_26410"],
        "tags": ["attr", "count", "floors"],
    },
    {
        "id": "gt10_yeonje_apt",
        "question": "연제구 공동주택은 몇 채야?",
        "expected": 1824,
        "gold_sql": (
            'SELECT COUNT(*)::int AS v FROM "AL_D010_26_20250704" '
            "WHERE \"A4\" LIKE '%연제구%' AND \"A9\" = '공동주택'"
        ),
        "expect_tables_any": ["AL_D010"],
        "tags": ["attr", "count", "usage"],
    },
]


def extract_scalar(rows: list[dict[str, Any]]) -> int | None:
    if not rows:
        return None
    row = rows[0]
    for value in row.values():
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
            return int(value.strip())
    return None


def verify_gold(conn) -> None:
    for case in GT_CASES:
        got = conn.execute(case["gold_sql"]).fetchone()["v"]
        if int(got) != int(case["expected"]):
            raise RuntimeError(
                f"GT drift {case['id']}: expected {case['expected']} got {got}"
            )


def score_case(case: dict[str, Any], result: dict[str, Any] | None, error: str | None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": case["id"],
        "question": case["question"],
        "expected": case["expected"],
        "exec_ok": False,
        "value_match": False,
        "pattern_ok": True,
        "got_value": None,
        "sql": None,
        "error": error,
        "fail_reasons": [],
    }
    if error or result is None:
        out["fail_reasons"].append("exec_error")
        return out

    out["exec_ok"] = True
    out["sql"] = result.get("sql")
    sql = (result.get("sql") or "").upper()
    got = extract_scalar(result.get("rows") or [])
    out["got_value"] = got
    out["value_match"] = got == case["expected"]
    if not out["value_match"]:
        out["fail_reasons"].append("value_mismatch")

    for token in case.get("expect_sql_all", []):
        if token.upper() not in sql:
            out["pattern_ok"] = False
            out["fail_reasons"].append(f"missing:{token}")
    any_sql = case.get("expect_sql_any")
    if any_sql and not any(t.upper() in sql for t in any_sql):
        out["pattern_ok"] = False
        out["fail_reasons"].append(f"missing_any:{any_sql}")
    tables_any = case.get("expect_tables_any")
    if tables_any and not any(t.upper() in sql for t in tables_any):
        out["pattern_ok"] = False
        out["fail_reasons"].append(f"missing_table:{tables_any}")

    # 최종 성공: 실행 성공 + 정답 값 일치
    out["pass"] = bool(out["exec_ok"] and out["value_match"])
    return out


def classify_sql_issue(sql: str | None, case_id: str) -> str:
    if not sql:
        return "no_sql"
    s = sql.upper()
    if "UPDATE" in s or "DELETE" in s or "DROP" in s:
        return "write_attempt"
    if case_id.startswith("gt03") or case_id.startswith("gt08"):
        if "ST_INTERSECTS" not in s:
            return "missing_spatial"
    if '"A3"' in sql and "LIKE" in s and any(
        x in case_id for x in ("saha", "jin", "haeundae", "yeonje", "geumjeong")
    ):
        return "wrong_district_col_A3"
    if "AL_D198" in s and case_id in {
        "gt01_saha_detached",
        "gt02_jin_factory",
        "gt05_haeundae_height",
        "gt10_yeonje_apt",
    }:
        return "wrong_building_table_D198"
    if "AL_D060" not in s and "industrial" in case_id:
        return "wrong_industrial_table"
    if "A16" not in sql and case_id.startswith("gt05"):
        return "wrong_height_col"
    return "semantic_or_other"


def run_rounds(rounds: int, out_path: Path) -> dict[str, Any]:
    settings = load_settings()
    with connect(settings.database_url) as conn:
        verify_gold(conn)

    all_rounds: list[dict[str, Any]] = []
    for r in range(1, rounds + 1):
        print(f"\n######## ROUND {r}/{rounds} ########", flush=True)
        round_reports = []
        for case in GT_CASES:
            print(f"\n--- [{r}] {case['id']}: {case['question']} ---", flush=True)
            t0 = time.time()
            result = None
            error = None
            try:
                result = ask(case["question"], settings)
                print("SQL:", result["sql"])
                print("rows:", result["row_count"], "sample:", (result["rows"] or [])[:1])
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                print("ERROR:", error)
            scored = score_case(case, result, error)
            scored["elapsed_sec"] = round(time.time() - t0, 1)
            scored["issue"] = classify_sql_issue(scored.get("sql"), case["id"])
            scored["round"] = r
            round_reports.append(scored)
            print(
                f"PASS={scored['pass']} got={scored['got_value']} "
                f"expected={scored['expected']} issue={scored['issue']}",
                flush=True,
            )
        passed = sum(1 for x in round_reports if x["pass"])
        all_rounds.append(
            {
                "round": r,
                "passed": passed,
                "total": len(round_reports),
                "reports": round_reports,
            }
        )
        # 중간 저장
        payload = build_summary(all_rounds)
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"ROUND {r} SCORE: {passed}/{len(round_reports)}", flush=True)

    return build_summary(all_rounds)


def build_summary(all_rounds: list[dict[str, Any]]) -> dict[str, Any]:
    per_case: dict[str, dict[str, Any]] = {}
    issue_counter: Counter[str] = Counter()
    for rnd in all_rounds:
        for rep in rnd["reports"]:
            cid = rep["id"]
            slot = per_case.setdefault(
                cid,
                {
                    "id": cid,
                    "question": rep["question"],
                    "expected": rep["expected"],
                    "passes": 0,
                    "exec_ok": 0,
                    "value_match": 0,
                    "runs": 0,
                    "issues": Counter(),
                    "got_values": [],
                    "sample_fail_sql": None,
                },
            )
            slot["runs"] += 1
            slot["passes"] += int(rep["pass"])
            slot["exec_ok"] += int(rep["exec_ok"])
            slot["value_match"] += int(rep["value_match"])
            slot["issues"][rep["issue"]] += 1
            issue_counter[rep["issue"]] += 1
            if rep["got_value"] is not None:
                slot["got_values"].append(rep["got_value"])
            if not rep["pass"] and slot["sample_fail_sql"] is None:
                slot["sample_fail_sql"] = rep.get("sql") or rep.get("error")

    per_case_out = []
    for cid, slot in per_case.items():
        runs = slot["runs"] or 1
        per_case_out.append(
            {
                "id": cid,
                "question": slot["question"],
                "expected": slot["expected"],
                "pass_rate": round(slot["passes"] / runs, 3),
                "exec_ok_rate": round(slot["exec_ok"] / runs, 3),
                "value_match_rate": round(slot["value_match"] / runs, 3),
                "issues": dict(slot["issues"]),
                "got_value_histogram": dict(Counter(slot["got_values"])),
                "sample_fail_sql": slot["sample_fail_sql"],
            }
        )

    round_scores = [
        {"round": r["round"], "passed": r["passed"], "total": r["total"]}
        for r in all_rounds
    ]
    total_pass = sum(r["passed"] for r in all_rounds)
    total_n = sum(r["total"] for r in all_rounds)

    # 수정 방향 초안 (데이터 기반)
    weak = sorted(per_case_out, key=lambda x: x["pass_rate"])
    directions: list[str] = []
    if issue_counter.get("wrong_district_col_A3", 0) > 0:
        directions.append(
            "법정동/구 필터는 A4(법정동명)만 허용하도록 컬럼 라우팅 규칙을 강제한다."
        )
    if issue_counter.get("missing_spatial", 0) > 0:
        directions.append(
            "공간 의도(안에/교차)면 ST_Intersects 템플릿을 LLM보다 우선 적용한다."
        )
    if issue_counter.get("wrong_building_table_D198", 0) > 0:
        directions.append(
            "부산 전역·구 단위 속성질의는 AL_D010을 기본 테이블로 고정한다."
        )
    if issue_counter.get("wrong_height_col", 0) > 0:
        directions.append(
            "높이/층수 슬롯을 테이블별로 매핑(A16/A26 vs A30/A31)하는 슬롯필러를 둔다."
        )
    if issue_counter.get("wrong_industrial_table", 0) > 0:
        directions.append(
            "산업단지 질의는 AL_D060(+필요시 TL_KODIS)만 스키마에 남긴다."
        )
    if any(x["pass_rate"] < 0.5 for x in weak[:3]):
        directions.append(
            "고빈도 패턴(구+용도 COUNT, 동 공간 COUNT, 기초구역 COUNT)은 "
            "규칙 기반 슬롯 채우기로 우회하고, LLM은 잔여 질의에만 사용한다."
        )
    if not directions:
        directions.append(
            "정답률이 안정적이면 few-shot 예제 강화와 결과검증(재생성) 루프를 추가한다."
        )

    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rounds": len(all_rounds),
        "overall_pass_rate": round(total_pass / total_n, 3) if total_n else 0,
        "overall_passed": total_pass,
        "overall_total": total_n,
        "round_scores": round_scores,
        "issue_counts": dict(issue_counter),
        "per_case": per_case_out,
        "recommended_directions": directions,
        "rounds_detail": all_rounds,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument(
        "--out",
        default="benchmark_gt10_results.json",
        help="결과 JSON 경로",
    )
    args = parser.parse_args()
    out_path = Path(args.out)
    summary = run_rounds(args.rounds, out_path)
    print("\n=== OVERALL ===")
    print(
        json.dumps(
            {
                "overall_pass_rate": summary["overall_pass_rate"],
                "round_scores": summary["round_scores"],
                "issue_counts": summary["issue_counts"],
                "per_case": [
                    {
                        "id": c["id"],
                        "pass_rate": c["pass_rate"],
                        "issues": c["issues"],
                    }
                    for c in summary["per_case"]
                ],
                "recommended_directions": summary["recommended_directions"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"saved: {out_path}")


if __name__ == "__main__":
    main()
