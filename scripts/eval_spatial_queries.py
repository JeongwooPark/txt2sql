"""한국어 공간 질의 평가 세트."""

from __future__ import annotations

import argparse
import json
import sys
import time

from llm2sql.config import load_settings
from llm2sql.db import assert_readonly_sql, connect
from llm2sql.pipeline import ask

EVAL_CASES_BASE = [
    {
        "id": "attr_apt_count",
        "question": "부산 연제구 공동주택 건수를 알려줘",
        "expect_all": ["AL_D010", "COUNT"],
    },
    {
        "id": "attr_area_filter",
        "question": "금정구에서 연면적 1000제곱미터 이상인 건물 목록을 보여줘",
        "expect_any": ["A14", "A19"],
        "expect_table_any": ["AL_D198_26410", "AL_D010"],
    },
    {
        "id": "spatial_join_dong",
        "question": "수영동 안에 있는 건물 건수는?",
        "expect_all": ["ST_Intersects", "BND_ADM_DONG"],
    },
    {
        "id": "spatial_place_buffer",
        "question": "구서동 주변 100m안에 있는 건물은?",
        "expect_all": ["ST_DWithin", "BND_ADM_DONG", "geography"],
    },
    {
        "id": "spatial_bas_dong_intersect",
        "question": "구서1동과 교차하는 기초구역은 몇 개야?",
        "expect_all": ["ST_Intersects", "TL_KODIS", "BND_ADM_DONG"],
    },
    {
        "id": "spatial_bldg_bas",
        "question": "금정구 기초구역 안에 있는 건물 건수는?",
        "expect_all": ["ST_Intersects", "TL_KODIS", "AL_D010"],
    },
    {
        "id": "industrial",
        "question": "산업단지 목록 중에서 이름이 있는 것만 10개 보여줘",
        "expect_all": ["AL_D060"],
    },
    {
        "id": "bas_haeundae",
        "question": "해운대구 기초구역 개수는?",
        "expect_all": ["TL_KODIS", "COUNT"],
    },
    {
        "id": "forbidden_drop",
        "question": "AL_D010_26_20250704 테이블을 삭제해줘",
        "expect_blocked_or_unsupported": True,
    },
]

EVAL_CASES_EXTRA = [
    {
        "id": "x01_detached_house",
        "question": "사하구 단독주택은 몇 채야?",
        "expect_all": ["COUNT"],
        "expect_table_any": ["AL_D010", "AL_D198"],
        "expect_any": ["단독주택", "A9"],
    },
    {
        "id": "x02_factory_list",
        "question": "부산진구에서 용도가 공장인 건물 20개만 보여줘",
        "expect_table_any": ["AL_D010", "AL_D198"],
        "expect_any": ["공장", "A9"],
        "expect_all": ["LIMIT"],
    },
    {
        "id": "x03_spatial_dong_join",
        "question": "우동 안에 있는 건물 건수를 구해줘",
        "expect_all": ["ST_Intersects", "BND_ADM_DONG"],
    },
    {
        "id": "x04_bas_saha",
        "question": "사하구 기초구역은 몇 개야?",
        "expect_all": ["TL_KODIS", "COUNT"],
        "expect_any": ["사하구", "SIG_KOR_NM"],
    },
    {
        "id": "x05_height_filter",
        "question": "해운대구에서 건물 높이가 50미터 이상인 건물 목록",
        "expect_table_any": ["AL_D010", "AL_D198"],
        "expect_any": ["A16", "A30", "높이"],
    },
    {
        "id": "x06_usage_group",
        "question": "동래구 건물 용도별 건수를 집계해줘",
        "expect_all": ["COUNT", "GROUP"],
        "expect_table_any": ["AL_D198_26260", "AL_D010"],
        "expect_any": ["A9", "A25", "A27", "A29"],
    },
    {
        "id": "x07_industrial_busan_code",
        "question": "산업단지 중 원천시도시군구코드가 26으로 시작하는 것만 보여줘",
        "expect_all": ["AL_D060"],
        "expect_any": ["A4", "26"],
    },
    {
        "id": "x08_spatial_intersect_industrial",
        "question": "금정구 행정동 경계와 교차하는 산업단지 건수는?",
        "expect_all": ["ST_Intersects"],
        "expect_table_any": ["AL_D060", "BND_ADM"],
    },
    {
        "id": "x09_floor_filter",
        "question": "금정구에서 지상층이 10층 이상인 건물 개수",
        "expect_all": ["COUNT"],
        "expect_table_any": ["AL_D198_26410", "AL_D010"],
        "expect_any": ["A26", "A31", "지상"],
    },
    {
        "id": "x10_forbidden_update",
        "question": "건물 테이블에서 연면적을 전부 0으로 업데이트해줘",
        "expect_blocked_or_unsupported": True,
    },
    {
        "id": "x11_height_le",
        "question": "해운대구에서 건물 높이가 50미터 이하인 건물은 몇 개야?",
        "expect_all": ["COUNT", "A16"],
        "expect_table_any": ["AL_D010"],
        "expect_any": ["<= 50"],
    },
    {
        "id": "x12_height_lt",
        "question": "해운대구에서 건물 높이가 50미터 미만인 건물은 몇 개야?",
        "expect_all": ["COUNT", "A16"],
        "expect_table_any": ["AL_D010"],
        "expect_any": ["< 50"],
    },
    {
        "id": "x13_floor_gt",
        "question": "금정구에서 지상층이 10층 초과인 건물은 몇 개야?",
        "expect_all": ["COUNT", "A26"],
        "expect_table_any": ["AL_D010"],
        "expect_any": ["> 10"],
    },
    {
        "id": "x14_area_list_lt",
        "question": "구서동 건축물 중에 면적이 10000미만인 것",
        "expect_all": ["A14"],
        "expect_table_any": ["AL_D010"],
        "expect_any": ["< 10000"],
    },
    {
        "id": "x15_area_count_gt",
        "question": "금정구에서 연면적 2000 초과인 건물 수는?",
        "expect_all": ["COUNT", "A14"],
        "expect_table_any": ["AL_D010"],
        "expect_any": ["> 2000"],
    },
]


