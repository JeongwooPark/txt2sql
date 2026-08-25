from __future__ import annotations

import re

import psycopg

# 대소문자 혼합 물리 테이블명 (미인용 시 소문자로 접힘)
_KNOWN_TABLES = (
    "AL_D010_26_20250704",
    "AL_D060_00_20250804",
    "AL_D198_26260_20250115",
    "AL_D198_26410_20250115",
    "BND_ADM_DONG_PG",
    "TL_KODIS_BAS_26_202507",
    "pnu_def",
)

_KNOWN_COLUMNS = (
    "SIG_KOR_NM",
    "SIG_CD",
    "ADM_NM",
    "ADM_CD",
    "BASE_DATE",
    "BAS_AR",
    "BAS_ID",
    "BAS_MGT_SN",
    "CTP_KOR_NM",
    "MVMN_DE",
    "MVMN_RESN",
    "NTFC_DE",
    "OPERT_DE",
    "PNU",
    "PNU_NM",
)


def load_name_maps(conn: psycopg.Connection) -> tuple[dict[str, str], dict[str, str]]:
    """표시명 → 물리 테이블/컬럼명 맵."""
    tables = {
        row["display_name"]: row["table_name"]
        for row in conn.execute(
            """
            SELECT table_name, display_name
            FROM table_metadata
            WHERE display_name IS NOT NULL AND display_name <> ''
            """
        ).fetchall()
        if row["display_name"]
    }
    counts: dict[str, list[str]] = {}
    for row in conn.execute(
        """
        SELECT column_name, display_name
        FROM column_metadata
        WHERE display_name IS NOT NULL AND display_name <> ''
        """
    ).fetchall():
        counts.setdefault(row["display_name"], []).append(row["column_name"])

    columns: dict[str, str] = {}
    for display, names in counts.items():
        uniq = sorted(set(names))
        if len(uniq) == 1:
            columns[display] = uniq[0]
    return tables, columns


def quote_known_identifiers(sql: str) -> str:
    """미인용 알려진 테이블/컬럼명에 쌍따옴표 부여."""
    from txt2sql.domain import D198_TABLES

    out = sql
    known = list(_KNOWN_TABLES)
    for name in D198_TABLES:
        if name not in known:
            known.append(name)
    for name in sorted(known, key=len, reverse=True):
        pattern = rf'(?<!["\w]){re.escape(name)}(?!["\w])'
        out = re.sub(pattern, f'"{name}"', out, flags=re.IGNORECASE)
    for name in sorted(_KNOWN_COLUMNS, key=len, reverse=True):
        pattern = rf'(?<!["\w]){re.escape(name)}(?!["\w])'
        out = re.sub(pattern, f'"{name}"', out, flags=re.IGNORECASE)
    out = re.sub(
        r'(?<!["\w])(AL_D198_[0-9]+_[0-9]+)(?!["\w])',
        lambda m: f'"{m.group(1)}"',
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r'(?<!["\w])(A\d{1,2})(?!["\w])',
        lambda m: f'"{m.group(1).upper()}"',
        out,
        flags=re.IGNORECASE,
    )
    return out


def rewrite_display_names(sql: str, table_map: dict[str, str], column_map: dict[str, str]) -> str:
    """SQL 내 따옴표 식별자 중 한글 표시명을 물리명으로 치환."""

    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in table_map:
            return f'"{table_map[name]}"'
        if name in column_map:
            return f'"{column_map[name]}"'
        return match.group(0)

    out = re.sub(r'"([^"]+)"', repl, sql)
    out = re.sub(r'"geom"', '"geometry"', out, flags=re.IGNORECASE)
    out = re.sub(r"\.geom\b", ".geometry", out, flags=re.IGNORECASE)
    out = quote_known_identifiers(out)
    return out
