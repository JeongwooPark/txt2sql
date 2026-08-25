"""지도 발행용 SQL: 적격 판정, geometry 주입, 집계→행정 경계."""

from __future__ import annotations

import re
from dataclasses import dataclass

from llm2sql.db import assert_readonly_sql
from llm2sql.domain import BUSAN_GU_CODES, extract_gu, extract_place, extract_places, wants_map_display
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
_NON_SPATIAL_TABLES = frozenset(
    {
        "pnu_def",
        "col_def",
        "table_metadata",
        "column_metadata",
        "llm_schema_catalog",
    }
)

_GEOM_SELECT_RE = re.compile(
    r"\b(?:st_asgeojson\s*\(|st_union\s*\(|\bgeometry\b|\bgeom\b)",
    re.I,
)
_D010_FEATURE_COLS = (
    "A0",
    "A4",
    "A5",
    "A9",
    "A12",
    "A14",
    "A16",
    "A24",
    "A26",
)
_BAS_FEATURE_COLS = ("BAS_ID", "SIG_KOR_NM", "BAS_AR")
_SIMPLE_COUNT_RE = re.compile(
    r"^\s*select\s+count\s*\(\s*(?:\*|1)\s*\)(?:\s+as\s+[\"\w]+)?\s*$",
    re.I,
)
_COUNT_RE = re.compile(r"\bcount\s*\(", re.I)
_ORDER_BY_RE = re.compile(r"\border\s+by\b", re.I)
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
_SQL_CLAUSE_WORDS = frozenset(
    {
        "where",
        "on",
        "join",
        "left",
        "right",
        "inner",
        "outer",
        "full",
        "cross",
        "natural",
        "group",
        "order",
        "limit",
        "having",
        "union",
        "intersect",
        "except",
        "fetch",
        "offset",
        "returning",
        "window",
        "using",
        "set",
        "into",
        "and",
        "or",
        "not",
        "as",
    }
)
_DIRECT_STAR_FROM_RE = re.compile(
    r'^\s*select\s+\*\s+from\s+"([^"]+)"',
    re.I,
)
_BUILDING_TABLE_RE = re.compile(r"^AL_D(?:010|198)_", re.I)
_NESTED_FROM_RE = re.compile(r"\bfrom\s*\(", re.I)


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
    """SELECT 목록에 geometry가 있는지. 서브쿼리 SELECT * 는 증거가 아니다."""
    clause = select_clause(sql)
    if _GEOM_SELECT_RE.search(clause):
        return True
    main = _main_select(strip_sql(sql))
    match = _DIRECT_STAR_FROM_RE.match(main)
    if not match:
        return False
    table = match.group(1)
    if table.lower() in {name.lower() for name in _NON_SPATIAL_TABLES}:
        return False
    return True


def spatial_aliases(sql: str) -> list[tuple[str, str]]:
    """(table, alias) — 공간 테이블 우선."""
    found: list[tuple[str, str]] = []
    for match in _FROM_RE.finditer(sql):
        table = match.group(1)
        alias = match.group(2)
        if alias and alias.lower() in _SQL_CLAUSE_WORDS:
            alias = None
        found.append((table, alias or table))
    preferred = {name.lower() for name in _SPATIAL_TABLES}
    skip = {name.lower() for name in _NON_SPATIAL_TABLES}
    spatial = [
        item
        for item in found
        if item[0].lower() in preferred or item[0] in _SPATIAL_TABLES
    ]
    if spatial:
        return spatial
    return [item for item in found if item[0].lower() not in skip] or found


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


def _feature_table_alias(sql: str) -> tuple[str, str] | None:
    """건물·단지·기초구역 등 '대상 피처' 테이블. 행정경계(BND)는 제외한다."""
    aliases = spatial_aliases(sql)
    by_table = {table: alias for table, alias in aliases}
    for name in (_D010, _D060, _BAS):
        if name in by_table:
            return name, by_table[name]
    for table, alias in aliases:
        if table.startswith("AL_D010") or table.startswith("AL_D060"):
            return table, alias
        if table.startswith("TL_KODIS"):
            return table, alias
    return None


def is_simple_count_sql(sql: str) -> bool:
    if _GROUP_BY_RE.search(sql):
        return False
    return bool(_SIMPLE_COUNT_RE.match(select_clause(sql)))


def is_scalar_aggregate_sql(sql: str) -> bool:
    """GROUP BY 없는 COUNT/AVG 등 한 덩어리 집계 (프로필·건수)."""
    if _GROUP_BY_RE.search(sql):
        return False
    return is_aggregate_sql(sql)


