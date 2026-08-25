"""QLoRA 실험 자격. verified pair·holdout·GPU가 모두 충족될 때만 시작한다."""

from __future__ import annotations

import json
from pathlib import Path

MIN_VERIFIED_PAIRS = 5000


def count_verified_pairs(gold_path: Path) -> int:
    n = 0
    for line in gold_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("status") == "verified":
            n += 1
    return n


def assess_lora_eligibility(
    *,
    verified_pairs: int,
    holdout_separated: bool,
    gpu_available: bool,
) -> dict[str, object]:
    reasons: list[str] = []
    if verified_pairs < MIN_VERIFIED_PAIRS:
        reasons.append(f"verified_pairs {verified_pairs} < {MIN_VERIFIED_PAIRS}")
    if not holdout_separated:
        reasons.append("holdout_not_separated")
    if not gpu_available:
        reasons.append("gpu_unavailable")
    eligible = not reasons
    return {
        "status": "ELIGIBLE" if eligible else "NOT_ELIGIBLE",
        "verified_pairs": verified_pairs,
        "min_verified_pairs": MIN_VERIFIED_PAIRS,
        "holdout_separated": holdout_separated,
        "gpu_available": gpu_available,
        "reasons": reasons,
    }
