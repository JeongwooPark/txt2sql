from xml.etree import ElementTree as ET

import pytest

from llm2sql.map.choropleth import (
    PALETTES,
    ChoroplethError,
    _is_numeric_type,
    _stats_from_row,
    build_sld,
    equal_interval_edges,
    is_identifier_field,
    jenks_edges,
    legend_spec,
    manual_edges,
    normalize_hex,
    palette_colors,
    style_name_for,
)


def test_numeric_fields_only() -> None:
    assert _is_numeric_type("double precision", "float8")
    assert _is_numeric_type("integer", "int4")
    assert _is_numeric_type("numeric", "numeric")
    assert not _is_numeric_type("text", "text")
    assert not _is_numeric_type("character varying", "varchar")
    assert not _is_numeric_type("USER-DEFINED", "geometry")
    assert not _is_numeric_type("USER-DEFINED", "geography")


def test_identifier_fields_rank_behind_metrics() -> None:
    assert is_identifier_field("sgis_cd")
    assert is_identifier_field("ADM_CD", "행정동 코드")
    assert not is_identifier_field("urban_pc", "활동인구 1인당 시가화용지 면적")


def test_stats_with_nulls() -> None:
    stats = _stats_from_row(
        {
            "count": 10,
            "valid_count": 7,
            "null_count": 3,
            "min": 1.5,
            "max": 9.0,
            "mean": 4.2,
            "median": 4.0,
            "unique_count": 7,
        }
    )
    assert stats["count"] == 10
    assert stats["valid_count"] == 7
    assert stats["null_count"] == 3
    assert stats["min"] == 1.5
    assert stats["null_count"] + stats["valid_count"] == stats["count"]


def test_equal_interval_breaks() -> None:
    edges, _msg = equal_interval_edges(0.0, 100.0, 5)
    assert edges[0] == 0.0
    assert edges[-1] == 100.0
    assert len(edges) == 6
    assert edges[1] == pytest.approx(20.0)


def test_equal_interval_constant_values() -> None:
    edges, _msg = equal_interval_edges(3.0, 3.0, 5)
    assert edges == [3.0, 3.0]


def test_quantile_duplicate_values() -> None:
    from llm2sql.map.choropleth import _dedupe_edges

    edges = _dedupe_edges([1.0, 1.0, 1.0, 5.0, 5.0, 9.0])
    assert edges == [1.0, 5.0, 9.0]


def test_jenks_breaks() -> None:
    values = [1, 1, 2, 2, 2, 10, 11, 12, 100, 110, 120]
    edges, _msg = jenks_edges(values, 3, min(values), max(values))
    assert edges[0] == 1
    assert edges[-1] == 120
    assert 2 <= len(edges) - 1 <= 3


def test_jenks_empty_values() -> None:
    with pytest.raises(ChoroplethError):
        jenks_edges([], 5, None, None)


def test_manual_breaks() -> None:
    edges = manual_edges([50, 100, 150, 200], 0.0, 300.0)
    assert edges[0] == 0.0
    assert edges[-1] == 300.0
    assert 50 in edges and 200 in edges


def test_manual_breaks_rejects_unsorted() -> None:
    with pytest.raises(ChoroplethError):
        manual_edges([100, 50], 0.0, 200.0)


def test_duplicate_values_reduce_classes() -> None:
    edges, msg = equal_interval_edges(1.0, 2.0, 5, unique_count=2)
    assert len(edges) - 1 == 2
    assert "2개 구간" in msg


def test_constant_values() -> None:
    edges, _msg = jenks_edges([4.0, 4.0, 4.0], 5, 4.0, 4.0)
    assert edges == [4.0, 4.0]


def test_empty_values() -> None:
    with pytest.raises(ChoroplethError):
        jenks_edges([], 5, 0.0, 1.0)


def test_palette_class_count_and_reverse() -> None:
    colors = palette_colors("YlOrRd", 5)
    assert len(colors) == 5
    assert colors == PALETTES["YlOrRd"][5]
    reversed_colors = palette_colors("YlOrRd", 5, reverse=True)
    assert reversed_colors == list(reversed(colors))
    null_independent = palette_colors("Blues", 4)
    assert "#BDBDBD" not in null_independent


def test_invalid_hex_blocked() -> None:
    with pytest.raises(ChoroplethError):
        normalize_hex("red")
    with pytest.raises(ChoroplethError):
        normalize_hex("#gg0000")
    assert normalize_hex("#BDBDBD") == "#bdbdbd"


def test_style_name_is_safe() -> None:
    name = style_name_for("adm_urban_area_per_capita", "urban_pc")
    assert name.startswith("choropleth__")
    assert name == "choropleth__adm_urban_area_per_capita__urban_pc"
    long_name = style_name_for("a" * 80, "b" * 80)
    assert len(long_name) <= 80
    assert long_name.startswith("choropleth__")


def _classification() -> dict:
    return {
        "layer": "adm_urban_area_per_capita",
        "field": "urban_pc",
        "field_display_name": "활동인구 1인당 시가화용지 면적",
        "unit": "㎡/명",
        "method": "jenks",
        "classes": 3,
        "min": 7.88,
        "max": 100.0,
        "null_count": 2,
        "valid_count": 8,
        "breaks": [
            {"min": 7.88, "max": 20.0, "color": "#ffffcc"},
            {"min": 20.0, "max": 50.0, "color": "#78c679"},
            {"min": 50.0, "max": 100.0, "color": "#006837"},
        ],
        "null_color": "#BDBDBD",
        "stroke": "#666666",
        "stroke_width": 0.7,
        "fill_opacity": 0.8,
        "reverse": False,
    }


def test_sld_is_valid_xml() -> None:
    xml = build_sld(_classification())
    root = ET.fromstring(xml)
    assert "StyledLayerDescriptor" in root.tag


def test_sld_rule_count() -> None:
    xml = build_sld(_classification())
    root = ET.fromstring(xml)
    ns = {"sld": "http://www.opengis.net/sld"}
    rules = root.findall(".//sld:Rule", ns)
    assert len(rules) == 4


def test_sld_last_class_inclusive() -> None:
    xml = build_sld(_classification())
    assert "PropertyIsLessThanOrEqualTo" in xml
    assert xml.count("<ogc:PropertyIsLessThan>") == 2
    assert xml.count("<ogc:PropertyIsLessThanOrEqualTo>") == 1


def test_sld_has_null_rule() -> None:
    xml = build_sld(_classification())
    assert "PropertyIsNull" in xml
    assert "urban_pc" in xml
    assert "#BDBDBD".lower() in xml.lower() or "#bdbdbd" in xml.lower()


def test_sld_escapes_xml() -> None:
    cls = _classification()
    cls["field"] = "urban_pc"
    cls["layer"] = "adm_urban_area_per_capita"
    xml = build_sld(cls)
    assert "<script" not in xml


def test_invalid_column_rejected_in_sld() -> None:
    cls = _classification()
    cls["field"] = "urban pc;drop"
    with pytest.raises(ChoroplethError):
        build_sld(cls)


def test_legend_spec() -> None:
    legend = legend_spec(_classification())
    assert legend["title"] == "활동인구 1인당 시가화용지 면적"
    assert legend["unit"] == "㎡/명"
    assert legend["items"][-1]["label"] == "데이터 없음"
    assert len(legend["items"]) == 4