def _sql_statements(sql: str) -> list[str]:
    return [part.strip() for part in strip_sql(sql).split(";") if part.strip()]


def _bnd_alias(sql: str) -> str | None:
    for table, alias in spatial_aliases(sql):
        if table == _BND or table.upper().startswith("BND_"):
            return alias
    return None


def count_to_feature_sql(sql: str, *, map_limit: int = 2000) -> str | None:
    """건수·프로필 집계를 같은 필터의 피처 SELECT로 바꾼다. 비교 질의는 UNION ALL."""
    stmts = _sql_statements(sql)
    converted: list[str] = []
    for stmt in stmts:
        one = _one_aggregate_to_features(stmt)
        if one is None:
            continue
        converted.append(one)
    if not converted:
        return None
    if len(converted) == 1:
        body = converted[0]
        if not _ORDER_BY_RE.search(body) and re.search(r'"A14"', body):
            body = f'{body}\nORDER BY "A14" DESC NULLS LAST'
        return _with_limit(body, map_limit, keep_existing=False)
    unioned = (
        "SELECT * FROM (\n"
        + "\nUNION ALL\n".join(converted)
        + '\n) map_features\nORDER BY "A14" DESC NULLS LAST'
    )
    return _with_limit(unioned, map_limit, keep_existing=False)


def _one_aggregate_to_features(sql: str) -> str | None:
    try:
        assert_readonly_sql(sql if sql.rstrip().endswith(";") else sql + ";")
    except ValueError:
        return None
    body = strip_sql(sql)
    if not is_scalar_aggregate_sql(body):
        return None
    found = _feature_table_alias(body)
    if found is None:
        return None
    table, alias = found
    main = _main_select(body)
    from_match = re.search(r"\bfrom\b", main, re.I)
    if not from_match:
        return None
    rest = main[from_match.start() :]
    q = _qual_ident(alias)
    bnd = _bnd_alias(body)
    if bnd:
        extra = f', {_qual_ident(bnd)}."ADM_NM" AS "ADM_NM"'
    else:
        extra = ', NULL::text AS "ADM_NM"'
    if table == _D010 or table.startswith("AL_D010"):
        cols = ", ".join(f'{q}."{c}"' for c in _D010_FEATURE_COLS)
        injected = f"SELECT {cols}{extra},\n       {q}.geometry AS geometry\n{rest}"
    elif table == _BAS or table.startswith("TL_KODIS"):
        cols = ", ".join(f'{q}."{c}"' for c in _BAS_FEATURE_COLS)
        injected = f"SELECT {cols}{extra},\n       {q}.geometry AS geometry\n{rest}"
    else:
        injected = f"SELECT {q}.geometry AS geometry{extra}\n{rest}"
    if body.lower().startswith("with"):
        prefix = body[: len(body) - len(main)]
        injected = prefix + injected
    return strip_sql(injected)


def _main_select(sql: str) -> str:
    body = strip_sql(sql)
    if body.lower().startswith("with"):
        match = re.search(r"\)\s*select\b", body, re.I)
        if match:
            return body[match.start() + 1 :].lstrip()
    return body


def _needs_subquery_geom_wrap(sql: str) -> bool:
    """바깥 FROM이 서브쿼리이거나 WITH CTE면 컬럼 주입이 스코프 밖이다."""
    if strip_sql(sql).lower().startswith("with"):
        return True
    return bool(_NESTED_FROM_RE.search(_main_select(sql)))


def _quoted_tables(sql: str) -> list[str]:
    return [match.group(1) for match in _FROM_RE.finditer(sql)]


def _wrap_join_geometry(body: str) -> str | None:
    """결과 행을 서브쿼리로 감싸 공간 테이블 geometry를 붙인다."""
    tables = _quoted_tables(body)
    has_building = any(_BUILDING_TABLE_RE.match(name) for name in tables)
    has_a0 = bool(re.search(r'"A0"', body))
    has_parcel = bool(re.search(r'"A4"', body) and re.search(r'"A5"', body))
    if has_building and (has_a0 or has_parcel):
        return _d010_geom_wrap(body, has_a0=has_a0, has_parcel=has_parcel)

    has_adm = bool(re.search(r'"ADM_CD"', body))
    if has_adm and any(name == _BND or name.upper().startswith("BND_") for name in tables):
        return (
            f'SELECT q.*, src.geometry AS geometry\n'
            f"FROM (\n{body}\n) q\n"
            f'LEFT JOIN "{_BND}" src ON src."ADM_CD" = q."ADM_CD"'
        )

    has_bas = bool(re.search(r'"BAS_ID"', body))
    if has_bas and any(name == _BAS or name.upper().startswith("TL_KODIS") for name in tables):
        return (
            f'SELECT q.*, src.geometry AS geometry\n'
            f"FROM (\n{body}\n) q\n"
            f'LEFT JOIN "{_BAS}" src ON src."BAS_ID" = q."BAS_ID"'
        )
    return None


