"""D010 SQL에 D198 전용 컬럼이 붙지 않게 고치거나 거절한다."""

from __future__ import annotations

import re


_D198_ON_D010 = (
    (r'"A34"', '"A13"'),
    (r'"A33"', '"A13"'),
    (r'"A30"', '"A16"'),
    (r'"A31"', '"A26"'),
)
_DECADE_BETWEEN = re.compile(
    r'"A13"\s+BETWEEN\s+\'(\d{4})-01-01\'\s+AND\s+\'\1-12-31\'',
    re.I,
)


def uses_d010_only(sql: str) -> bool:
    text = sql or ""
    return "AL_D010" in text and "AL_D198" not in text


def rewrite_d198_columns_on_d010(sql: str, question: str | None = None) -> str:
    """D010 전용 SQL의 A34/A30/A31을 D010 컬럼으로 옮긴다. 년대는 10년 구간."""
    if not uses_d010_only(sql):
        return sql
    out = sql
    for pattern, repl in _D198_ON_D010:
        out = re.sub(pattern, repl, out)
    if question and "년대" in question:
        out = _DECADE_BETWEEN.sub(_decade_year_between, out)
    return out


def _decade_year_between(match: re.Match[str]) -> str:
    year = int(match.group(1))
    return (
        "LEFT(regexp_replace(\"A13\"::text, '[^0-9]', '', 'g'), 4)::int "
        f"BETWEEN {year} AND {year + 9}"
    )


def d010_has_d198_columns(sql: str) -> bool:
    if not uses_d010_only(sql):
        return False
    return bool(re.search(r'"(A33|A34|A30)"', sql or ""))
