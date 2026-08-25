"""데이터 관리용 식별자·테이블 코드 해석 (llm2_geodb와 동일 규칙)."""

from __future__ import annotations

import re

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_GEOM_NAMES = {"geometry", "geom", "the_geom", "shape", "geography"}
_PROTECTED = {
    "table_metadata",
    "column_metadata",
    "llm_schema_catalog",
    "col_def",
    "pnu_def",
    "spatial_ref_sys",
    "geometry_columns",
    "geography_columns",
    "raster_columns",
    "raster_overviews",
}


def is_safe_ident(name: str) -> bool:
    return bool(_IDENT.fullmatch(name or ""))


def is_protected_table(name: str) -> bool:
    short = (name or "").split(".")[-1].lower()
    return short in _PROTECTED or short.startswith("temp_")


def is_geometry_column(name: str, data_type: str = "") -> bool:
    n = (name or "").lower()
    dtype = (data_type or "").lower()
    if n in _GEOM_NAMES:
        return True
    if dtype in {"geometry", "geography", "raster"}:
        return True
    if dtype == "user-defined" and n in _GEOM_NAMES:
        return True
    return False


def split_schema_table(name: str, default_schema: str = "public") -> tuple[str, str]:
    raw = (name or "").strip()
    if "." in raw:
        schema, table = raw.split(".", 1)
    else:
        schema, table = default_schema, raw
    schema = schema.strip()
    table = table.strip()
    if not is_safe_ident(schema) or not is_safe_ident(table):
        raise ValueError("허용되지 않은 테이블명입니다.")
    if is_protected_table(table):
        raise ValueError("시스템·임시 테이블은 데이터 관리 대상이 아닙니다.")
    return schema, table


def table_from_shapefile(filename: str) -> str:
    stem = (filename or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if "." in stem:
        stem = stem.rsplit(".", 1)[0]
    stem = re.sub(r"[^A-Za-z0-9_]", "_", stem)
    stem = re.sub(r"_+", "_", stem).strip("_")
    if not is_safe_ident(stem) or is_protected_table(stem):
        raise ValueError("Shapefile 파일명에서 안전한 테이블명을 만들 수 없습니다.")
    return stem


def extract_display_name_and_unit(col_kor_nm: str) -> tuple[str, str]:
    if not col_kor_nm:
        return "", ""
    display_name = col_kor_nm
    unit = ""
    if "(" in col_kor_nm and ")" in col_kor_nm:
        start = col_kor_nm.find("(")
        end = col_kor_nm.find(")")
        if start < end:
            unit = col_kor_nm[start + 1 : end]
            display_name = col_kor_nm[:start].strip()
    elif col_kor_nm.endswith("수"):
        unit = "수"
        display_name = re.sub(r"[\s_\-]+$", "", col_kor_nm[:-1])
        display_name = re.sub(r"\s{2,}", " ", display_name)
    return display_name, unit


def _is_nan_like(value: object) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    if not text:
        return True
    return text.lower() in {"nan", "nat", "none", "null"}


def create_column_description(sample: object, etc: object) -> str:
    parts: list[str] = []
    if not _is_nan_like(sample):
        parts.append(f"예시: {str(sample).strip()}")
    if not _is_nan_like(etc):
        parts.append(f"보조 설명: {str(etc).strip()}")
    return ", ".join(parts)


def parse_al_table_name(table: str) -> dict[str, str] | None:
    """AL_D010_26_20250704 형태를 데이터코드·PNU·갱신일로 분해한다."""
    parts = (table or "").split("_")
    if len(parts) < 4:
        return None
    data_code = f"{parts[0]}_{parts[1]}"
    pnu_code = parts[2]
    update_date = parts[3]
    if not (len(update_date) == 8 and update_date.isdigit()):
        return None
    formatted = ""
    if len(update_date) == 8 and update_date.isdigit():
        formatted = f"{update_date[:4]}년 {update_date[4:6]}월 {update_date[6:8]}일"
    return {
        "data_code": data_code,
        "pnu_code": pnu_code,
        "update_date": update_date,
        "formatted_date": formatted,
    }
