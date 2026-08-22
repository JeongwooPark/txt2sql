"""A–E 승격 비교. 미달 또는 ENV_BLOCKED이면 hybrid로 올리지 않는다."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _read(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    artifacts = ROOT / "artifacts" / "evaluation"
    phase1 = _read(artifacts / "phase1_gate.json")
    phase2 = _read(artifacts / "phase2_retrieval_gate.json")
    phase3 = _read(artifacts / "phase3_gate.json")
    phase4 = _read(artifacts / "phase4_gate.json")
    variant_a = _read(artifacts / "variant_a_off.json")

    blocked: list[str] = []
    summary1 = phase1.get("summary") or {}
    p1_ok = (
        phase1.get("gate_passed") is True
        or phase1.get("phase1_gate") == "PASSED"
    ) and int(summary1.get("passed") or 0) >= 30 and not summary1.get("env_blocked")
    if not p1_ok:
        blocked.append("phase1_gold")

    p2_ok = (
        phase2.get("gate_passed") is True
        and int(phase2.get("n") or 0) >= 10
        and float(phase2.get("schema_recall_at_10") or 0) >= 1.0
        and float(phase2.get("value_recall_at_5") or 0) >= 1.0
        and not phase2.get("env_blocked")
    )
    if not p2_ok:
        blocked.append("phase2_holdout")

    if phase3.get("gate_passed") is not True:
        blocked.append("phase3_unit")

    live = phase4.get("live_spatial_accuracy")
    live_ok = (
        isinstance(live, dict)
        and float(live.get("accuracy") or 0) >= 1.0
        and int(live.get("passed") or 0) == int(live.get("n") or 0)
        and int(live.get("n") or 0) >= 6
        and phase4.get("env_blocked") is not True
        and phase4.get("gate_passed") is True
    )
    if live == "not_measured" or not live_ok:
        blocked.append("phase4_live_spatial")

    a_summary = (variant_a.get("summary") or {}) if variant_a else {}
    a_ran = bool(variant_a) and a_summary.get("env_blocked") is not True
    if variant_a and a_summary.get("env_blocked"):
        blocked.append("variant_a_env_blocked")
    elif not variant_a:
        blocked.append("variant_a_not_run")

    promote = not blocked
    payload = {
        "variants": {
            "A": {
                "label": "off",
                "semantic_plan_mode": "off",
                "ran": a_ran,
                "env_blocked": bool(a_summary.get("env_blocked")),
                "summary": a_summary or None,
                "block_reason": variant_a.get("block_reason") if variant_a else "not_run",
                "note": "baseline 0.2.2 path; --official omitted because models use :latest; digest recorded",
            },
            "B": {
                "label": "hybrid_0.2.2",
                "semantic_plan_mode": "hybrid",
                "ran": False,
                "note": "pre-v1.1 hybrid not re-run; compare C/E against A only",
            },
            "C": {
                "label": "plan11_verifier",
                "semantic_plan_mode": "hybrid" if promote else "shadow",
                "ran": True,
                "phase1": {
                    "phase1_gate": phase1.get("phase1_gate"),
                    "gate_passed": phase1.get("gate_passed"),
                    "summary": summary1,
                },
            },
            "D": {
                "label": "plus_linking",
                "semantic_plan_mode": "hybrid" if promote else "shadow",
                "ran": True,
                "phase2": phase2,
            },
            "E": {
                "label": "plus_candidates",
                "semantic_plan_mode": "hybrid" if promote else "shadow",
                "ran": True,
                "phase3": phase3,
                "phase4": {
                    "gate_passed": phase4.get("gate_passed"),
                    "env_blocked": phase4.get("env_blocked"),
                    "live_spatial_accuracy": live,
                    "unit_tests_passed": phase4.get("unit_tests_passed"),
                },
            },
        },
        "promote_hybrid": promote,
        "keep_mode": "hybrid" if promote else "shadow",
        "blocked_by": blocked,
        "official_latest_tag": False,
        "models": variant_a.get("models"),
        "note": (
            "Promoted SEMANTIC_PLAN_MODE default to hybrid."
            if promote
            else "Do not change SEMANTIC_PLAN_MODE default to hybrid until every promotion KPI passes without ENV_BLOCKED."
        ),
    }
    out = artifacts / "phase5_promotion.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"promote_hybrid": promote, "blocked_by": blocked, "keep_mode": payload["keep_mode"]}, ensure_ascii=False, indent=2))
    return 0 if promote else 1


if __name__ == "__main__":
    raise SystemExit(main())
