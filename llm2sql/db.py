from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

# 읽기 전용: 데이터 변경/DDL 키워드 차단
_FORBIDDEN = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "create",
    "grant",
    "revoke",
    "copy",
    "call",
    "execute",
    "do",
)

_GEOM_TYPE_NAMES = {"geometry", "geography"}


@contextmanager
def connect(database_url: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        yield conn


def assert_readonly_sql(sql: str) -> None:
    normalized = " ".join(sql.lower().split())
    if not (normalized.startswith("select") or normalized.startswith("with")):
        raise ValueError("SELECT/WITH 쿼리만 허용됩니다.")
    if ";" in normalized.rstrip(";"):
        raise ValueError("한 번에 하나의 SQL문만 허용됩니다.")
    for word in _FORBIDDEN:
        if f" {word} " in f" {normalized} " or normalized.startswith(f"{word} "):
            raise ValueError(f"금지된 키워드가 포함되어 있습니다: {word.upper()}")


def ensure_limit(sql: str, default_limit: int = 100) -> str:
    """집계가 아닌 조회에 LIMIT이 없으면 강제 부여."""
    body = sql.rstrip().rstrip(";")
    lower = body.lower()
    if re.search(r"\blimit\b", lower):
        return body + ";"
    # COUNT/순수 스칼라 집계만 있는 단순 쿼리는 LIMIT 생략 허용
    if re.search(r"\bcount\s*\(", lower) and not re.search(
        r"\bgroup\s+by\b", lower
    ):
        return body + ";"
    return f"{body}\nLIMIT {default_limit};"


def _sanitize_row(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        type_name = type(value).__name__.lower()
        module = type(value).__class__.__module__
        if value is None:
            out[key] = None
        elif "Geometry" in type(value).__name__ or type_name in _GEOM_TYPE_NAMES:
            out[key] = "<geometry omitted>"
        elif module.startswith("shapely") or "WKB" in type(value).__name__.upper():
            out[key] = "<geometry omitted>"
        elif isinstance(value, (memoryview, bytes, bytearray)):
            # WKB 등 바이너리 geometry
            out[key] = "<binary omitted>"
        else:
            out[key] = value
    return out


def execute_query(
    conn: psycopg.Connection,
    sql: str,
    *,
    default_limit: int = 100,
) -> list[dict[str, Any]]:
    assert_readonly_sql(sql)
    sql = ensure_limit(sql, default_limit=default_limit)
    with conn.cursor() as cur:
        cur.execute(sql)
        if cur.description is None:
            return []
        rows = list(cur.fetchall())
        return [_sanitize_row(dict(r)) for r in rows]
