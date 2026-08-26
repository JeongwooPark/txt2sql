"""Compiler safety — reuse existing readonly / preexec validators."""

from __future__ import annotations

from typing import Any

from txt2sql.db import assert_readonly_sql
from txt2sql.sql_validator import validate_sql_preexec


def validate_compiled_sql(
    sql: str,
    *,
    question: str = "",
    conn: Any | None = None,
) -> str | None:
    assert_readonly_sql(sql)
    return validate_sql_preexec(question, sql, conn=conn, use_explain=conn is not None)
