"""테이블 메타데이터 CSV 양식. 엑셀에서 채운 뒤 업로드한다."""

from __future__ import annotations

import csv
import io
from typing import Any

from txt2sql.data.names import is_geometry_column, split_schema_table

# 엑셀에서 바로 읽히도록 한글 헤더를 쓴다. 영문 헤더도 업로드 시 받는다.
HEADER_KO = ("구분", "이름", "표시명", "설명", "카테고리", "단위", "자료형")
_HEADER_ALIASES = {
    "구분": "kind",
    "kind": "kind",
    "이름": "name",
    "name": "name",
    "표시명": "display_name",
    "display_name": "display_name",
    "설명": "description",
    "description": "description",
    "카테고리": "category",
    "category": "category",
    "단위": "unit",
    "unit": "unit",
    "자료형": "data_type",
    "data_type": "data_type",
}
_KIND_ALIASES = {
    "테이블": "table",
    "table": "table",
    "컬럼": "column",
    "column": "column",
}
_FORMULA_PREFIX = ("=", "+", "-", "@", "\t", "\r")


def editable_columns(structure: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for column in structure or []:
        name = str(column.get("column_name") or "")
        dtype = str(column.get("data_type") or "")
        if not name or is_geometry_column(name, dtype):
            continue
        out.append(column)
    return out


def build_metadata_csv(
    table_name: str,
    *,
    structure: list[dict[str, Any]],
    table_metadata: dict[str, Any] | None = None,
    column_metadata: dict[str, Any] | None = None,
    comments: dict[str, Any] | None = None,
) -> bytes:
    """현재 값으로 채운 UTF-8 BOM CSV. 엑셀이 한글을 깨지 않게 한다."""
    table_metadata = table_metadata or {}
    column_metadata = column_metadata or {}
    comments = comments or {}
    col_comments = comments.get("column_comments") or {}
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(HEADER_KO)
    writer.writerow(
        [
            "테이블",
            table_name,
            _csv_cell(table_metadata.get("display_name") or table_name.split(".")[-1]),
            _csv_cell(table_metadata.get("description") or comments.get("table_comment") or ""),
            _csv_cell(table_metadata.get("category") or ""),
            "",
            "",
        ]
    )
    for column in editable_columns(structure):
        name = str(column["column_name"])
        meta = column_metadata.get(name) or {}
        writer.writerow(
            [
                "컬럼",
                name,
                _csv_cell(meta.get("display_name") or ""),
                _csv_cell(meta.get("description") or col_comments.get(name) or ""),
                "",
                _csv_cell(meta.get("unit") or ""),
                column.get("data_type") or meta.get("data_type") or "",
            ]
        )
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def decode_csv_bytes(raw: bytes) -> str:
    if not raw:
        raise ValueError("빈 CSV 파일입니다.")
    for encoding in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("CSV 인코딩을 읽을 수 없습니다. UTF-8 또는 엑셀 CSV로 저장하세요.")


def parse_metadata_csv(
    raw: bytes,
    *,
    expected_table: str,
    structure: list[dict[str, Any]],
    default_schema: str = "public",
) -> dict[str, Any]:
    """업로드 CSV → update_table_metadata 인자. 양식에 없는 컬럼은 건드리지 않는다."""
    text = decode_csv_bytes(raw)
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV 헤더가 없습니다. 양식을 다시 내려받으세요.")
    allowed = {str(item["column_name"]) for item in editable_columns(structure)}
    schema, table = split_schema_table(expected_table, default_schema)
    expected_full = f"{schema}.{table}"
    table_meta: dict[str, str] = {}
    columns: dict[str, dict[str, str]] = {}
    skipped: list[str] = []
    saw_table = False
    for raw_row in reader:
        row = _normalize_row(raw_row)
        kind = _KIND_ALIASES.get(row["kind"].lower(), _KIND_ALIASES.get(row["kind"], ""))
        name = row["name"].strip()
        if not kind or not name:
            continue
        if kind == "table":
            _assert_same_table(name, expected_full, default_schema)
            saw_table = True
            table_meta = {
                "display_name": row["display_name"],
                "description": row["description"],
                "category": row["category"],
            }
            continue
        if kind != "column":
            continue
        if name not in allowed:
            skipped.append(name)
            continue
        dtype = ""
        for item in structure:
            if str(item.get("column_name")) == name:
                dtype = str(item.get("data_type") or "")
                break
        columns[name] = {
            "display_name": row["display_name"],
            "description": row["description"],
            "unit": row["unit"],
            "data_type": row["data_type"] or dtype,
        }
    if not saw_table and not columns:
        raise ValueError("CSV에 테이블 또는 컬럼 행이 없습니다.")
    return {
        "table_name": expected_full,
        "table_metadata": table_meta,
        "column_metadata": columns,
        "skipped_columns": skipped,
        "has_table_row": saw_table,
    }


def merge_parsed_with_existing(
    parsed: dict[str, Any],
    existing: dict[str, Any] | None,
) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """테이블 행이 없으면 기존 테이블 메타를 유지한다. 컬럼은 CSV에 있는 것만 덮어쓴다."""
    existing_table = (existing or {}).get("table_metadata") or {}
    if parsed.get("has_table_row"):
        table_meta = dict(parsed.get("table_metadata") or {})
    else:
        table_meta = {
            "display_name": str(existing_table.get("display_name") or ""),
            "description": str(existing_table.get("description") or ""),
            "category": str(existing_table.get("category") or ""),
        }
    return table_meta, dict(parsed.get("column_metadata") or {})


def csv_download_name(table_name: str) -> str:
    short = (table_name or "table").split(".")[-1]
    return f"{short}_metadata.csv"


def _normalize_row(raw_row: dict[str, Any]) -> dict[str, str]:
    out = {
        "kind": "",
        "name": "",
        "display_name": "",
        "description": "",
        "category": "",
        "unit": "",
        "data_type": "",
    }
    for key, value in (raw_row or {}).items():
        label = (key or "").strip()
        mapped = _HEADER_ALIASES.get(label) or _HEADER_ALIASES.get(label.lower())
        if mapped:
            out[mapped] = _unescape_cell("" if value is None else str(value).strip())
    return out


def _csv_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    if text.startswith(_FORMULA_PREFIX):
        return "'" + text
    return text


def _unescape_cell(text: str) -> str:
    if text.startswith("'") and len(text) > 1 and text[1] in "=+-@\t\r":
        return text[1:]
    return text


def _assert_same_table(csv_name: str, expected_full: str, default_schema: str) -> None:
    has_schema = "." in (csv_name or "").strip()
    try:
        schema, table = split_schema_table(csv_name, default_schema)
    except ValueError as exc:
        raise ValueError(f"CSV 테이블명 '{csv_name}'을 사용할 수 없습니다.") from exc
    exp_schema, exp_table = expected_full.split(".", 1)
    if table != exp_table or (has_schema and schema != exp_schema):
        raise ValueError(
            f"CSV의 테이블({csv_name})이 선택한 테이블({expected_full})과 다릅니다."
        )
