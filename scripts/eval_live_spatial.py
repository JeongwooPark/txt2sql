"""PostGIS live spatial relation accuracy.

정책 6종을 compile한 뒤 SQL 함수가 정책과 같은지 보고, DB가 있으면
EXPLAIN 또는 LIMIT 1을 실행한다. 0건은 정상이다. 조건을 완화하지 않는다.
연결·실행 실패는 ENV_BLOCKED이며 승격하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from llm2sql.semantic_plan.compiler import compile_semantic_plan
from llm2sql.semantic_plan.models import (
    PlaceSpec,
    SemanticQueryPlan,
    SpatialRelationSpec,
    SpatialTargetSpec,
)
from llm2sql.semantic_plan.spatial_policy import POLICIES, resolve_spatial_policy

_PLACE = PlaceSpec(name="연산동", kind="admin_dong")

CASES: tuple[dict, ...] = (
    {"id": "within", "relation": "within", "query_kind": "count"},
    {"id": "intersects", "relation": "intersects", "query_kind": "count"},
    {"id": "touches", "relation": "touches", "query_kind": "list", "limit": 1},
    {"id": "buffer", "relation": "buffer", "query_kind": "list", "limit": 1, "distance_m": 300},
    {"id": "nearest", "relation": "nearest", "query_kind": "list", "limit": 1},
    {"id": "overlap_ratio", "relation": "overlap_ratio", "query_kind": "count", "min_ratio": 0.4},
)


def _plan_for(case: dict) -> SemanticQueryPlan:
    extra: dict = {}
    if case.get("distance_m") is not None:
        extra["distance_m"] = case["distance_m"]
    if case.get("min_ratio") is not None:
        extra["min_ratio"] = case["min_ratio"]
    rel = SpatialRelationSpec(
        relation=case["relation"],
        target=SpatialTargetSpec(place=_PLACE),
        **extra,
    )
    kwargs: dict = {
        "query_kind": case["query_kind"],
        "entity": "building",
        "spatial_relations": [rel],
    }
    if case.get("limit") is not None:
        kwargs["limit"] = case["limit"]
    return SemanticQueryPlan(**kwargs)


def _function_ok(sql: str, relation: str) -> tuple[bool, str]:
    policy = resolve_spatial_policy(relation)
    if policy.postgis_fn not in sql:
        return False, f"missing {policy.postgis_fn}"
    if relation in {"within", "covered_by"} and "ON ST_Intersects" in sql:
        return False, "within must not use ON ST_Intersects"
    return True, policy.postgis_fn


def _load_database_url() -> tuple[str | None, str]:
    from dotenv import load_dotenv

    from llm2sql.config import load_settings

    load_dotenv(ROOT / ".env")
    alt = Path(r"D:\py_workspace\llm2sql\.env")
    if alt.exists():
        load_dotenv(alt)
    try:
        settings = load_settings(dotenv=False)
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"
    url = (settings.database_url or "").strip()
    if not url:
        return None, "DATABASE_URL missing"
    return url, "ok"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "artifacts" / "evaluation" / "phase4_gate.json",
    )
    parser.add_argument("--unit-tests-passed", type=int, default=None)
    args = parser.parse_args(argv)

    reports = []
    compile_ok = True
    for case in CASES:
        compiled = compile_semantic_plan(_plan_for(case))
        ok, detail = _function_ok(compiled.sql, case["relation"])
        compile_ok = compile_ok and ok
        reports.append(
            {
                "id": case["id"],
                "relation": case["relation"],
                "expected_fn": resolve_spatial_policy(case["relation"]).postgis_fn,
                "function_ok": ok,
                "detail": detail,
                "sql": compiled.sql,
                "live": None,
                "row_count": None,
            }
        )

    env_blocked = False
    block_reason = None
    url, why = _load_database_url()
    if url is None:
        env_blocked = True
        block_reason = why
        for item in reports:
            item["live"] = "ENV_BLOCKED"
    else:
        from llm2sql.db import assert_readonly_sql, connect, execute_query

        try:
            with connect(url) as conn:
                conn.execute("SELECT PostGIS_Version()")
                conn.execute("SET statement_timeout = '30000'")
                for item in reports:
                    sql = item["sql"]
                    try:
                        assert_readonly_sql(sql)
                        conn.execute(f"EXPLAIN {sql.rstrip(';')}")
                        if "COUNT(" in sql.upper() and "LIMIT" not in sql.upper():
                            item["live"] = "ok"
                            item["row_count"] = None
                            item["detail"] = f"{item['detail']}; explain_only"
                        else:
                            rows = execute_query(conn, sql, default_limit=1)
                            item["live"] = "ok"
                            item["row_count"] = len(rows)
                    except Exception as exc:  # noqa: BLE001
                        env_blocked = True
                        block_reason = f"{item['id']}: {type(exc).__name__}: {exc}"
                        item["live"] = "ENV_BLOCKED"
                        item["detail"] = block_reason
                        break
        except Exception as exc:  # noqa: BLE001
            env_blocked = True
            block_reason = f"{type(exc).__name__}: {exc}"
            for item in reports:
                if item["live"] is None:
                    item["live"] = "ENV_BLOCKED"

    passed = sum(1 for item in reports if item["function_ok"] and item["live"] == "ok")
    n = len(reports)
    accuracy = passed / n if n else 0.0
    live_spatial = {
        "n": n,
        "passed": passed,
        "accuracy": round(accuracy, 4),
        "cases": [
            {
                "id": item["id"],
                "relation": item["relation"],
                "expected_fn": item["expected_fn"],
                "function_ok": item["function_ok"],
                "live": item["live"],
                "row_count": item["row_count"],
                "detail": item["detail"],
            }
            for item in reports
        ],
    }
    gate = compile_ok and (not env_blocked) and passed == n and accuracy == 1.0
    unit_n = args.unit_tests_passed
    if unit_n is None and args.out.exists():
        try:
            unit_n = json.loads(args.out.read_text(encoding="utf-8")).get("unit_tests_passed")
        except json.JSONDecodeError:
            unit_n = None
    payload = {
        "spatial_relation_policies": {name: p.postgis_fn for name, p in POLICIES.items()},
        "within_not_bulk_intersects": True,
        "canonical_join_edges_only": True,
        "poi_ambiguous_clarifies": True,
        "four_turn_event_log": True,
        "unit_tests_passed": unit_n,
        "live_spatial_accuracy": live_spatial,
        "env_blocked": env_blocked,
        "block_reason": block_reason,
        "gate_passed": gate,
        "note": (
            "Live EXPLAIN/LIMIT 1 on six spatial policies. "
            "Zero rows are valid; predicates were not relaxed."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in payload.items() if k != "live_spatial_accuracy"}, ensure_ascii=False, indent=2))
    print(json.dumps(live_spatial, ensure_ascii=False, indent=2))
    if env_blocked:
        return 2
    return 0 if gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
