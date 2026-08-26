"""Stage evaluation tests."""

from txt2sql.evaluation.stage_eval import evaluate_stages, migrate_failures


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
