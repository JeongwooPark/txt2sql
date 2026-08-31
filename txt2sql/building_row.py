"""D010 / D198 건물 행 공통 해석 (지번·주소·컬럼 매핑)."""

from __future__ import annotations

import re
from typing import Any

from txt2sql.canonical_physical_columns import D010_FIELD_COLUMNS, D198_FIELD_COLUMNS

_JIBUN_RE = re.compile(r"^\d+(-\d+)?$")


def is_d198_table(table: str | None) -> bool:
    return bool(table and str(table).upper().startswith("AL_D198"))


def field_columns_for_table(table: str | None) -> dict[str, str]:
    if is_d198_table(table):
        return dict(D198_FIELD_COLUMNS)
    return dict(D010_FIELD_COLUMNS)


def infer_row_dataset(
    row: dict[str, Any] | None,
    *,
    table: str | None = None,
    route: str | None = None,
) -> str:
    """행이 D010인지 D198인지 판별. ``d010`` | ``d198``."""
    if is_d198_table(table):
        return "d198"
    if route and str(route).startswith("d198_"):
        return "d198"
    if not row:
        return "d010"
    if row.get("A13") and _looks_like_jibun(row.get("A7")):
        return "d198"
    if row.get("A24") and _looks_like_jibun(row.get("A5")) and not row.get("A7"):
        return "d010"
    if row.get("A30") is not None and row.get("A19") is not None and row.get("A13"):
        return "d198"
    return "d010"


def _looks_like_jibun(value: Any) -> bool:
    text = str(value or "").strip()
    if not text or text.lower() == "nan":
        return False
    return bool(_JIBUN_RE.fullmatch(text))


def row_approval_date(
    row: dict[str, Any],
    *,
    table: str | None = None,
    route: str | None = None,
) -> str:
    dataset = infer_row_dataset(row, table=table, route=route)
    if dataset == "d198":
        lot_col, special_col = "A7", "A6"
    else:
        lot_col, special_col = "A5", "A7"
    lot = str(row.get(lot_col) or "").strip()
    if lot.lower() == "nan":
        lot = ""
    special = str(row.get(special_col) or "").strip()
    if not lot:
        return ""
    if special in ("산", "산지"):
        return f"산{lot}"
    return lot


def row_building_name(
    row: dict[str, Any],
    *,
    table: str | None = None,
    route: str | None = None,
    fallback: str | None = None,
) -> str | None:
    dataset = infer_row_dataset(row, table=table, route=route)
    if dataset == "d198":
        for key in ("A13", "A14"):
            val = row.get(key)
            if val not in (None, "") and str(val).lower() != "nan":
                return str(val).strip()
    else:
        for key in ("A24", "A25"):
            val = row.get(key)
            if val not in (None, "") and str(val).lower() != "nan":
                return str(val).strip()
    return fallback


def row_full_address(
    row: dict[str, Any],
    *,
    table: str | None = None,
    route: str | None = None,
) -> str:
    legal = str(row.get("A4") or "").strip()
    if legal.lower() == "nan":
        legal = ""
    lot = row_lot_address(row, table=table, route=route)
    return " ".join(part for part in (legal, lot) if part)


def row_usage(
    row: dict[str, Any],
    *,
    table: str | None = None,
    route: str | None = None,
) -> Any:
    dataset = infer_row_dataset(row, table=table, route=route)
    if dataset == "d198":
        for key in ("A27", "A25", "A9"):
            val = row.get(key)
            if val not in (None, "") and not (isinstance(val, (int, float)) and val < 10):
                return val
        return row.get("A25") or row.get("A27")
    for key in ("A9", "A25"):
        val = row.get(key)
        if val not in (None, "") and not (isinstance(val, (int, float)) and val < 10):
            return val
    return row.get("A25") or row.get("A9")


def row_height(
    row: dict[str, Any],
    *,
    table: str | None = None,
    route: str | None = None,
) -> Any:
    dataset = infer_row_dataset(row, table=table, route=route)
    return row.get("A30" if dataset == "d198" else "A16")


def row_ground_floors(
    row: dict[str, Any],
    *,
    table: str | None = None,
    route: str | None = None,
) -> Any:
    dataset = infer_row_dataset(row, table=table, route=route)
    return row.get("A31" if dataset == "d198" else "A26")


def row_gross_floor_area(
    row: dict[str, Any],
    *,
    table: str | None = None,
    route: str | None = None,
) -> Any:
    dataset = infer_row_dataset(row, table=table, route=route)
    return row.get("A19" if dataset == "d198" else "A14")


def row_building_area(
    row: dict[str, Any],
    *,
    table: str | None = None,
    route: str | None = None,
) -> Any:
    dataset = infer_row_dataset(row, table=table, route=route)
    return row.get("A18" if dataset == "d198" else "A12")


def row_structure(
    row: dict[str, Any],
    *,
    table: str | None = None,
    route: str | None = None,
) -> Any:
    dataset = infer_row_dataset(row, table=table, route=route)
    return row.get("A23" if dataset == "d198" else "A11")


def row_approval_date(
    row: dict[str, Any],
    *,
    table: str | None = None,
    route: str | None = None,
) -> str:
    dataset = infer_row_dataset(row, table=table, route=route)
    keys = ("A34", "A33") if dataset == "d198" else ("A34", "A33", "A13")
    for key in keys:
        raw = row.get(key)
        if raw in (None, ""):
            continue
        text = str(raw).strip()
        if re.match(r"^\d{4}", text):
            return text
    return ""


def normalize_building_row(
    row: dict[str, Any],
    *,
    table: str | None = None,
    route: str | None = None,
) -> dict[str, Any]:
    """한글 별칭·타 테이블 컬럼명을 물리 컬럼 키로 보강."""
    out = dict(row)
    dataset = infer_row_dataset(row, table=table, route=route)
    cols = D198_FIELD_COLUMNS if dataset == "d198" else D010_FIELD_COLUMNS
    alias_to_field = {
        "연면적": "gross_floor_area_m2",
        "건물면적": "building_area_m2",
        "건축물면적": "building_area_m2",
        "대지면적": "site_area_m2",
        "높이": "height_m",
        "지상층": "ground_floors",
        "지상층수": "ground_floors",
        "법정동명": "legal_dong",
        "법정동": "legal_dong",
        "지번": "lot_address",
        "용도": "usage",
        "건축물용도명": "usage",
        "건물명": "name",
        "건축물id": "building_id",
        "건축물ID": "building_id",
        "건물통합식별번호": "id",
        "gis건물통합식별번호": "id",
    }
    for key, val in list(row.items()):
        field = alias_to_field.get(str(key))
        if field:
            col = cols.get(field)
            if col and col not in out:
                out[col] = val
        compact = str(key).replace(" ", "").lower()
        for alias, mapped in alias_to_field.items():
            if compact == alias.replace(" ", "").lower():
                col = cols.get(mapped)
                if col and col not in out:
                    out[col] = val
    return out


def infer_building_schema_from_columns(columns: list[str] | None) -> str | None:
    if not columns:
        return None
    upper = {str(c).upper() for c in columns}
    if {"A7", "A13", "A30"}.issubset(upper):
        return "d198"
    if {"A5", "A24", "A16"}.issubset(upper) and "A13" not in upper:
        return "d010"
    return None
