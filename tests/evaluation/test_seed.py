from llm2sql.evaluation.harness import evaluate_case
from llm2sql.evaluation.jsonl import dump_jsonl, load_jsonl
from llm2sql.evaluation.seed_cases import seed_cases


def test_seed_schema_and_count() -> None:
    cases = seed_cases()
    assert len(cases) == 30
    assert all(item.status == "verified" for item in cases)
    assert all(item.gold_plan is not None for item in cases)
    ids = [item.id for item in cases]
    assert ids == [f"K{i:02d}" for i in range(1, 31)]


def test_seed_jsonl_roundtrip(tmp_path) -> None:
    path = tmp_path / "test.jsonl"
    dump_jsonl(path, seed_cases())
    loaded = load_jsonl(path)
    assert len(loaded) == 30
    assert loaded[0].gold_plan["aggregations"][0]["function"] == "sum"


def test_evaluator_labels_nine_semantic_errors() -> None:
    cases = {item.id: item for item in seed_cases()}
    sum_wrong = dict(cases["K01"].gold_plan)
    sum_wrong["aggregations"] = [{"function": "avg", "field": "height_m", "alias": "avg_height_m"}]
    assert "P05" in evaluate_case(cases["K01"], predicted_plan=sum_wrong).error_codes

    max_wrong = dict(cases["K02"].gold_plan)
    max_wrong["aggregations"] = [{"function": "avg", "field": "height_m", "alias": "avg_height_m"}]
    assert "P05" in evaluate_case(cases["K02"], predicted_plan=max_wrong).error_codes

    min_wrong = dict(cases["K03"].gold_plan)
    min_wrong["aggregations"] = [{"function": "avg", "field": "gross_floor_area_m2", "alias": "avg_gfa"}]
    assert "P05" in evaluate_case(cases["K03"], predicted_plan=min_wrong).error_codes

    group_wrong = dict(cases["K04"].gold_plan)
    group_wrong["group_by"] = []
    group_wrong["aggregations"] = [{"function": "count", "field": None, "alias": "n"}]
    assert "P05" in evaluate_case(cases["K04"], predicted_plan=group_wrong).error_codes

    not_wrong = dict(cases["K05"].gold_plan)
    not_wrong["filters"] = [{"field": "usage", "operator": "eq", "value": "공동주택", "value2": None, "unit": None}]
    not_wrong["predicate"] = None
    codes = evaluate_case(cases["K05"], predicted_plan=not_wrong).error_codes
    assert "P04" in codes

    or_wrong = dict(cases["K06"].gold_plan)
    or_wrong["predicate"] = {"op": "and", "args": cases["K06"].gold_plan["predicate"]["args"]}
    assert "P04" in evaluate_case(cases["K06"], predicted_plan=or_wrong).error_codes

    range_wrong = dict(cases["K07"].gold_plan)
    range_wrong["filters"] = [
        {"field": "height_m", "operator": "gte", "value": 50, "value2": None, "unit": "m"}
    ]
    assert "P03" in evaluate_case(cases["K07"], predicted_plan=range_wrong).error_codes

    asc_wrong = dict(cases["K08"].gold_plan)
    asc_wrong["order_by"] = [{"field": "height_m", "direction": "desc", "nulls": "last"}]
    assert "P06" in evaluate_case(cases["K08"], predicted_plan=asc_wrong).error_codes

    cmp_wrong = dict(cases["K09"].gold_plan)
    cmp_wrong["filters"] = []
    codes = evaluate_case(cases["K09"], predicted_plan=cmp_wrong).error_codes
    assert "P02" in codes or "P03" in codes
