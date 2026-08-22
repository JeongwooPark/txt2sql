"""A–E 승격 비교. 미달 또는 ENV_BLOCKED이면 hybrid로 올리지 않는다."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    artifacts = ROOT / "artifacts" / "evaluation"
    phase1 = json.loads((artifacts / "phase1_gate.json").read_text(encoding="utf-8"))
    phase2 = json.loads((artifacts / "phase2_retrieval_gate.json").read_text(encoding="utf-8"))
    phase3 = json.loads((artifacts / "phase3_gate.json").read_text(encoding="utf-8"))
    phase4 = json.loads((artifacts / "phase4_gate.json").read_text(encoding="utf-8"))
    blocked = []
    if phase1.get("phase1_gate") != "PASSED" and not phase1.get("gate_passed"):
        blocked.append("phase1_gold")
    if not phase2.get("gate_passed"):
        blocked.append("phase2_holdout")
    live_missing = phase4.get("live_spatial_accuracy") == "not_measured"
    if live_missing:
        blocked.append("phase4_live_spatial")
    payload = {
        "variants": {
            "A": {"label": "off", "semantic_plan_mode": "off", "ran": False, "note": "baseline 0.2.2 path"},
            "B": {"label": "hybrid_0.2.2", "semantic_plan_mode": "hybrid", "ran": False, "note": "pre-v1.1 hybrid not re-run as default"},
            "C": {"label": "plan11_verifier", "semantic_plan_mode": "shadow", "ran": True, "phase1": phase1},
            "D": {"label": "plus_linking", "semantic_plan_mode": "shadow", "ran": True, "phase2": phase2},
            "E": {"label": "plus_candidates", "semantic_plan_mode": "shadow", "ran": True, "phase3": phase3, "phase4": phase4},
        },
        "promote_hybrid": False,
        "keep_mode": "shadow",
        "blocked_by": blocked,
        "official_latest_tag": False,
        "note": "Do not change SEMANTIC_PLAN_MODE default to hybrid until every promotion KPI passes without ENV_BLOCKED.",
    }
    out = artifacts / "phase5_promotion.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(out.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