def _d010_geom_wrap(body: str, *, has_a0: bool, has_parcel: bool) -> str:
    """D010 A0 우선, 없으면 지번(A4+A5)으로 건물 폴리곤을 붙인다."""
    if has_a0 and not has_parcel:
        return (
            f'SELECT q.*, src.geometry AS geometry\n'
            f"FROM (\n{body}\n) q\n"
            f'LEFT JOIN "{_D010}" src ON src."A0"::text = q."A0"::text'
        )
    preds: list[str] = []
    order = "1"
    if has_a0:
        preds.append('s."A0"::text = q."A0"::text')
        order = 'CASE WHEN s."A0"::text = q."A0"::text THEN 0 ELSE 1 END'
    if has_parcel:
        preds.append(
            '(s."A4" IS NOT DISTINCT FROM q."A4" '
            'AND s."A5" IS NOT DISTINCT FROM q."A5")'
        )
    where = " OR ".join(preds)
    return (
        f'SELECT q.*, src.geometry AS geometry\n'
        f"FROM (\n{body}\n) q\n"
        f"LEFT JOIN LATERAL (\n"
        f"  SELECT s.geometry\n"
        f'  FROM "{_D010}" s\n'
        f"  WHERE {where}\n"
        f"  ORDER BY {order}\n"
        f"  LIMIT 1\n"
        f") src ON TRUE"
    )


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

    # 바깥 FROM이 서브쿼리/CTE면 alias.geometry 주입은 스코프 밖이다.
    # 건물명 조회(SELECT * FROM (DISTINCT ON … UNION …))가 이 형태다.
    if _needs_subquery_geom_wrap(body):
        wrapped = _wrap_join_geometry(body)
        if wrapped:
            try:
                assert_readonly_sql(
                    wrapped if wrapped.rstrip().endswith(";") else wrapped + ";"
                )
            except ValueError:
                return None
            return _with_limit(wrapped, map_limit, keep_existing=False)
        return None

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
    multi = gu_boundary_union_sql(question)
    if multi:
        return multi
    place = extract_place(question)
    gu = extract_gu(question)
    if place and str(place).endswith("동"):
        return _dong_boundary_sql(str(place))
    if gu:
        return _gu_boundary_sql(gu)
    if place and (str(place).endswith("구") or str(place).endswith("군")):
        return _gu_boundary_sql(str(place))
    return None


def gu_boundary_union_sql(question: str) -> str | None:
    """질문의 구·군만 있을 때 경계 UNION. 동이 섞이면 None (건물 피처 유지)."""
    places = extract_places(question)
    if not places:
        gu = extract_gu(question)
        places = [gu] if gu else []
    if not places:
        return None
    if any(str(p).endswith("동") for p in places):
        return None
    gus = [p for p in places if str(p).endswith(("구", "군"))]
    if not gus:
        return None
    parts = [strip_sql(_gu_boundary_sql(g)) for g in gus[:3]]
    return "\nUNION ALL\n".join(parts) + ";"


def _dong_boundary_sql(place: str) -> str:
    where = admin_dong_where(place)
    return (
        f'SELECT d."ADM_CD", d."ADM_NM", d.geometry\n'
        f'FROM "{_BND}" d\n'
        f"WHERE {where};"
    )


