"""지도 발행용 SQL: 적격 판정, geometry 주입, 집계→행정 경계."""

from __future__ import annotations

import re
from dataclasses import dataclass

from llm2sql.db import assert_readonly_sql
from llm2sql.domain import BUSAN_GU_CODES, extract_gu, extract_place
from llm2sql.spatial_templates import admin_dong_where

_D010 = "AL_D010_26_20250704"
_BND = "BND_ADM_DONG_PG"
_BAS = "TL_KODIS_BAS_26_202507"
_D060 = "AL_D060_00_20250804"

_SKIP_ROUTES = frozenset(
    {
        "guide",
        "coverage",
        "out_of_scope",
        "meta",
        "clarify",
        "clarify_place",
        "clarify_unknown_term",
        "chart_help",
        "chart_render",
        "chart_decline",
        "guide_coverage",
        "followup_no_context",
    }
)

_SPATIAL_TABLES = (
    _D010,
    _BND,
    _BAS,
    _D060,
)

_GEOM_SELECT_RE = re.compile(
    r"\b(?:st_asgeojson\s*\(|st_union\s*\(|\bgeometry\b|\bgeom\b)",
    re.I,
)
_COUNT_RE = re.compile(r"\bcount\s*\(", re.I)
_GROUP_BY_RE = re.compile(r"\bgroup\s+by\b", re.I)
_FEATURE_COL_RE = re.compile(
    r'\b(?:A0|BAS_ID|ADM_CD|ADM_NM|A4)\b',
    re.I,
)
_LIMIT_RE = re.compile(r"\blimit\s+\d+\s*;?\s*$", re.I)
_FROM_RE = re.compile(
    r'(?:from|join)\s+"([^"]+)"(?:\s+(?:as\s+)?([a-zA-Z_][\w]*))?',
    re.I,
)
_SELECT_STAR_RE = re.compile(r"^\s*(?:with\b[\s\S]+?\))?select\s+\*", re.I)


@dataclass(frozen=True)
class MapPlan:
    """발행할 SELECT와 표시 메타."""

    kind: str  # features | boundary
    sql: str
    title: str


def is_map_route(route: str | None) -> bool:
    if not route:
        return True
    if route in _SKIP_ROUTES:
        return False
    if route.startswith("guide"):
        return False
    if route.startswith("chart_"):
        return False
    if route.startswith("clarify"):
        return False
    if route.startswith("meta"):
        return False
    return True


def strip_sql(sql: str) -> str:
    return sql.strip().rstrip(";").strip()


def select_clause(sql: str) -> str:
    body = strip_sql(sql)
    main = _main_select(body)
    lower = main.lower()
    from_at = re.search(r"\bfrom\b", lower)
    if not from_at:
        return main
    return main[: from_at.start()]


def is_aggregate_sql(sql: str) -> bool:
    clause = select_clause(sql)
    if _GROUP_BY_RE.search(sql) and not _GEOM_SELECT_RE.search(clause):
        return True
    if _COUNT_RE.search(clause) and not _FEATURE_COL_RE.search(clause):
        if not _GEOM_SELECT_RE.search(clause):
            return True
    return False


def has_geometry_select(sql: str) -> bool:
    clause = select_clause(sql)
    if _SELECT_STAR_RE.search(strip_sql(sql)):
        return True
    return bool(_GEOM_SELECT_RE.search(clause))


def spatial_aliases(sql: str) -> list[tuple[str, str]]:
    """(table, alias) — 공간 테이블 우선."""
    found: list[tuple[str, str]] = []
    for match in _FROM_RE.finditer(sql):
        table = match.group(1)
        alias = match.group(2) or table
        found.append((table, alias))
    preferred = {name.lower() for name in _SPATIAL_TABLES}
    spatial = [item for item in found if item[0].lower() in preferred or item[0] in _SPATIAL_TABLES]
    return spatial or found


def _geometry_alias(sql: str) -> str | None:
    aliases = spatial_aliases(sql)
    if not aliases:
        return None
    order = (_D010, _D060, _BAS, _BND)
    by_table = {table: alias for table, alias in aliases}
    for table in order:
        if table in by_table:
            return by_table[table]
    return aliases[0][1]


def _main_select(sql: str) -> str:
    body = strip_sql(sql)
    if body.lower().startswith("with"):
        match = re.search(r"\)\s*select\b", body, re.I)
        if match:
            return body[match.start() + 1 :].lstrip()
    return body


