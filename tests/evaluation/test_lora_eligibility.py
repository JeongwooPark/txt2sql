from pathlib import Path

from llm2sql.evaluation.lora_eligibility import (
    MIN_VERIFIED_PAIRS,
    assess_lora_eligibility,
    count_verified_pairs,
)


def test_current_gold_is_not_eligible() -> None:
    gold = Path("benchmarks/korean_postgis_v1/test.jsonl")
    n = count_verified_pairs(gold)
    result = assess_lora_eligibility(
        verified_pairs=n,
        holdout_separated=False,
        gpu_available=True,
    )
    assert n < MIN_VERIFIED_PAIRS
    assert result["status"] == "NOT_ELIGIBLE"
    assert any("verified_pairs" in item for item in result["reasons"])
