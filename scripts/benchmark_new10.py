"""신규/후속 기능 검증용 질문 10건 감증 테스트."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from llm2sql.config import load_settings
from llm2sql.pipeline import ask
from llm2sql.session import SessionContext

CASES: list[dict[str, Any]] = [
    {
        "id": "n01",
        "question": "현재 사용가능한 데이터는 몇개야?",
        "expect_route": "meta_catalog_count",
        "expect_contains": ["6개"],
        "note": "카탈로그 개수",
    },
    {
        "id": "n02",
        "question": "A4 컬럼 의미가 뭐야?",
        "expect_route": "meta_column",
        "expect_contains": ["법정동명", "테이블마다"],
        "note": "속성 설명(컬럼)",
    },
    {
        "id": "n03",
        "question": "송정동 건물 몇 채야?",
        "expect_route": "clarify_place",
        "expect_contains": ["강서구", "해운대구"],
        "note": "동명 모호성 확인",
    },
    {
        "id": "n04",
        "question": "구서동에서 제일 좋은 아파트는?",
        "expect_route": "clarify_vague",
        "expect_contains": ["주관", "건물면적", "연면적"],
        "note": "주관적 표현 확인 요청",
    },
    {
        "id": "n05",
        "question": "구서동 아파트의 특징은?",
        "expect_route": "building_profile",
        "expect_contains": ["공동주택", "연면적", "503"],
        "note": "동+용도 특징 요약",
    },
    {
        "id": "n06",
        "question": "구서동에서 건물면적이 가장 큰 아파트는?",
        "expect_route": "building_rank_건물면적",
        "expect_contains": ["구서", "건물면적"],
        "note": "건물면적 순위 (후속 기준점)",
        "session": "rank",
    },
    {
        "id": "n07",
        "question": "그 아파트의 이름은?",
        "expect_route": "followup_attr",
        "expect_contains": ["건물명"],
        "note": "후속: 이름",
        "session": "rank",
    },
    {
        "id": "n08",
        "question": "지번은?",
        "expect_route": "followup_attr",
        "expect_contains": ["지번"],
        "note": "후속: 지번",
        "session": "rank",
    },
    {
        "id": "n09",
        "question": "구서동에서 높이가 가장 높은 아파트는?",
        "expect_route": "building_rank_높이",
        "expect_contains": ["높이", "구서동"],
        "note": "높이 순위",
    },
    {
        "id": "n10",
        "question": "하동 아파트 특징은?",
        "expect_route": "clarify_unknown_place",
        "expect_contains": ["찾지 못"],
        "note": "없는 지명 확인",
    },
]


def _pass_case(case: dict[str, Any], result: dict[str, Any]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    route = result.get("route")
    answer = result.get("answer") or ""
    if case.get("expect_route") and route != case["expect_route"]:
        issues.append(f"route={route} (expected {case['expect_route']})")
    for token in case.get("expect_contains") or []:
        if token not in answer:
            issues.append(f"missing:{token}")
    if not result.get("ok", True):
        issues.append(f"ok=False error={result.get('error')}")
    return (len(issues) == 0, issues)


def main() -> None:
    settings = load_settings()
    sessions: dict[str, SessionContext] = {}
    results: list[dict[str, Any]] = []
    passed = 0

    print("=== 신규 기능 감증 테스트 (10문항) ===\n")
    t0 = time.perf_counter()

    for case in CASES:
        sid = case.get("session")
        if sid:
            session = sessions.setdefault(sid, SessionContext())
        else:
            session = SessionContext()

        q = case["question"]
        started = time.perf_counter()
        result = ask(q, settings, session=session)
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        ok, issues = _pass_case(case, result)
        if ok:
            passed += 1

        row = {
            "id": case["id"],
            "note": case["note"],
            "question": q,
            "pass": ok,
            "issues": issues,
            "route": result.get("route"),
            "elapsed_ms": elapsed_ms,
            "answer": result.get("answer"),
            "sql": result.get("sql"),
            "focus_a0": (session.focus_row or {}).get("A0"),
            "focus_name": (session.focus_row or {}).get("A24"),
        }
        results.append(row)

        status = "PASS" if ok else "FAIL"
        print(f"[{case['id']}] {status} ({elapsed_ms} ms) — {case['note']}")
        print(f"  Q: {q}")
        print(f"  route: {result.get('route')}")
        ans = (result.get("answer") or "").replace("\n", " / ")
        if len(ans) > 240:
            ans = ans[:237] + "..."
        print(f"  A: {ans}")
        if issues:
            print(f"  issues: {issues}")
        if sid and session.focus_row:
            print(
                f"  session[{sid}]: A0={session.focus_row.get('A0')} "
                f"name={session.focus_row.get('A24')}"
            )
        print()

    total_ms = round((time.perf_counter() - t0) * 1000)
    summary = {
        "passed": passed,
        "total": len(CASES),
        "pass_rate": passed / len(CASES),
        "elapsed_ms": total_ms,
        "fail_ids": [r["id"] for r in results if not r["pass"]],
        "cases": results,
    }
    out = Path("benchmark_new10_results.json")
    out.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print("=== OVERALL ===")
    print(
        json.dumps(
            {
                "passed": passed,
                "total": len(CASES),
                "pass_rate": summary["pass_rate"],
                "elapsed_ms": total_ms,
                "fail_ids": summary["fail_ids"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"saved: {out.resolve()}")


if __name__ == "__main__":
    main()
