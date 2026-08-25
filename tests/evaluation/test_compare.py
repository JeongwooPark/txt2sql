from txt2sql.evaluation.compare import compare, to_markdown
from txt2sql.evaluation.results import compare_result_sets


def test_compare_runs_delta() -> None:
    a = {"summary": {"name": "eval_plan", "mode": "off", "n": 2, "passed": 0, "metrics": {"plan_exact_match": 0.0}, "env_blocked": False, "error_counts": {"P05": 2}}}
    b = {"summary": {"name": "eval_plan", "mode": "hybrid", "n": 2, "passed": 1, "metrics": {"plan_exact_match": 0.5}, "env_blocked": False, "error_counts": {"P05": 1}}}
    cmp = compare(a, b)
    assert cmp["metrics"]["plan_exact_match"]["delta"] == 0.5
    md = to_markdown(cmp)
    assert "plan_exact_match" in md


def test_compare_result_sets_uses_hash_not_sql() -> None:
    gold = [{"a": 1}]
    pred = [{"a": 1}]
    out = compare_result_sets(pred, gold, mode="set")
    assert out["match"] is True
    assert "sql" not in out
