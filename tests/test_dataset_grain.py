"""Dataset grain policy tests."""

from __future__ import annotations

from txt2sql.dataset_grain import needs_d198_building_grain, simple_building_usage_count


def test_simple_usage_count_prefers_d010() -> None:
    assert simple_building_usage_count("남구 창고시설 건물 몇 채야?")
    assert not needs_d198_building_grain("남구 창고시설 건물 몇 채야?")


def test_detail_usage_needs_d198() -> None:
    assert needs_d198_building_grain("해운대구 아파트 몇 채야?")
    assert not simple_building_usage_count("해운대구 아파트 몇 채야?")


def test_area_metric_needs_d198() -> None:
    assert needs_d198_building_grain("남구 창고시설 중 연면적 500 이상 건물 몇 채야?")
