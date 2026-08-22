from llm2sql.semantic_catalog.linking import retrieve_tables, retrieve_values
from llm2sql.semantic_catalog.loader import load_bindings
from llm2sql.semantic_catalog.registry import duplicate_bindings, get_binding, get_edge, list_entities


def test_bindings_and_no_duplicates() -> None:
    assert "building" in list_entities()
    assert "industrial_complex" in list_entities()
    assert get_binding("building").table.startswith("AL_D010")
    assert duplicate_bindings() == []
    assert load_bindings()["admin_area"].table == "BND_ADM_DONG_PG"
    get_edge("building_in_admin")


def test_value_margin_can_clarify() -> None:
    result = retrieve_tables("해운대구 공동주택")
    assert result.hits
    values = retrieve_values("아파트")
    assert values.hits
    assert values.hits[0].binding.endswith("공동주택")


def test_poi_without_canonical_name_clarifies() -> None:
    from llm2sql.semantic_catalog.linking import retrieve_poi

    unclear = retrieve_poi("역 근처 아파트")
    assert unclear.clarify is True
    exact = retrieve_poi("부산역")
    assert exact.clarify is False
    assert exact.hits[0].key == "부산역"