def _gu_boundary_sql(gu: str) -> str:
    """구 경계. BND ADM_CD는 센서스(21…)라 법정동코드(26410)와 안 맞는다.

    기초구역 SIG_CD(26410)·시군구명으로 합집합을 만든다.
    """
    code = BUSAN_GU_CODES.get(gu)
    safe = gu.replace("'", "''")
    geom = (
        "ST_Multi(ST_CollectionExtract("
        "ST_MakeValid(ST_UnaryUnion(ST_Collect(t.geometry))), 3))"
    )
    if code:
        where = f't."SIG_CD" = \'{code}\''
        sig = f"'{code}'"
    else:
        where = f't."SIG_KOR_NM" = \'{safe}\''
        sig = "NULL"
    return (
        f"SELECT '{safe}' AS \"SIG_KOR_NM\", {sig} AS \"SIG_CD\",\n"
        f"       {geom} AS geometry\n"
        f'FROM "{_BAS}" t\n'
        f"WHERE {where} AND t.geometry IS NOT NULL"
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
    if _profile_prefers_gu_boundary(route, question):
        bounds = gu_boundary_union_sql(question) or boundary_sql(question)
        if bounds:
            return MapPlan(kind="boundary", sql=bounds, title=title)
    source = (sql or "").strip()
    display = wants_map_display(question) or route == "building_map_display"
    if display and source:
        if is_aggregate_sql(source):
            features = count_to_feature_sql(source, map_limit=map_limit)
            if features:
                return MapPlan(kind="features", sql=features, title=title)
        stripped = _LIMIT_RE.sub("", strip_sql(source)).strip()
        wrapped = ensure_geometry_select(stripped, map_limit=map_limit)
        if wrapped:
            return MapPlan(kind="features", sql=wrapped, title=title)
    if source and not is_aggregate_sql(source):
        wrapped = ensure_geometry_select(source, map_limit=map_limit)
        if wrapped:
            return MapPlan(kind="features", sql=wrapped, title=title)
    # 건수 질의라도 지도에는 대상 건물(아파트 등)을 그린다. 동·구 경계는 최후 수단.
    if source:
        features = count_to_feature_sql(source, map_limit=map_limit)
        if features:
            return MapPlan(kind="features", sql=features, title=title)
    boundary = boundary_sql(question)
    if boundary:
        return MapPlan(kind="boundary", sql=boundary, title=title)
    return None


def map_scope_key(sql: str | None) -> str:
    """지도에 그릴 대상(FROM·JOIN·WHERE) 지문. SELECT 목록·LIMIT 차이는 무시한다."""
    body = strip_sql(sql or "")
    if not body:
        return ""
    wrapped = re.search(
        r"\bfrom\s*\(\s*(.*?)\s*\)\s*(?:as\s+)?q\b",
        body,
        flags=re.I | re.S,
    )
    if wrapped:
        body = strip_sql(wrapped.group(1))
    main = _main_select(body)
    from_at = re.search(r"\bfrom\b", main, re.I)
    rest = main[from_at.start() :] if from_at else main
    rest = _LIMIT_RE.sub("", rest)
    rest = re.sub(r"\s+order\s+by\b[\s\S]*$", "", rest, flags=re.I)
    return re.sub(r"\s+", " ", rest).strip().lower()


# 단일 건물 bbox가 너무 작을 때 fit이 과확대되지 않도록 (~330m @ 위도 35°)
_MIN_EXTENT_SPAN_DEG = 0.003


def pad_lonlat_extent(
    extent: list[float] | None,
    *,
    min_span: float = _MIN_EXTENT_SPAN_DEG,
    margin: float = 0.15,
) -> list[float] | None:
    """작은 피처도 화면에 들어오도록 lon/lat bbox에 최소 폭과 여백을 준다."""
    if not extent or len(extent) != 4:
        return extent
    try:
        minx, miny, maxx, maxy = (float(extent[0]), float(extent[1]), float(extent[2]), float(extent[3]))
    except (TypeError, ValueError):
        return extent
    if maxx < minx:
        minx, maxx = maxx, minx
    if maxy < miny:
        miny, maxy = maxy, miny
    span = max(float(min_span), 0.0)
    if maxx - minx < span:
        mid = (minx + maxx) / 2.0
        minx, maxx = mid - span / 2.0, mid + span / 2.0
    if maxy - miny < span:
        mid = (miny + maxy) / 2.0
        miny, maxy = mid - span / 2.0, mid + span / 2.0
    pad_x = (maxx - minx) * float(margin)
    pad_y = (maxy - miny) * float(margin)
    return [minx - pad_x, miny - pad_y, maxx + pad_x, maxy + pad_y]


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


_PROFILE_BOUNDARY_ROUTES = frozenset(
    {
        "building_profile",
        "building_profile_compare",
    }
)


def _profile_prefers_gu_boundary(route: str | None, question: str) -> bool:
    """구 전체 특성·비교는 건물 전체를 올리지 않고 구 경계만 그린다."""
    if route not in _PROFILE_BOUNDARY_ROUTES:
        return False
    places = extract_places(question)
    if not places:
        gu = extract_gu(question)
        places = [gu] if gu else []
    if not places:
        return False
    return all(str(p).endswith(("구", "군")) for p in places)
