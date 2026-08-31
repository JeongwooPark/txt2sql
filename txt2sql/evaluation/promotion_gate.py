"""Promotion gate checker (Gate 1: MAIN >= 70%)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from txt2sql.evaluation.baseline import load_baseline_manifest
from txt2sql.evaluation.execution_sources import share_execution_sources

ROOT = Path(__file__).resolve().parents[2]

GATE1_TARGET_PASS = 340
GATE1_TARGET_TOTAL = 485
GATE1_TARGET_ACC = 70.0
GATE1_SEMANTIC_IR_MIN = 50.0
GATE1_LEGACY_MAX = 35.0


def check_promotion_gate(
    result: dict[str, Any],
    *,
    baseline_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check Gate 1 promotion criteria."""
    main = result.get("main") or {}
    if "passed" not in main and "passed" in result:
        main = {
            "passed": result.get("passed"),
            "total": result.get("total"),
            "accuracy_pct": result.get("accuracy_pct"),
        }

    passed = int(main.get("passed", 0))
    total = int(main.get("total", 0))
    acc = float(main.get("accuracy_pct", 0))

    exec_share = share_execution_sources(result)
    semantic_ir_pct = 0.0
    legacy_pct = 0.0
    share = exec_share.get("share_pct") or {}
    for src, pct in share.items():
        if src in {"semantic_v2", "ir_fast_path"}:
            semantic_ir_pct += pct
        if src in {"legacy_router"}:
            legacy_pct += pct

    migration = result.get("migration") or result.get("fixed") and {
        "fixed": result.get("fixed"),
        "regressed": result.get("regressed"),
    } or {}
    regressed_n = len(migration.get("regressed") or []) if isinstance(migration.get("regressed"), list) else migration.get("regressed_n", 0)
    fixed_n = len(migration.get("fixed") or []) if isinstance(migration.get("fixed"), list) else migration.get("fixed_n", 0)

    checks = {
        "main_accuracy": acc >= GATE1_TARGET_ACC,
        "main_pass_count": passed >= GATE1_TARGET_PASS,
        "place_scope_regression_zero": regressed_n == 0 or (baseline_manifest and baseline_manifest.get("regressed", 0) == 0),
        "regressed_lte_fixed": regressed_n <= fixed_n,
        "semantic_ir_coverage": semantic_ir_pct >= GATE1_SEMANTIC_IR_MIN,
        "legacy_share_not_increased": legacy_pct <= GATE1_LEGACY_MAX,
    }

    return {
        "gate": "Gate1",
        "target": f"{GATE1_TARGET_PASS}/{GATE1_TARGET_TOTAL} ({GATE1_TARGET_ACC}%)",
        "actual": f"{passed}/{total} ({acc}%)",
        "passed": all(checks.values()),
        "checks": checks,
        "execution_source_share": share,
        "semantic_ir_pct": semantic_ir_pct,
        "legacy_pct": legacy_pct,
        "migration": {
            "fixed_n": fixed_n,
            "regressed_n": regressed_n,
        },
    }


def check_from_file(result_path: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    try:
        baseline = load_baseline_manifest()
    except Exception:
        baseline = None
    return check_promotion_gate(result, baseline_manifest=baseline)
