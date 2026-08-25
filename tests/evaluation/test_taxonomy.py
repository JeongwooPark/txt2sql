from txt2sql.evaluation.taxonomy import ERROR_LABELS


def test_taxonomy_covers_required_codes() -> None:
    required = {
        "R01", "P01", "P02", "P03", "P04", "P05", "P06", "P07",
        "S01", "S02", "S03", "S04", "G01", "G02",
        "Q01", "Q02", "Q03", "A01", "A02", "C01",
    }
    assert required <= set(ERROR_LABELS)
    assert ERROR_LABELS["P05"] == "aggregate_error"
    assert ERROR_LABELS["A01"] == "should_clarify_but_executed"