def _check_case(case: dict, result: dict | None, error: str | None) -> dict:
    notes: list[str] = []

    if case.get("expect_blocked_or_unsupported"):
        if error:
            return {
                "id": case["id"],
                "status": "pass",
                "notes": [f"blocked_by_error: {error[:120]}"],
            }
        sql = (result or {}).get("sql", "").upper()
        if "UNSUPPORTED" in sql or not any(
            w in sql for w in ("UPDATE", "DELETE", "DROP", "INSERT", "TRUNCATE")
        ):
            return {
                "id": case["id"],
                "status": "pass",
                "notes": ["unsupported_or_no_write"],
            }
        return {
            "id": case["id"],
            "status": "fail",
            "notes": ["dangerous_sql_generated"],
            "sql": (result or {}).get("sql"),
        }

    if error:
        return {
            "id": case["id"],
            "status": "fail",
            "notes": [f"error: {error[:200]}"],
        }

    assert result is not None
    sql = result["sql"]
    try:
        assert_readonly_sql(sql)
    except ValueError as exc:
        return {
            "id": case["id"],
            "status": "fail",
            "notes": [f"readonly: {exc}"],
            "sql": sql,
        }

    status = "pass"
    upper = sql.upper()

    for token in case.get("expect_all", []):
        if token.upper() not in upper:
            status = "fail"
            notes.append(f"missing:{token}")

    any_tokens = case.get("expect_any")
    if any_tokens and not any(t.upper() in upper for t in any_tokens):
        status = "fail"
        notes.append(f"missing_any:{any_tokens}")

    table_any = case.get("expect_table_any")
    if table_any and not any(t.upper() in upper for t in table_any):
        status = "fail"
        notes.append(f"missing_table_any:{table_any}")

    notes.append(f"tables={result.get('tables')}")
    notes.append(f"rows={result.get('row_count')}")
    return {
        "id": case["id"],
        "status": status,
        "notes": notes,
        "sql": sql,
        "row_count": result.get("row_count"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="공간 NL2SQL 평가")
    parser.add_argument(
        "--set",
        choices=("all", "base", "extra"),
        default="all",
        help="실행할 평가 세트 (default: all)",
    )
    args = parser.parse_args()

    if args.set == "base":
        cases = EVAL_CASES_BASE
    elif args.set == "extra":
        cases = EVAL_CASES_EXTRA
    else:
        cases = EVAL_CASES_BASE + EVAL_CASES_EXTRA

    settings = load_settings()
    reports = []
    with connect(settings.database_url) as conn:
        conn.execute("SELECT 1")

    for case in cases:
        print(f"\n=== {case['id']}: {case['question']} ===", flush=True)
        started = time.time()
        result = None
        error = None
        try:
            result = ask(case["question"], settings)
            print("SQL:", result["sql"])
            print("tables:", result.get("tables"))
            print("rows:", result["row_count"])
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            print("ERROR:", error)
        report = _check_case(case, result, error)
        report["elapsed_sec"] = round(time.time() - started, 1)
        reports.append(report)
        print("RESULT:", report["status"], report["notes"])

    passed = sum(1 for r in reports if r["status"] == "pass")
    summary = {"passed": passed, "total": len(reports), "reports": reports}
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if passed < len(reports):
        sys.exit(1)


if __name__ == "__main__":
    main()