def ensure_geometry_select(sql: str, *, map_limit: int = 2000) -> str | None:
    """SELECT에 geometry가 없으면 주 공간 테이블에서 주입한다."""
    try:
        assert_readonly_sql(sql if sql.rstrip().endswith(";") else sql + ";")
    except ValueError:
        return None
    body = strip_sql(sql)
    has_limit = bool(_LIMIT_RE.search(body))
    if has_geometry_select(body):
        return _with_limit(body, map_limit, keep_existing=has_limit)

    alias = _geometry_alias(body)
    if alias is None:
        return None
    main = _main_select(body)
    from_match = re.search(r"\bfrom\b", main, re.I)
    if not from_match:
        return None
    select_head = main[: from_match.start()].rstrip()
    rest = main[from_match.start() :]
    if select_head.lower().endswith(","):
        injected = f"{select_head} {_qual_ident(alias)}.geometry AS geometry\n{rest}"
    else:
        injected = (
            f"{select_head},\n       {_qual_ident(alias)}.geometry AS geometry\n{rest}"
        )
    if body.lower().startswith("with"):
        prefix = body[: len(body) - len(main)]
        injected = prefix + injected
    return _with_limit(injected, map_limit, keep_existing=has_limit)


def _with_limit(sql: str, map_limit: int, *, keep_existing: bool) -> str:
    body = strip_sql(sql)
    if keep_existing and _LIMIT_RE.search(body):
        return body + ";"
    if _LIMIT_RE.search(body):
        return body + ";"
    if _COUNT_RE.search(select_clause(body)) and not _GROUP_BY_RE.search(body):
        return body + ";"
    return f"{body}\nLIMIT {int(map_limit)};"


def boundary_sql(question: str) -> str | None:
    """건수·집계 질의의 필터 영역을 행정 경계로 그린다."""
    place = extract_place(question)
    gu = extract_gu(question)
    if place and str(place).endswith("동"):
        return _dong_boundary_sql(str(place))
    if gu:
        return _gu_boundary_sql(gu)
    if place and (str(place).endswith("구") or str(place).endswith("군")):
        return _gu_boundary_sql(str(place))
    return None


def _dong_boundary_sql(place: str) -> str:
    where = admin_dong_where(place)
    return (
        f'SELECT d."ADM_CD", d."ADM_NM", d.geometry\n'
        f'FROM "{_BND}" d\n'
        f"WHERE {where};"
    )


def _gu_boundary_sql(gu: str) -> str:
    code = BUSAN_GU_CODES.get(gu)
    safe = gu.replace("'", "''")
    if code:
        return (
            f"SELECT '{safe}' AS \"ADM_NM\", ST_Union(d.geometry) AS geometry\n"
            f'FROM "{_BND}" d\n'
            f"WHERE d.\"ADM_CD\" LIKE '{code}%';"
        )
    return (
        f"SELECT d.\"ADM_CD\", d.\"ADM_NM\", d.geometry\n"
        f'FROM "{_BND}" d\n'
        f"WHERE d.\"ADM_NM\" LIKE '{safe}%'\n"
        f"  AND d.\"ADM_CD\" LIKE '21%';"
    )


def plan_map_sql(
    *,
    question: str,
    sql: str | None,
    route: str | None,
    ok: bool,
    map_limit: int = 2000,
) -> MapPlan | None:
    if not ok or not is_map_route(route):
        return None
    title = _title(question, route)
    source = (sql or "").strip()
    if source and not is_aggregate_sql(source):
        wrapped = ensure_geometry_select(source, map_limit=map_limit)
        if wrapped:
            return MapPlan(kind="features", sql=wrapped, title=title)
    boundary = boundary_sql(question)
    if boundary:
        return MapPlan(kind="boundary", sql=boundary, title=title)
    return None


def _qual_ident(alias: str) -> str:
    if re.fullmatch(r"[a-z_][a-z0-9_]*", alias):
        return alias
    return '"' + alias.replace('"', '""') + '"'


def _title(question: str, route: str | None) -> str:
    text = re.sub(r"\s+", " ", (question or "").strip())
    if len(text) > 40:
        text = text[:37] + "…"
    if text:
        return text
    return route or "분석 결과"
