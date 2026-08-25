"""테이블 메타데이터 CSV 양식 생성·파싱."""

from __future__ import annotations

import pytest

from txt2sql.data.csv_meta import (
    build_metadata_csv,
    merge_parsed_with_existing,
    parse_metadata_csv,
)

STRUCTURE = [
    {"column_name": "A0", "data_type": "character varying"},
    {"column_name": "A9", "data_type": "numeric"},
    {"column_name": "geom", "data_type": "geometry"},
]


def _csv(
    *,
    table_name: str = "public.sample_table",
    table_metadata: dict | None = None,
    column_metadata: dict | None = None,
) -> bytes:
    return build_metadata_csv(
        table_name,
        structure=STRUCTURE,
        table_metadata=table_metadata
        or {
            "display_name": "샘플 테이블",
            "description": "설명",
            "category": "건물",
        },
        column_metadata=column_metadata
        or {
            "A0": {"display_name": "고유번호", "description": "키", "unit": ""},
            "A9": {"display_name": "면적", "description": "", "unit": "㎡"},
        },
    )


def test_build_skips_geometry_and_uses_korean_headers() -> None:
    text = _csv().decode("utf-8-sig")
    assert text.startswith("구분,이름,표시명")
    assert "geom" not in text
    assert "테이블,public.sample_table,샘플 테이블" in text
    assert "컬럼,A0,고유번호" in text
    assert "컬럼,A9,면적" in text


def test_roundtrip_korean_headers() -> None:
    parsed = parse_metadata_csv(
        _csv(),
        expected_table="public.sample_table",
        structure=STRUCTURE,
    )
    assert parsed["has_table_row"] is True
    assert parsed["table_metadata"]["display_name"] == "샘플 테이블"
    assert parsed["table_metadata"]["category"] == "건물"
    assert parsed["column_metadata"]["A0"]["display_name"] == "고유번호"
    assert parsed["column_metadata"]["A9"]["unit"] == "㎡"
    assert "geom" not in parsed["column_metadata"]
    assert parsed["skipped_columns"] == []


def test_english_headers_and_short_table_name() -> None:
    raw = (
        "kind,name,display_name,description,category,unit,data_type\r\n"
        "table,sample_table,영문표시,desc,교통,,\r\n"
        "column,A0,Code,id,,,varchar\r\n"
    ).encode("utf-8")
    parsed = parse_metadata_csv(
        raw,
        expected_table="public.sample_table",
        structure=STRUCTURE,
    )
    assert parsed["table_metadata"]["display_name"] == "영문표시"
    assert parsed["column_metadata"]["A0"]["display_name"] == "Code"


def test_wrong_table_name_rejected() -> None:
    with pytest.raises(ValueError, match="선택한 테이블"):
        parse_metadata_csv(
            _csv(table_name="public.other_table"),
            expected_table="public.sample_table",
            structure=STRUCTURE,
        )


def test_unknown_column_skipped_and_missing_table_row_keeps_existing() -> None:
    raw = (
        "구분,이름,표시명,설명,카테고리,단위,자료형\r\n"
        "컬럼,A0,바뀐이름,새설명,,,\r\n"
        "컬럼,missing_col,무시,,,,\r\n"
    ).encode("utf-8-sig")
    parsed = parse_metadata_csv(
        raw,
        expected_table="sample_table",
        structure=STRUCTURE,
    )
    assert parsed["has_table_row"] is False
    assert parsed["skipped_columns"] == ["missing_col"]
    table_meta, columns = merge_parsed_with_existing(
        parsed,
        {
            "table_metadata": {
                "display_name": "기존표시",
                "description": "기존설명",
                "category": "토지",
            }
        },
    )
    assert table_meta["display_name"] == "기존표시"
    assert table_meta["category"] == "토지"
    assert columns["A0"]["display_name"] == "바뀐이름"
    assert "A9" not in columns


def test_formula_prefix_roundtrip() -> None:
    raw = _csv(
        table_metadata={
            "display_name": "샘플",
            "description": "=1+1",
            "category": "기타",
        }
    )
    text = raw.decode("utf-8-sig")
    assert "'=1+1" in text
    parsed = parse_metadata_csv(
        raw,
        expected_table="public.sample_table",
        structure=STRUCTURE,
    )
    assert parsed["table_metadata"]["description"] == "=1+1"
