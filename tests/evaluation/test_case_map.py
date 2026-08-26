"""case_map extraction tests."""

from txt2sql.evaluation.case_map import case_pass_map, case_rows


def test_prefers_rows_with_pass() -> None:
    doc = {
        "failed_items": [{"id": "X", "reason": "x"}],
        "rows": [
            {"id": "A", "pass": True},
            {"id": "B", "pass": False},
        ],
    }
    rows = case_rows(doc)
    assert len(rows) == 2
    assert case_pass_map(doc) == {"A": True, "B": False}


def test_false_pass_not_swallowed_by_ok_chain() -> None:
    # Historical bug: ok or passed or pass would skip False incorrectly if ok were weird;
    # explicit key order must keep pass=False.
    doc = {"rows": [{"id": "Z", "pass": False}]}
    assert case_pass_map(doc)["Z"] is False
