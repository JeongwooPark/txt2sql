"""Round migration fixture tests."""

from txt2sql.evaluation.case_map import case_pass_map, case_passed
from txt2sql.evaluation.stage_eval import migrate_failures


def test_migration_fixture_exact() -> None:
    # before: 2 pass / 2 fail
    before = {"A": True, "B": True, "C": False, "D": False}
    # after: A still pass, B regressed, C fixed, D still fail
    after = {"A": True, "B": False, "C": True, "D": False}
    mig = migrate_failures(before, after)
    assert mig["fixed"] == ["C"]
    assert mig["regressed"] == ["B"]
    assert mig["still_pass"] == ["A"]
    assert mig["still_fail"] == ["D"]
    assert len(mig["fixed"]) + len(mig["regressed"]) + len(mig["still_pass"]) + len(
        mig["still_fail"]
    ) == 4


def test_case_pass_prefers_pass_key() -> None:
    assert case_passed({"pass": False, "ok": True}) is False
    assert case_passed({"ok": False}) is False
    assert case_passed({"passed": True}) is True


def test_case_pass_map_from_rows() -> None:
    doc = {
        "rows": [
            {"id": "Q1", "pass": True},
            {"id": "Q2", "pass": False},
        ]
    }
    assert case_pass_map(doc) == {"Q1": True, "Q2": False}
