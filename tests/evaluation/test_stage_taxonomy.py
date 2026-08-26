"""Stage taxonomy mapping tests."""

from collections import Counter

from txt2sql.evaluation.stage_eval import stages_from_reason, taxonomy_from_reason


def test_stage_taxonomy_common_reasons() -> None:
    assert taxonomy_from_reason("count-mismatch gold=1") == "COUNT_MISMATCH"
    assert "p03" in taxonomy_from_reason("engine-fail:P03").lower() or "P03" in taxonomy_from_reason(
        "engine-fail:P03"
    )
    ev = stages_from_reason(case_id="Q1", final_pass=False, reason="scalar-mismatch")
    assert ev.stages.execution == "FAIL"
    assert ev.root_cause == "SCALAR_MISMATCH"


def test_no_unknown_flood_on_real_reasons() -> None:
    reasons = [
        "count-mismatch",
        "list-top-missing",
        "scalar-mismatch",
        "engine-fail:plan generation failed",
        "group-mismatch",
        "engine-fail:P03",
        "engine-fail:unsupported_coverage:",
        "engine-fail:slot_below_threshold:fields",
    ]
    tax = Counter(taxonomy_from_reason(r) for r in reasons)
    assert tax.get("unknown", 0) == 0
