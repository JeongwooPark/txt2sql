"""Stage evaluation tests."""

from txt2sql.evaluation.stage_eval import (
    evaluate_stages,
    migrate_failures,
    stages_from_reason,
    stages_from_result,
)


def test_stage_eval_root_cause() -> None:
    result = evaluate_stages(
        case_id="Q203",
        final_pass=False,
        understanding_ok=True,
        binding_ok=True,
        logical_ok=True,
        physical_ok=True,
        compile_ok=True,
        execution_ok=True,
        policy_ok=False,
    )
    assert result.stages.policy == "FAIL"
    assert result.root_cause == "STAGE_POLICY"
    assert result.as_dict()["id"] == "Q203"


def test_failure_migration() -> None:
    before = {"A": True, "B": False, "C": False}
    after = {"A": False, "B": True, "C": False}
    mig = migrate_failures(before, after)
    assert mig["fixed"] == ["B"]
    assert mig["regressed"] == ["A"]
    assert mig["still_fail"] == ["C"]


def test_stages_from_result_v2_compile_failure() -> None:
    row = {
        "logical_status": "READY",
        "physical_strategy": "D198_EXECUTOR",
        "execution_source": "semantic_plan",
        "v2_failure_code": "COMPILE",
        "reason": "count-mismatch",
    }
    ev = stages_from_result(case_id="Q301", final_pass=False, row=row)
    assert ev.stages.compile == "FAIL"
    assert ev.root_cause == "V2_COMPILE"
    assert ev.extras.get("source") == "result_fields"


def test_stages_from_result_v2_success_pass() -> None:
    row = {
        "logical_status": "READY",
        "physical_strategy": "D198_EXECUTOR",
        "execution_source": "semantic_v2",
    }
    ev = stages_from_result(case_id="Q301", final_pass=True, row=row)
    assert ev.stages.compile == "PASS"
    assert ev.stages.execution == "PASS"


def test_stages_from_result_falls_back_to_reason() -> None:
    row = {"reason": "count-mismatch gold=1 pred=[2]"}
    ev = stages_from_result(case_id="Qx", final_pass=False, row=row, reason=row["reason"])
    # No obs fields → reason path
    assert ev.stages.execution == "FAIL"
    assert "COUNT" in (ev.root_cause or "") or ev.root_cause == "COUNT_MISMATCH"
