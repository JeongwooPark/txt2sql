"""Physical name isolation for QueryIR."""

import pytest

from txt2sql.query_ir import QueryIR, QueryIRError, assert_no_physical_names, normalize_query_ir
from txt2sql.query_ir.models import MeasureIR, PredicateIR, ScopeIR


def test_rejects_physical_table_in_measure() -> None:
    ir = QueryIR(measures=[MeasureIR(concept="AL_D010")])
    with pytest.raises(QueryIRError):
        normalize_query_ir(ir)


def test_rejects_physical_column() -> None:
    with pytest.raises(QueryIRError):
        assert_no_physical_names({"field": "A16"})


def test_rejects_postgis_and_sql() -> None:
    with pytest.raises(QueryIRError):
        assert_no_physical_names("ST_Intersects(a,b)")
    with pytest.raises(QueryIRError):
        assert_no_physical_names("SELECT * FROM building")


def test_allows_canonical_concepts() -> None:
    ir = QueryIR(
        task="aggregate",
        scope=ScopeIR(place="해운대구"),
        predicates=[PredicateIR(field="building_coverage_ratio", operator="gte", value=60)],
        measures=[MeasureIR(concept="gross_floor_area_m2")],
    )
    out = normalize_query_ir(ir)
    assert out.measures[0].concept == "gross_floor_area_m2"
