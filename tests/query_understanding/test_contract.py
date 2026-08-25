from txt2sql.query_understanding.contract import extract_contract
from txt2sql.evaluation.seed_cases import seed_cases


def test_and_or_not_spans() -> None:
    c = extract_contract("해운대구 공동주택 또는 단독주택 그리고 창고 제외")
    kinds = {item.kind for item in c.boolean_ops}
    assert "or" in kinds
    assert "not" in kinds
    or_span = next(item for item in c.boolean_ops if item.kind == "or")
    assert c.question[or_span.start:or_span.end] == "또는"


def test_range_span_indices() -> None:
    q = "부산진구 높이 50m 이상 100m 이하 건물"
    c = extract_contract(q)
    assert c.ranges
    span = c.ranges[0]
    assert q[span.start:span.end] == span.text
    assert span.meta["low"] == 50
    assert span.meta["high"] == 100
    assert span.meta.get("field") == "height_m"


def test_area_range_inclusive_exclusive() -> None:
    q = "구서1동에서 면적이 1000이상 10000미만의 건물을 찾아라"
    c = extract_contract(q)
    assert c.ranges
    span = c.ranges[0]
    assert span.meta["low"] == 1000
    assert span.meta["high"] == 10000
    assert span.meta.get("lo_rel") == "이상"
    assert span.meta.get("hi_rel") == "미만"
    assert span.meta.get("field") == "gross_floor_area_m2"


def test_spacing_and_particle_variants() -> None:
    a = extract_contract("수영구 건물 최대높이")
    b = extract_contract("수영구 건물 최대 높이")
    assert a.aggregations and a.aggregations[0].value == "max"
    assert b.aggregations and b.aggregations[0].value == "max"
    c = extract_contract("연제구에서 창고시설이 아닌 건물 수")
    assert any(item.kind == "not" for item in c.boolean_ops)


def test_sort_aggregate_compare() -> None:
    c = extract_contract("기장군 낮은 건물 10개")
    assert any(item.value == "asc" for item in c.order)
    assert c.limits and c.limits[0].value == 10
    d = extract_contract("해운대구 건물 높이 합계")
    assert d.aggregations[0].value == "sum"
    e = extract_contract("남구에서 건축면적이 연면적보다 큰 건물")
    assert e.comparisons
    assert e.comparisons[0].value["left"] == "building_area_m2"
    assert e.comparisons[0].value["right"] == "gross_floor_area_m2"


def test_group_and_unresolved() -> None:
    c = extract_contract("금정구 용도별 평균 높이")
    assert c.groups
    assert c.aggregations[0].value == "avg"
    d = extract_contract("해운대구 건물을 왜 보여줘")
    assert d.unresolved_spans


def test_conflicting_numeric_and_step02_contracts() -> None:
    c = extract_contract("높이 10m 이상 20m 이하 높이 80m 이상 90m 이하")
    assert c.ranges
    seeds = seed_cases()
    for case in seeds[:9]:
        extracted = extract_contract(case.question)
        assert extracted.places, case.id
        if case.id == "K01":
            assert any(item.value == "sum" for item in extracted.aggregations)
        if case.id == "K06":
            assert any(item.kind == "or" for item in extracted.boolean_ops)
        if case.id == "K07":
            assert extracted.ranges
        if case.id == "K08":
            assert any(item.value == "asc" for item in extracted.order)
