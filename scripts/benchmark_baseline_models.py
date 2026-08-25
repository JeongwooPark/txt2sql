"""Phase2: Baseline 모델 비교 (동일 Phase1 RAG SQL 파이프라인).

규칙 라우터를 우회하고 Schema RAG + 동적 few-shot + SQLGlot/EXPLAIN +
실행 재시도만으로 모델별 Syntax / Exec / Execution Accuracy를 비교한다.

기본 후보:
  - qwen3:latest          (한국어 주력)
  - qwen3.5:latest        (한국어 신형)
  - sqlcoder:7b           (SQL 전문 baseline)
  - gemma3:latest         (일반 LLM baseline)

CypressTree / OmniSQL은 Ollama에 없을 경우 자동 skip.
수동 등록 예: ollama create cypresstree -f Modelfile
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ollama

from txt2sql.config import load_settings
from txt2sql.db import connect
from txt2sql.rag_sql import run_rag_sql

# benchmark_gt10과 동일 GT (모델에게는 질문만 전달)
GT_CASES: list[dict[str, Any]] = [
    {
        "id": "gt01_saha_detached",
        "question": "사하구 단독주택은 몇 채야?",
        "expected": 13623,
        "difficulty": "easy",
        "expect_tables_any": ["AL_D010"],
        "tags": ["attr", "count", "usage"],
    },
    {
        "id": "gt02_jin_factory",
        "question": "부산진구에서 용도가 공장인 건물은 몇 개야?",
        "expected": 150,
        "difficulty": "easy",
        "expect_tables_any": ["AL_D010"],
        "tags": ["attr", "count", "usage"],
    },
    {
        "id": "gt03_u1dong_spatial",
        "question": "우1동 안에 있는 건물 건수는?",
        "expected": 3381,
        "difficulty": "medium",
        "expect_sql_all": ["ST_Intersects", "BND_ADM_DONG"],
        "tags": ["spatial", "count"],
    },
    {
        "id": "gt04_saha_bas",
        "question": "사하구 기초구역은 몇 개야?",
        "expected": 228,
        "difficulty": "easy",
        "expect_tables_any": ["TL_KODIS"],
        "tags": ["attr", "count", "bas"],
    },
    {
        "id": "gt05_haeundae_height",
        "question": "해운대구에서 건물 높이가 50미터 이상인 건물은 몇 개야?",
        "expected": 805,
        "difficulty": "medium",
        "expect_tables_any": ["AL_D010"],
        "expect_sql_any": ["A16"],
        "tags": ["attr", "count", "height"],
    },
    {
        "id": "gt06_dongrae_usage_kinds",
        "question": "동래구 건물의 주요용도명 종류는 몇 가지야?",
        "expected": 29,
        "difficulty": "medium",
        "expect_tables_any": ["AL_D198_26260"],
        "tags": ["attr", "count", "distinct", "usage"],
    },
    {
        "id": "gt07_industrial_code26",
        "question": "산업단지 중 원천시도시군구코드가 26으로 시작하는 것은 몇 개야?",
        "expected": 130,
        "difficulty": "easy",
        "expect_tables_any": ["AL_D060"],
        "tags": ["attr", "count", "industrial"],
    },
    {
        "id": "gt08_saha_ind_spatial",
        "question": "사하구 기초구역과 교차하는 산업단지는 몇 개야?",
        "expected": 93,
        "difficulty": "hard",
        "expect_sql_all": ["ST_Intersects", "AL_D060", "TL_KODIS"],
        "tags": ["spatial", "count", "industrial"],
    },
    {
        "id": "gt09_geumjeong_floors",
        "question": "금정구에서 지상층이 10층 이상인 건물은 몇 개야?",
        "expected": 546,
        "difficulty": "medium",
        "expect_tables_any": ["AL_D010", "AL_D198_26410"],
        "tags": ["attr", "count", "floors"],
    },
    {
        "id": "gt10_yeonje_apt",
        "question": "연제구 공동주택은 몇 채야?",
        "expected": 1824,
        "difficulty": "easy",
        "expect_tables_any": ["AL_D010"],
        "tags": ["attr", "count", "usage"],
    },
]

DEFAULT_MODELS = [
    "qwen3:latest",
    "qwen3.5:latest",
    "sqlcoder:7b",
    "gemma3:latest",
    # 로컬에 있으면 포함, 없으면 skip
    "cypresstree:latest",
    "omnisql:7b",
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


def check_syntax_valid(sql: str | None) -> bool:
    if not sql:
        return False
    try:
        import sqlglot

        sqlglot.parse_one(sql, read="postgres")
        return True
    except Exception:
        # sqlglot 없으면 SELECT/WITH 휴리스틱
        low = sql.strip().lower()
        return low.startswith("select") or low.startswith("with")


def list_local_models(host: str) -> set[str]:
    client = ollama.Client(host=host)
    payload = client.list()
    models = payload.get("models") if isinstance(payload, dict) else getattr(payload, "models", [])
    names: set[str] = set()
    for m in models or []:
        name = m.get("name") if isinstance(m, dict) else getattr(m, "model", None) or getattr(m, "name", None)
        if name:
            names.add(str(name))
            # tag 없는 별칭도 매칭
            if ":" in str(name):
                names.add(str(name).split(":", 1)[0])
    return names


def resolve_models(requested: list[str], local: set[str]) -> tuple[list[str], list[str]]:
    available: list[str] = []
    skipped: list[str] = []
    for model in requested:
        base = model.split(":", 1)[0]
        if model in local or base in local or any(n.startswith(base + ":") for n in local):
            # 정확한 태그 우선
            if model in local:
                available.append(model)
            else:
                # local에 있는 전체 이름 찾기
                match = next((n for n in local if n == model or n.startswith(base + ":")), model)
                available.append(match if match in local else model)
        else:
            skipped.append(model)
    # 중복 제거 유지 순서
    seen: set[str] = set()
    uniq: list[str] = []
    for m in available:
        if m not in seen:
            seen.add(m)
            uniq.append(m)
    return uniq, skipped


def score_case(case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    sql = result.get("sql")
    error = result.get("error")
    rows = result.get("rows") or []
    got = extract_scalar(rows)
    syntax_ok = check_syntax_valid(sql)
    exec_ok = bool(result.get("ok")) and error is None
    value_match = got == case["expected"]
    schema_ok = True
    upper = (sql or "").upper()
    for token in case.get("expect_sql_all", []):
        if token.upper() not in upper:
            schema_ok = False
    any_sql = case.get("expect_sql_any")
    if any_sql and not any(t.upper() in upper for t in any_sql):
        schema_ok = False
    tables_any = case.get("expect_tables_any")
    if tables_any and not any(t.upper() in upper for t in tables_any):
        schema_ok = False

    return {
        "id": case["id"],
        "question": case["question"],
        "difficulty": case.get("difficulty"),
        "expected": case["expected"],
        "got_value": got,
        "sql": sql,
        "error": error,
        "syntax_valid": syntax_ok,
        "exec_success": exec_ok,
        "execution_accuracy": bool(exec_ok and value_match),
        "schema_linking_ok": schema_ok,
        "retries": result.get("retries"),
        "diagnostics": result.get("diagnostics"),
    }


def evaluate_model(
    model: str,
    *,
    cases: list[dict[str, Any]],
) -> dict[str, Any]:
    base = load_settings()
    settings = base.with_overrides(ollama_model=model)
    reports: list[dict[str, Any]] = []
    client = ollama.Client(host=settings.ollama_host)

    print(f"\n======== MODEL: {model} ========", flush=True)
    with connect(settings.database_url) as conn:
        for case in cases:
            print(f"--- {case['id']}: {case['question']}", flush=True)
            t0 = time.time()
            result = run_rag_sql(
                case["question"],
                settings,
                conn=conn,
                ollama_client=client,
                skip_answer=True,
            )
            scored = score_case(case, result)
            scored["elapsed_sec"] = round(time.time() - t0, 2)
            reports.append(scored)
            print(
                f"  syntax={scored['syntax_valid']} exec={scored['exec_success']} "
                f"acc={scored['execution_accuracy']} got={scored['got_value']} "
                f"expected={scored['expected']} ({scored['elapsed_sec']}s)",
                flush=True,
            )
            if scored.get("sql"):
                print(f"  SQL: {scored['sql'][:200]}", flush=True)
            if scored.get("error"):
                print(f"  ERR: {scored['error']}", flush=True)

    n = len(reports) or 1
    summary = {
        "model": model,
        "n": len(reports),
        "syntax_validity": round(sum(r["syntax_valid"] for r in reports) / n, 3),
        "execution_success": round(sum(r["exec_success"] for r in reports) / n, 3),
        "execution_accuracy": round(
            sum(r["execution_accuracy"] for r in reports) / n, 3
        ),
        "schema_linking_accuracy": round(
            sum(r["schema_linking_ok"] for r in reports) / n, 3
        ),
        "avg_elapsed_sec": round(
            sum(r["elapsed_sec"] for r in reports) / n, 2
        ),
        "cases": reports,
    }
    print(
        f">>> {model}: syn={summary['syntax_validity']} "
        f"exec={summary['execution_success']} "
        f"acc={summary['execution_accuracy']} "
        f"link={summary['schema_linking_accuracy']}",
        flush=True,
    )
    return summary


def build_comparison(results: list[dict[str, Any]], skipped: list[str]) -> dict[str, Any]:
    ranking = sorted(
        [
            {
                "model": r["model"],
                "execution_accuracy": r["execution_accuracy"],
                "execution_success": r["execution_success"],
                "syntax_validity": r["syntax_validity"],
                "schema_linking_accuracy": r["schema_linking_accuracy"],
                "avg_elapsed_sec": r["avg_elapsed_sec"],
            }
            for r in results
        ],
        key=lambda x: (
            x["execution_accuracy"],
            x["execution_success"],
            x["schema_linking_accuracy"],
        ),
        reverse=True,
    )
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pipeline": "phase1_rag_sql (M-Schema + example retrieval + sqlglot/explain + retry)",
        "metrics": [
            "syntax_validity",
            "execution_success",
            "execution_accuracy",
            "schema_linking_accuracy",
        ],
        "skipped_models": skipped,
        "ranking": ranking,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Baseline NL2SQL 모델 비교")
    parser.add_argument(
        "--models",
        nargs="*",
        default=DEFAULT_MODELS,
        help="비교할 Ollama 모델 목록",
    )
    parser.add_argument(
        "--out",
        default="benchmark_baseline_results.json",
        help="결과 JSON 경로",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="케이스 수 제한 (0=전체)",
    )
    args = parser.parse_args()

    settings = load_settings()
    local = list_local_models(settings.ollama_host)
    models, skipped = resolve_models(list(args.models), local)
    cases = GT_CASES[: args.limit] if args.limit and args.limit > 0 else GT_CASES

    print("Local models:", sorted(local))
    print("Evaluate:", models)
    if skipped:
        print("Skipped (not installed):", skipped)

    if not models:
        raise SystemExit("평가할 모델이 없습니다. ollama pull 후 다시 실행하세요.")

    results = [evaluate_model(m, cases=cases) for m in models]
    payload = build_comparison(results, skipped)
    out_path = Path(args.out)
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n=== RANKING ===")
    print(json.dumps(payload["ranking"], ensure_ascii=False, indent=2))
    print(f"saved: {out_path}")


if __name__ == "__main__":
    main()
