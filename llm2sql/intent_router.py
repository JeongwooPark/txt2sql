"""고빈도 GIS 질의 패턴을 규칙으로 해석해 SQL을 직접 생성한다."""

from __future__ import annotations

import re
from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row

from llm2sql.d198_attrs import (
    D198_SELECT_COLS,
    ValueBinSpec,
    YearStatsSpec,
    parse_d198_question,
    parse_value_bin,
    parse_year_stats,
    rank_sane_sql,
    value_bin_sane_sql,
)
from llm2sql.domain import (
    D198_TABLES,
    DONG_PATTERN,
    GU_PATTERN,
    LENGTH_DIST_PATTERN,
    _NAME_STOP,
    age_date_predicate,
    busan_gu_code,
    calendar_year_predicate_sql,
    d198_table_for_gu,
    extract_age_compare,
    extract_age_years,
    extract_building_name_candidate,
    extract_gu,
    extract_place,
    extract_special_land,
    extract_structure,
    extract_usage,
    is_busan_wide,
    legal_dong_guess,
    looks_like_age_question,
    looks_like_building_name_lookup,
    looks_like_measure_threshold,
    wants_map_display,
    _FALSE_DONG,
    place_a4_predicate,
    sane_floor_area_sql,
    sane_footprint_sql,
    sane_height_sql,
)
from llm2sql.spatial_templates import (
    place_buffer_count_sql,
    place_buffer_list_sql,
    scoped_count_sql,
    scoped_list_sql,
)
from llm2sql.spatial_router import try_spatial_route
from llm2sql.units import UNIT_TOKEN, convert_for_schema, pyeong_threshold, sql_number


@dataclass(frozen=True)
class RoutedQuery:
    intent: str
    sql: str


_GU = GU_PATTERN
_DONG = DONG_PATTERN
_COUNT_HINT = ("몇", "개수", "건수", "채", "수", "세어", "구해", "알려", "조회", "얼마")
_LIST_HINT = (
    "무엇이 있어",
    "뭐가 있어",
    "뭐 있어",
    "어떤 게 있어",
    "어떤것이 있어",
    "어떤 것이 있어",
    "목록",
    "리스트",
)


def _wants_count(q: str) -> bool:
    # 순위·최댓값 질의는 건수가 아님
    if any(k in q for k in ("가장", "제일", "최대", "상위", "1등", "큰 순", "높은 순")):
        return False
    if any(k in q for k in _COUNT_HINT):
        return True
    # "해운대구 건물?"처럼 짧은 물음만 건수로 간주
    stripped = q.rstrip()
    if stripped.endswith(("?", "？")) and len(stripped) <= 24:
        return True
    return False


def _wants_list(q: str) -> bool:
    return any(k in q for k in _LIST_HINT)


_D010 = "AL_D010_26_20250704"


def _usage_kind_specs() -> list[tuple[str, str, str, str]]:
    from llm2sql.domain import D198_BY_GU

    specs: list[tuple[str, str, str, str]] = []
    for gu, table in D198_BY_GU.items():
        stem = gu.replace("구", "").replace("군", "")
        key = stem if len(stem) >= 2 else gu
        specs.append((key, f"usage_kinds_{stem or gu}", table, gu))
    return specs


def _swap_d198_for_d010(sql: str) -> str:
    return re.sub(r"AL_D198_[0-9]+_[0-9]+", _D010, sql)


def _count_sql(intent: str, table: str, where: str) -> RoutedQuery:
    return RoutedQuery(
        intent,
        f'SELECT COUNT(*) AS cnt\nFROM "{table}"\nWHERE {where};',
    )


def _a4_place_filters(place: str | None, gu: str | None) -> list[str]:
    from llm2sql.gazetteer import is_legal_dong, uses_admin_boundary

    where: list[str] = []
    if place and uses_admin_boundary(place):
        if gu:
            where.append(f'"A4" LIKE \'%{gu}%\'')
        return where
    if place and is_legal_dong(place):
        where.append(place_a4_predicate(place))
        if gu:
            where.append(f'"A4" LIKE \'%{gu}%\'')
    elif gu:
        where.append(f'"A4" LIKE \'%{gu}%\'')
    elif place:
        where.append(place_a4_predicate(place))
    return where


def _d198_select_list() -> str:
    cols = ", ".join(f'"{c}"' for c in D198_SELECT_COLS)
    return f"SELECT {cols}"


def _d198_year_stats_sql(
    tables: list[str],
    where_sql: str,
    stats: YearStatsSpec,
) -> RoutedQuery:
    date_col = stats.date_col
    year_expr = f"SUBSTRING(\"{date_col}\" FROM 1 FOR 4)"
    bin_years = getattr(stats, "bin_years", 1) or 1
    if stats.mode == "decade" or bin_years == 10:
        period_expr = f"(FLOOR(({year_expr})::int / 10) * 10)::int"
        alias = "decade"
    elif stats.mode == "bin" or bin_years > 1:
        period_expr = (
            f"(FLOOR(({year_expr})::int / {bin_years}) * {bin_years})::int"
        )
        alias = "period"
    else:
        period_expr = f"({year_expr})::int"
        alias = "year"
    extra = [where_sql, f"{year_expr} ~ '^[0-9]{{4}}$'"]
    if stats.mode == "decade" and stats.decades:
        ins = ", ".join(str(d) for d in stats.decades)
        extra.append(f"{period_expr} IN ({ins})")
    where = " AND ".join(p for p in extra if p and p != "TRUE")

    def one(tbl: str) -> str:
        return (
            f'SELECT {period_expr} AS {alias}, COUNT(*) AS n\n'
            f'FROM "{tbl}"\n'
            f"WHERE {where}\n"
            f"GROUP BY 1"
        )

    if len(tables) == 1:
        sql = f"{one(tables[0])}\nORDER BY 1;"
    else:
        inner = "\nUNION ALL\n".join(one(t) for t in tables)
        sql = (
            f"SELECT {alias}, SUM(n) AS n\n"
            f"FROM (\n{inner}\n) AS year_parts\n"
            f"GROUP BY 1\n"
            f"ORDER BY 1;"
        )
    return RoutedQuery("d198_year_stats", sql)


def _d198_value_bin_sql(
    tables: list[str],
    where_sql: str,
    spec: ValueBinSpec,
) -> RoutedQuery:
    col = spec.col
    width = spec.bin_width
    wsql = str(int(width)) if float(width).is_integer() else f"{width:g}"
    period_expr = f'(FLOOR("{col}" / {wsql}) * {wsql})::int'
    extra = [where_sql, value_bin_sane_sql(col)]
    where = " AND ".join(p for p in extra if p and p != "TRUE")

    def one(tbl: str) -> str:
        return (
            f"SELECT {period_expr} AS period, COUNT(*) AS n\n"
            f'FROM "{tbl}"\n'
            f"WHERE {where}\n"
            f"GROUP BY 1"
        )

    if len(tables) == 1:
        sql = f"{one(tables[0])}\nORDER BY 1;"
    else:
        inner = "\nUNION ALL\n".join(one(t) for t in tables)
        sql = (
            "SELECT period, SUM(n) AS n\n"
            f"FROM (\n{inner}\n) AS value_parts\n"
            "GROUP BY 1\n"
            "ORDER BY 1;"
        )
    return RoutedQuery("d198_value_bins", sql)


def _route_d198_attr(
    q: str,
    *,
    conn: psycopg.Connection | None,
) -> RoutedQuery | None:
    """용도별건물공간정보(AL_D198) 속성 필터·목록·건수·순위."""
    parsed = parse_d198_question(q)
    if parsed is None:
        return None
    gu = extract_gu(q)
    place = extract_place(q)
    table = _resolve_d198_table(q, conn=conn, gu=gu, place=place)
    if table:
        tables = [table]
    elif (
        parsed.dataset_hint
        or parse_year_stats(q) is not None
        or parse_value_bin(q) is not None
    ):
        tables = list(D198_TABLES)
    else:
        return None

    where = list(_a4_place_filters(place, gu))
    where.extend(parsed.filters)
    if parsed.rank and parsed.order_col:
        sane = rank_sane_sql(parsed.order_col)
        if sane:
            where.append(sane)
    where_sql = " AND ".join(where) if where else "TRUE"
    vbin = parse_value_bin(q)
    if vbin is not None:
        return _d198_value_bin_sql(tables, where_sql, vbin)
    stats = parse_year_stats(q)
    if stats is not None:
        return _d198_year_stats_sql(tables, where_sql, stats)

    order_col = parsed.order_col or "A19"
    order_dir = "ASC" if parsed.order_asc else "DESC"
    select = _d198_select_list()

    if parsed.rank:
        limit = 1
        intent = "d198_attr_rank"
    elif parsed.lookup:
        limit = 20
        intent = "d198_attr_lookup"
    elif _wants_threshold_list(q) or not any(k in q for k in _AREA_COUNTISH):
        limit = 100
        intent = "d198_attr_list"
    else:
        intent = "d198_attr_count"
        if len(tables) == 1:
            return _count_sql(intent, tables[0], where_sql)
        parts = [
            f'SELECT COUNT(*) AS c FROM "{t}" WHERE {where_sql}' for t in tables
        ]
        sql = (
            "SELECT COALESCE(SUM(c), 0) AS cnt\n"
            "FROM (\n  "
            + "\n  UNION ALL\n  ".join(parts)
            + "\n) AS d198_parts;"
        )
        return RoutedQuery(intent, sql)

    def list_sql(tbl: str, n: int) -> str:
        return (
            f"{select}\n"
            f'FROM "{tbl}"\n'
            f"WHERE {where_sql}\n"
            f'ORDER BY "{order_col}" {order_dir} NULLS LAST\n'
            f"LIMIT {n};"
        )

    if len(tables) == 1:
        return RoutedQuery(intent, list_sql(tables[0], limit))

    inner = "\nUNION ALL\n".join(
        f'  {select} FROM "{t}" WHERE {where_sql}' for t in tables
    )
    sql = (
        f"{select}\n"
        f"FROM (\n{inner}\n) AS d198_u\n"
        f'ORDER BY "{order_col}" {order_dir} NULLS LAST\n'
        f"LIMIT {limit};"
    )
    return RoutedQuery(intent, sql)


def _route_catalog_attr(q: str) -> RoutedQuery | None:
    """GIS건물통합·산업단지·행정구역·기초구역 전 속성."""
    from llm2sql.catalog_attrs import match_catalog, place_filters

    parsed = match_catalog(q)
    if parsed is None:
        return None
    ds = parsed.dataset
    where = list(place_filters(ds, q))
    where.extend(parsed.filters)
    where_sql = " AND ".join(where) if where else "TRUE"
    order_col = parsed.order_col or ds.order_col
    order_dir = "ASC" if parsed.order_asc else "DESC"
    cols = ", ".join(f'"{c}"' for c in ds.select_cols)
    select = f"SELECT {cols}"
    prefix = ds.intent_prefix

    if parsed.rank:
        limit, intent = 1, f"{prefix}_rank"
    elif parsed.lookup:
        limit, intent = 20, f"{prefix}_lookup"
    elif _wants_threshold_list(q) or not any(k in q for k in _AREA_COUNTISH):
        limit, intent = 100, f"{prefix}_list"
    else:
        return _count_sql(f"{prefix}_count", ds.table, where_sql)

    sql = (
        f"{select}\n"
        f'FROM "{ds.table}"\n'
        f"WHERE {where_sql}\n"
        f'ORDER BY "{order_col}" {order_dir} NULLS LAST\n'
        f"LIMIT {limit};"
    )
    return RoutedQuery(intent, sql)


_AREA_METRICS = (
    ("건물면적", "A12"),
    ("건축물면적", "A12"),
    ("건축면적", "A12"),
    ("연면적", "A14"),
    ("대지면적", "A15"),
    ("면적", "A14"),
)
_AREA_LISTISH = (
    "목록",
    "리스트",
    "보여",
    "것은",
    "인것",
    "인 것",
    "인것은",
    "것들",
    "어떤",
    "찾아",
    "알려줘",
    "이름",
    "건물명",
    "명칭",
)
_AREA_COUNTISH = ("몇", "건수", "개수", "채수", "수는", "개가", "채야", "몇개")


def _rel_op(rel: str) -> str:
    if rel in ("초과", "넘는"):
        return ">"
    if rel == "미만":
        return "<"
    if rel in ("이하", "까지", "사이"):
        return "<="
    return ">="


def _parse_lo_hi_range(
    q: str,
    prefix: str,
    schema_unit: str,
) -> tuple[tuple[str, str], tuple[str, str]] | None:
    """((lo_op, lo_sql), (hi_op, hi_sql)) — N 이상 M 미만 등 한 지표 구간."""
    m = re.search(
        rf"{prefix}"
        rf"(\d+(?:\.\d+)?)\s*{UNIT_TOKEN}\s*"
        r"(이상|초과|부터)\s*"
        rf"(\d+(?:\.\d+)?)\s*{UNIT_TOKEN}\s*"
        r"(이하|미만|까지|사이)",
        q,
    )
    if not m:
        return None
    lo = convert_for_schema(m.group(1), m.group(2), schema_unit)
    hi = convert_for_schema(m.group(4), m.group(5), schema_unit)
    if lo is None or hi is None or lo.canonical >= hi.canonical:
        return None
    return (_rel_op(m.group(3)), lo.sql), (_rel_op(m.group(6)), hi.sql)


def _parse_area_threshold(q: str) -> tuple[str, str, str] | None:
    """(col, op, value) — 면적 N 이상/이하. 기초구역 면적은 제외."""
    if "기초구역" in q:
        return None
    for label, col in _AREA_METRICS:
        m = re.search(
            rf"{label}\s*(?:이|가)?\s*(\d+(?:\.\d+)?)\s*"
            rf"{UNIT_TOKEN}\s*"
            r"(이상|이하|초과|미만|넘는)",
            q,
        )
        if not m:
            continue
        converted = convert_for_schema(m.group(1), m.group(2), "㎡")
        if converted is None:
            continue
        return col, _rel_op(m.group(3)), converted.sql
    hit = pyeong_threshold(q)
    if hit is not None:
        converted, rel = hit
        return "A14", _rel_op(rel), converted.sql
    return None


def _parse_area_predicates(q: str) -> tuple[str, list[str]] | None:
    """(order_col, extras) — 단일 임계 또는 구간."""
    if "기초구역" in q:
        return None
    for label, col in _AREA_METRICS:
        pair = _parse_lo_hi_range(q, rf"{re.escape(label)}\s*(?:이|가)?\s*", "㎡")
        if pair is None:
            continue
        (lo_op, lo_v), (hi_op, hi_v) = pair
        return col, [f'"{col}" {lo_op} {lo_v}', f'"{col}" {hi_op} {hi_v}']
    parsed = _parse_area_threshold(q)
    if parsed is None:
        return None
    col, op, area = parsed
    return col, [f'"{col}" {op} {area}']


def _wants_threshold_list(q: str) -> bool:
    return any(k in q for k in _AREA_LISTISH) and not any(
        k in q for k in _AREA_COUNTISH
    )


def _route_map_display(q: str) -> RoutedQuery | None:
    """「건물데이터를 표시하라」→ 건수 SQL. 지도는 COUNT를 피처로 올린다."""
    if not wants_map_display(q):
        return None
    if "산업단지" in q or "기초구역" in q:
        return None
    place = extract_place(q)
    gu = extract_gu(q)
    if not place and not gu:
        return None
    extra: list[str] = []
    usage = extract_usage(q)
    if usage:
        extra.append(f"\"A9\" = '{usage}'")
    year_sql = calendar_year_predicate_sql(q, col="A13")
    if year_sql:
        extra.append(year_sql)
    if gu and (not place or str(place).endswith(("구", "군"))):
        where = [place_a4_predicate(gu), *extra]
        sql = (
            'SELECT COUNT(*) AS cnt\n'
            'FROM "AL_D010_26_20250704"\n'
            f'WHERE {" AND ".join(where)};'
        )
        return RoutedQuery("building_map_display", sql)
    kind, sql = scoped_count_sql(place, gu, extra)
    if kind == "none":
        return None
    return RoutedQuery("building_map_display", sql)


def _route_measure_threshold(
    q: str,
    *,
    extras: list[str],
    order_col: str,
    list_intent: str,
    count_intent: str,
) -> RoutedQuery | None:
    """동·구 수치 임계 — 목록 또는 건수."""
    place = extract_place(q)
    gu = extract_gu(q)
    extra = list(extras)
    usage = extract_usage(q)
    if usage:
        extra.append(f'"A9" = \'{usage}\'')
    year_sql = calendar_year_predicate_sql(q, col="A13")
    if year_sql:
        extra.append(year_sql)
    kind, sql = (
        scoped_list_sql(place, gu, extra, order_col=order_col)
        if _wants_threshold_list(q)
        else scoped_count_sql(place, gu, extra)
    )
    if kind == "none":
        return None
    if _wants_threshold_list(q):
        return RoutedQuery(list_intent, sql)
    return RoutedQuery(count_intent, sql)


def _route_building_area_threshold(q: str) -> RoutedQuery | None:
    parsed = _parse_area_predicates(q)
    if parsed is None:
        return None
    col, extras = parsed
    return _route_measure_threshold(
        q,
        extras=extras,
        order_col=col,
        list_intent="building_area_threshold_list",
        count_intent="building_area_threshold_count",
    )


def _parse_height_threshold(q: str) -> tuple[str, str] | None:
    if "높이" not in q:
        return None
    m = re.search(
        rf"높이[가이]?\s*(\d+(?:\.\d+)?)\s*{UNIT_TOKEN}\s*"
        r"(이상|이하|초과|미만|넘는)",
        q,
    )
    if not m:
        return None
    converted = convert_for_schema(m.group(1), m.group(2), "m")
    if converted is None:
        return None
    return _rel_op(m.group(3)), converted.sql


def _parse_floor_threshold(q: str) -> tuple[str, str] | None:
    m = re.search(
        r"(?:지상\s*층?|층수|지상층)[이가]?\s*(\d+)\s*층\s*(이상|이하|초과|미만|넘는)",
        q,
    )
    if m:
        return _rel_op(m.group(2)), m.group(1)
    m = re.search(r"(\d+)\s*층\s*(이상|이하|초과|미만|넘는)", q)
    if m:
        return _rel_op(m.group(2)), m.group(1)
    if "지상" not in q and "층수" not in q:
        return None
    m = re.search(r"지상\s*층?[이가]?\s*(\d+)\s*층", q)
    if not m:
        return None
    if "미만" in q:
        rel = "미만"
    elif "이하" in q:
        rel = "이하"
    elif "넘는" in q or "초과" in q:
        rel = "초과"
    elif "이상" in q:
        rel = "이상"
    else:
        return None
    return _rel_op(rel), m.group(1)


def _route_building_height_threshold(q: str) -> RoutedQuery | None:
    pair = _parse_lo_hi_range(q, r"높이[가이]?\s*", "m") if "높이" in q else None
    if pair is not None:
        extras = [f'"A16" {pair[0][0]} {pair[0][1]}', f'"A16" {pair[1][0]} {pair[1][1]}']
    else:
        parsed = _parse_height_threshold(q)
        if parsed is None:
            return None
        op, meters = parsed
        extras = [f'"A16" {op} {meters}']
    return _route_measure_threshold(
        q,
        extras=extras,
        order_col="A16",
        list_intent="building_height_threshold_list",
        count_intent="building_height_count",
    )


def _route_building_structure(q: str) -> RoutedQuery | None:
    """동·구 + 건축물구조(A11) 및/또는 특수지(A6/A7) 목록/건수."""
    st = extract_structure(q)
    land = extract_special_land(q)
    if st is None and land is None:
        return None
    filters = _a4_place_filters(extract_place(q), extract_gu(q))
    if not filters:
        return None
    where = list(filters)
    if st:
        where.append(f"\"A11\" ILIKE '{st[1]}'")
    if land:
        where.append(land[1])
    usage = extract_usage(q)
    if usage:
        where.append(f'"A9" = \'{usage}\'')
    where_sql = " AND ".join(where)
    if st and land:
        list_intent, count_intent = "building_attr_list", "building_attr_count"
    elif st:
        list_intent, count_intent = (
            "building_structure_list",
            "building_structure_count",
        )
    else:
        list_intent, count_intent = (
            "building_special_land_list",
            "building_special_land_count",
        )
    if _wants_threshold_list(q) or not any(k in q for k in _AREA_COUNTISH):
        return RoutedQuery(
            list_intent,
            (
                'SELECT "A0", "A4", "A5", "A6", "A7", "A9", "A11", "A12", '
                '"A14", "A16", "A24", "A26",\n'
                "       COUNT(*) OVER() AS total_n\n"
                f'FROM "{_D010}"\n'
                f"WHERE {where_sql}\n"
                'ORDER BY "A14" DESC NULLS LAST\n'
                "LIMIT 100;"
            ),
        )
    return _count_sql(count_intent, _D010, where_sql)


def _parse_floor_range(q: str) -> tuple[tuple[str, str], tuple[str, str]] | None:
    m = re.search(
        r"(?:지상\s*층?|층수|지상층)[이가]?\s*(\d+)\s*층\s*(이상|초과|부터)\s*(\d+)\s*층\s*(이하|미만|까지|사이)",
        q,
    )
    if not m:
        m = re.search(
            r"(\d+)\s*층\s*(이상|초과|부터)\s*(\d+)\s*층\s*(이하|미만|까지|사이)",
            q,
        )
    if not m:
        return None
    lo, hi = int(m.group(1)), int(m.group(3))
    if lo >= hi:
        return None
    return (_rel_op(m.group(2)), str(lo)), (_rel_op(m.group(4)), str(hi))


def _route_building_floor_threshold(q: str) -> RoutedQuery | None:
    pair = _parse_floor_range(q)
    if pair is not None:
        extras = [f'"A26" {pair[0][0]} {pair[0][1]}', f'"A26" {pair[1][0]} {pair[1][1]}']
    else:
        parsed = _parse_floor_threshold(q)
        if parsed is None:
            return None
        op, floors = parsed
        extras = [f'"A26" {op} {floors}']
    return _route_measure_threshold(
        q,
        extras=extras,
        order_col="A26",
        list_intent="building_floor_threshold_list",
        count_intent="building_floor_count",
    )


def _route_usage_kinds(q: str) -> RoutedQuery | None:
    if not (("용도" in q) and ("종류" in q or "몇 가지" in q or "몇가지" in q)):
        return None
    for key, intent, table, like in _usage_kind_specs():
        if key in q:
            return RoutedQuery(
                intent,
                (
                    f'SELECT COUNT(DISTINCT "A25") AS cnt\n'
                    f'FROM "{table}"\n'
                    f"WHERE \"A4\" LIKE '%{like}%' AND \"A25\" IS NOT NULL;"
                ),
            )
    return None


def _legal_dong_for_filter(
    conn: psycopg.Connection | None, place: str
) -> str:
    if conn is None:
        return place
    from llm2sql.clarify_qa import _lookup_admin_dong

    if _lookup_admin_dong(conn, place):
        guessed = legal_dong_guess(place)
        if guessed:
            return guessed
    return place


def _looks_like_rank_ask(q: str) -> bool:
    if any(
        k in q
        for k in ("상위", "가장 높", "가장 큰", "제일 높", "제일 큰", "높은 순", "큰 순")
    ):
        return True
    return bool(
        re.search(r"\d+\s*(개|곳|채|동)\b", q)
        and any(k in q for k in ("높", "큰", "상위", "넓은"))
    )


def _numeric_families(q: str) -> set[str]:
    fam: set[str] = set()
    if _parse_area_threshold(q) is not None:
        fam.add("area")
    if _parse_height_threshold(q) is not None:
        fam.add("height")
    if _parse_floor_threshold(q) is not None:
        fam.add("floors")
    return fam


def should_defer_compound_to_plan(q: str) -> bool:
    """단일 규칙 라우트가 조건을 일부만 먹을 복합질의는 SQP에 넘긴다."""
    if any(h in q for h in ("용도별건물", "AL_D198", "D198")):
        return False
    families = _numeric_families(q)
    if len(families) >= 2:
        return True
    spatial_inside = any(
        k in q for k in ("안에", "내에", "내부", "안쪽", "경계 안", "경계안")
    )
    if spatial_inside and (families or _looks_like_rank_ask(q)):
        return True
    if _has_place_buffer_hint(q) and families:
        return True
    if extract_structure(q) and (
        "floors" in families or _looks_like_rank_ask(q) or families
    ):
        return True
    if any(k in q for k in ("평균", "합계")) and any(
        k in q for k in ("높이", "연면적", "건축면적", "대지면적", "층수", "지상")
    ):
        return True
    if "용도별" in q and any(k in q for k in ("개수", "건수", "분포", "구성")):
        return True
    if any(k in q for k in (" 또는 ", " 혹은 ", "이거나", "제외", "아닌", "빼고")):
        return True
    if any(k in q for k in ("사이", "부터", "까지", "건폐율", "용적율", "용적률", "위반")):
        return True
    return False


def try_route(
    question: str,
    conn: psycopg.Connection | None = None,
) -> RoutedQuery | None:
    q = question.strip()

    # 산업단지 관련 규칙 라우트 (건물명보다 우선)
    industrial = _route_buildings_in_industrial(q)
    if industrial is not None:
        return industrial
    industrial = _route_industrial_names(q)
    if industrial is not None:
        return industrial
    industrial = _route_industrial_count(q)
    if industrial is not None:
        return industrial

    # 행정동·기초구역·건물 공간 연산 (속성 COUNT/행정구 오탐보다 우선)
    spatial_hit = try_spatial_route(q)
    if spatial_hit is not None:
        return spatial_hit

    # 지도 표출 — 카탈로그·SQP 주소 목록보다 우선
    map_hit = _route_map_display(q)
    if map_hit is not None:
        return map_hit

    if should_defer_compound_to_plan(q):
        return None

    # 용도별건물공간정보(D198) 전 속성 — D010 면적/산지 오탐보다 우선
    # 특정 건물명+사용승인일 조회는 카탈로그(A13 있음) 오탐보다 이름 조회가 우선
    if not looks_like_building_name_lookup(q):
        d198_hit = _route_d198_attr(q, conn=conn)
        if d198_hit is not None:
            return d198_hit

        catalog_hit = _route_catalog_attr(q)
        if catalog_hit is not None:
            return catalog_hit

    # 동래/금정 주요용도명 종류 — 건물명 조회보다 우선
    usage_kinds = _route_usage_kinds(q)
    if usage_kinds is not None:
        return usage_kinds

    # 면적·높이·층수 임계(동/구) — 건물명 ILIKE 오탐보다 우선
    area_hit = _route_building_area_threshold(q)
    if area_hit is not None:
        return area_hit
    height_hit = _route_building_height_threshold(q)
    if height_hit is not None:
        return height_hit
    floor_hit = _route_building_floor_threshold(q)
    if floor_hit is not None:
        return floor_hit

    struct_hit = _route_building_structure(q)
    if struct_hit is not None:
        return struct_hit

    # 순위·최댓값 — 「가장 큰 아파트」가 건물명 조회로 빠지지 않게
    ranked_early = _route_building_rank(q)
    if ranked_early is not None:
        return ranked_early

    # 지명 버퍼(동 경계 + N m) — 「주변」이 건물명 ILIKE로 빠지지 않게
    place_buf = _route_place_buffer(q)
    if place_buf is not None:
        return place_buf

    # 특정 건물명(고유명사) 조회 — clarify/LLM보다 우선
    name_hit = _route_building_name_lookup(q)
    if name_hit is not None:
        return name_hit

    # 좌표 버퍼 (LLM이 D198로 빠지는 경우 방지)
    m = re.search(
        r"(?:좌표|점)?\s*\(?\s*(12\d\.\d+)\s*[, ]\s*(35\.\d+)\s*\)?.*?"
        r"(\d+(?:\.\d+)?)\s*(킬로미터|㎞|km|미터|m)(?![a-zA-Z²2])",
        q,
    )
    if m and any(k in q for k in ("이내", "근처", "버퍼", "주변", "반경")):
        lon, lat = m.group(1), m.group(2)
        converted = convert_for_schema(m.group(3), m.group(4), "m")
        if converted is not None:
            meters = converted.sql
            return RoutedQuery(
                "buffer_count",
                (
                    'SELECT COUNT(*) AS cnt\n'
                    f'FROM "{_D010}" b\n'
                    "WHERE ST_DWithin(\n"
                    "  b.geometry::geography,\n"
                    f"  ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326)::geography,\n"
                    f"  {meters}\n"
                    ");"
                ),
            )

    # 구 기초구역 ∩ 산업단지
    m = re.search(rf"{_GU}\s*기초구역.{{0,20}}교차.{{0,20}}산업단지", q)
    if not m:
        m = re.search(rf"산업단지.{{0,24}}{_GU}\s*기초구역", q)
    if m and ("산업단지" in q and "기초구역" in q and "교차" in q):
        gu = m.group(1)
        return RoutedQuery(
            "industrial_bas_intersect",
            (
                'SELECT COUNT(DISTINCT i."A0") AS cnt\n'
                'FROM "AL_D060_00_20250804" i\n'
                'JOIN "TL_KODIS_BAS_26_202507" t\n'
                "  ON ST_Intersects(i.geometry, t.geometry)\n"
                f'WHERE t."SIG_KOR_NM" = \'{gu}\';'
            ),
        )

    # 기초구역 개수
    m = re.search(rf"{_GU}\s*기초구역", q)
    if (
        m
        and _wants_count(q)
        and "산업단지" not in q
        and "교차" not in q
        and "면적" not in q
    ):
        gu = m.group(1)
        return RoutedQuery(
            "bas_count",
            (
                'SELECT COUNT(*) AS cnt\n'
                'FROM "TL_KODIS_BAS_26_202507"\n'
                f'WHERE "SIG_KOR_NM" = \'{gu}\';'
            ),
        )

    # 건축 경과년수 (동래/금정 D198 사용승인·허가일자)
    aged = _route_building_age(q, conn=conn)
    if aged is not None:
        return aged

    # 공공시설 등 목록
    listed = _route_facility_list(q, conn=conn)
    if listed is not None:
        return listed

    # 구 주요용도명/용도 종류 (동래→D198_26260, 금정→D198_26410)
    # place/usage COUNT보다 먼저 매칭해야 "건물의 주요용도명 종류"가 건물건수로 오탐되지 않음
    usage_kinds = _route_usage_kinds(q)
    if usage_kinds is not None:
        return usage_kinds

    # 장소(동 우선) + 용도 COUNT / 행정동 공간 COUNT
    usage_count = _route_place_usage_count(q, conn=conn)
    if usage_count is not None:
        return usage_count

    # 장소(구/동) + 건물 건수 (용도 미지정)
    place_count = _route_place_building_count(q)
    if place_count is not None:
        return place_count

    # 동 공간 포함 (안에/내부/안쪽/경계 안)
    m = re.search(
        rf"{_DONG}\s*(?:안(?:에|쪽)?|내부|경계\s*안).{{0,12}}건물",
        q,
    )
    if not m:
        m = re.search(rf"건물.{{0,12}}{_DONG}\s*(?:안(?:에|쪽)?|내부|경계\s*안)", q)
        if m:
            dong = m.group(1)
        else:
            dong = None
    else:
        dong = m.group(1)
    if dong and _wants_count(q):
        from llm2sql.spatial_templates import building_in_dong_count_sql

        return RoutedQuery("building_in_dong_spatial", building_in_dong_count_sql(dong))
    if dong and _wants_list(q):
        from llm2sql.spatial_templates import building_in_dong_list_sql

        return RoutedQuery(
            "building_in_dong_spatial_list",
            building_in_dong_list_sql(dong),
        )

    # 산업단지 코드 prefix
    if "산업단지" in q and re.search(r"\b26\b|26으로", q) and _wants_count(q):
        if "교차" not in q and "기초구역" not in q:
            return RoutedQuery(
                "industrial_code_prefix",
                (
                    'SELECT COUNT(*) AS cnt\n'
                    'FROM "AL_D060_00_20250804"\n'
                    'WHERE "A4" LIKE \'26%\';'
                ),
            )

    # 구 연면적 상위 N
    m = re.search(rf"{_GU}.{{0,20}}연면적.{{0,16}}(?:상위\s*)?(\d+)", q)
    if m and any(k in q for k in ("상위", "큰 순", "연면적")):
        gu, n = m.group(1), m.group(2)
        only_area = any(k in q for k in ("면적값", "면적 값", "연면적만", "값만"))
        cols = (
            '"A14" AS v'
            if only_area or (n == "1" and "가장" in q)
            else '"A4", "A9", "A14"'
        )
        if only_area or (n == "1" and "가장" in q and "보여" not in q):
            if "가장" in q and n == "1":
                cols = '"A14" AS v'
                return RoutedQuery(
                    "building_area_top1_value",
                    (
                        f"SELECT {cols}\n"
                        'FROM "AL_D010_26_20250704"\n'
                        f'WHERE "A4" LIKE \'%{gu}%\'\n'
                        'ORDER BY "A14" DESC NULLS LAST\n'
                        "LIMIT 1;"
                    ),
                )
        return RoutedQuery(
            "building_area_topn",
            (
                f"SELECT {cols}\n"
                'FROM "AL_D010_26_20250704"\n'
                f'WHERE "A4" LIKE \'%{gu}%\'\n'
                'ORDER BY "A14" DESC NULLS LAST\n'
                f"LIMIT {n};"
            ),
        )

    # 구 기초구역 면적 상위 N (면적값이면 BAS_AR만)
    m = re.search(rf"{_GU}\s*기초구역.{{0,24}}(?:상위\s*)?(\d+)", q)
    if m and any(k in q for k in ("면적", "큰 순", "상위")):
        gu, n = m.group(1), m.group(2)
        if any(k in q for k in ("면적값", "면적 값", "면적만")) or (
            n == "1" and "면적" in q
        ):
            return RoutedQuery(
                "bas_area_topn_value",
                (
                    'SELECT "BAS_AR" AS v\n'
                    'FROM "TL_KODIS_BAS_26_202507"\n'
                    f'WHERE "SIG_KOR_NM" = \'{gu}\'\n'
                    'ORDER BY "BAS_AR" DESC NULLS LAST\n'
                    f"LIMIT {n};"
                ),
            )
        return RoutedQuery(
            "bas_area_topn",
            (
                'SELECT "BAS_AR", "BAS_ID", "SIG_KOR_NM"\n'
                'FROM "TL_KODIS_BAS_26_202507"\n'
                f'WHERE "SIG_KOR_NM" = \'{gu}\'\n'
                'ORDER BY "BAS_AR" DESC NULLS LAST\n'
                f"LIMIT {n};"
            ),
        )

    ranked = _route_building_rank(q)
    if ranked is not None:
        return ranked

    return None


def _resolve_d198_table(
    q: str,
    *,
    conn: psycopg.Connection | None,
    gu: str | None,
    place: str | None,
) -> str | None:
    table = d198_table_for_gu(gu)
    if table:
        return table
    if conn is None or not place:
        return None
    with conn.cursor(row_factory=dict_row) as cur:
        for tbl in D198_TABLES:
            cur.execute(
                f"""
                SELECT 1 AS ok FROM "{tbl}"
                WHERE "A4" LIKE %s
                LIMIT 1
                """,
                (f"%{place}%",),
            )
            if cur.fetchone():
                return tbl
    return None


_PLACE_BUFFER_HINT = ("주변", "근처", "인근", "버퍼", "반경")
_LENGTH_DIST = LENGTH_DIST_PATTERN


def _has_place_buffer_hint(q: str) -> bool:
    if any(k in q for k in _PLACE_BUFFER_HINT):
        return True
    return bool(re.search(rf"{_LENGTH_DIST}\s*(?:안|이내)", q))


def _wants_place_buffer_list(q: str) -> bool:
    """「있는 건물은?」은 목록. 「몇 채/건수」는 건수."""
    if any(k in q for k in ("몇", "개수", "건수", "채", "세어", "구해")):
        return False
    if any(
        k in q
        for k in (
            "목록",
            "리스트",
            "보여",
            "있는 건물",
            "건물은",
            "건물들",
            "무엇",
            "어떤",
        )
    ):
        return True
    return "있는" in q


def _route_place_buffer(q: str) -> RoutedQuery | None:
    """법정·행정동 경계의 N m 버퍼 안 건물 (ST_DWithin geography)."""
    if not _has_place_buffer_hint(q):
        return None
    if re.search(r"12\d\.\d+", q) or "좌표" in q:
        return None
    if looks_like_measure_threshold(q):
        return None
    if looks_like_age_question(q):
        return None
    if any(k in q for k in ("산업단지", "기초구역")):
        return None
    locational = any(k in q for k in _PLACE_BUFFER_HINT)
    if not locational and any(
        k in q for k in ("높이", "연면적", "건물면적", "대지면적", "층수")
    ):
        return None
    if not any(k in q for k in ("건물", "건축물", "채")):
        return None

    m = re.search(rf"{_DONG}[^\d]{{0,28}}{_LENGTH_DIST}", q)
    if m:
        dong, num, unit = m.group(1), m.group(2), m.group(3)
    else:
        m = re.search(rf"{_LENGTH_DIST}[^\d]{{0,28}}{_DONG}", q)
        if not m:
            return None
        num, unit, dong = m.group(1), m.group(2), m.group(3)
    if dong in _FALSE_DONG:
        return None

    converted = convert_for_schema(num, unit, "m")
    if converted is None:
        return None
    expand_deg = sql_number(max(0.0015, converted.canonical / 111000.0 * 1.5))
    meters = converted.sql
    exterior = any(k in q for k in ("경계 밖", "바깥", "외부"))
    if _wants_place_buffer_list(q):
        intent = "place_buffer_outside_list" if exterior else "place_buffer_list"
        return RoutedQuery(
            intent,
            place_buffer_list_sql(dong, meters, expand_deg, exterior=exterior),
        )
    intent = "place_buffer_outside_count" if exterior else "place_buffer_count"
    return RoutedQuery(
        intent,
        place_buffer_count_sql(dong, meters, expand_deg, exterior=exterior),
    )


def _route_place_building_count(q: str) -> RoutedQuery | None:
    """용도 없이 구/동 건물 건수만 묻는 경우."""
    if not any(k in q for k in ("건물", "건축물", "채")):
        return None
    if extract_usage(q):
        return None
    if not _wants_count(q):
        return None
    if looks_like_age_question(q):
        return None
    if "산업단지" in q or "기초구역" in q:
        return None
    if any(k in q for k in ("연면적", "건물면적", "대지면적", "면적", "높이", "지상층", "층수")):
        return None
    if "용도별" in q:
        return None
    if any(k in q for k in ("안에", "내부", "안쪽", "경계 안", "교차", "겹치", "인접")):
        return None
    if _has_place_buffer_hint(q):
        return None

    place = extract_place(q)
    gu = extract_gu(q)
    if not place and not gu:
        return None

    kind, sql = scoped_count_sql(place, gu)
    if kind == "none":
        return None
    intent = "building_in_dong_spatial" if kind == "admin" else "building_place_count"
    return RoutedQuery(intent, sql)


def _route_place_usage_count(
    q: str,
    *,
    conn: psycopg.Connection | None,
) -> RoutedQuery | None:
    usage = extract_usage(q)
    if not usage or "산업단지" in q:
        return None
    if not _wants_count(q):
        return None
    if ("연면적" in q or "건물면적" in q or "대지면적" in q or "면적" in q) and any(
        k in q for k in ("이상", "이하", "초과", "미만", "넘는")
    ):
        return None
    if looks_like_age_question(q):
        return None

    place = extract_place(q)
    gu = extract_gu(q)
    if not place and not gu:
        return None

    if usage == "공공용시설":
        extra = ["(\"A9\" = '공공용시설' OR \"A9\" ILIKE '%공공%')"]
    else:
        extra = [f"\"A9\" = '{usage}'"]
    kind, sql = scoped_count_sql(place, gu, extra)
    if kind == "none":
        return None
    intent = (
        "building_admin_dong_usage_count" if kind == "admin" else "building_usage_count"
    )
    return RoutedQuery(intent, sql)


def _route_building_age(
    q: str,
    *,
    conn: psycopg.Connection | None,
) -> RoutedQuery | None:
    if not looks_like_age_question(q):
        return None
    years = extract_age_years(q)
    if years is None:
        return None

    gu = extract_gu(q)
    place = extract_place(q)
    usage = extract_usage(q)
    compare = extract_age_compare(q)
    date_col = "A33" if "허가" in q and "사용승인" not in q else "A34"

    table = _resolve_d198_table(q, conn=conn, gu=gu, place=place)
    tables: list[str]
    if table:
        tables = [table]
    elif is_busan_wide(q) or (gu is None and place is None):
        # 부산 전체·장소 미지정 → 사용승인일이 있는 동래+금정 합산
        tables = list(D198_TABLES)
    else:
        return None

    where: list[str] = []
    if place and place.endswith("동"):
        dong = _legal_dong_for_filter(conn, place)
        where.append(f'"A4" LIKE \'%{dong}%\'')
        if gu:
            where.append(f'"A4" LIKE \'%{gu}%\'')
    elif gu:
        where.append(f'"A4" LIKE \'%{gu}%\'')

    if usage and usage != "공공용시설":
        where.append(f'"A25" = \'{usage}\'')
    elif usage == "공공용시설":
        where.append("(\"A29\" = '공공용' OR \"A25\" ILIKE '%공공%')")

    where.append(age_date_predicate(date_col, years, compare))
    where_sql = " AND ".join(where) if where else age_date_predicate(
        date_col, years, compare
    )

    if len(tables) == 1:
        sql = (
            "SELECT COUNT(*) AS cnt\n"
            f'FROM "{tables[0]}"\n'
            f"WHERE {where_sql};"
        )
        intent = "building_age_count"
    else:
        parts = [
            f'SELECT COUNT(*) AS c FROM "{t}" WHERE {where_sql}' for t in tables
        ]
        sql = (
            "SELECT COALESCE(SUM(c), 0) AS cnt\n"
            "FROM (\n  "
            + "\n  UNION ALL\n  ".join(parts)
            + "\n) AS age_parts;"
        )
        intent = "building_age_count_d198_partial"

    return RoutedQuery(intent, sql)


def _route_facility_list(
    q: str,
    *,
    conn: psycopg.Connection | None,
) -> RoutedQuery | None:
    if not _wants_list(q):
        return None
    usage = extract_usage(q)
    public = usage == "공공용시설" or any(
        k in q for k in ("공공시설", "공공시설물", "공공용")
    )
    if not public and usage is None:
        return None
    place = extract_place(q)
    gu = extract_gu(q)
    if not place and not gu:
        return None

    table = _resolve_d198_table(q, conn=conn, gu=gu, place=place)
    if table and public:
        where: list[str] = []
        if place and place.endswith("동"):
            dong = _legal_dong_for_filter(conn, place)
            where.append(f'"A4" LIKE \'%{dong}%\'')
        elif gu:
            where.append(f'"A4" LIKE \'%{gu}%\'')
        where.append("(\"A29\" = '공공용' OR \"A25\" ILIKE '%공공%' OR \"A28\" = '5')")
        where_sql = " AND ".join(where)
        return RoutedQuery(
            "public_facility_list",
            (
                'SELECT "A25" AS usage, "A13" AS name, "A7" AS jibeon, COUNT(*) AS n\n'
                f'FROM "{table}"\n'
                f"WHERE {where_sql}\n"
                'GROUP BY "A25", "A13", "A7"\n'
                "ORDER BY n DESC NULLS LAST\n"
                "LIMIT 30;"
            ),
        )

    where2: list[str] = []
    if place and place.endswith("동"):
        where2.append(place_a4_predicate(place))
        if gu:
            where2.append(f'"A4" LIKE \'%{gu}%\'')
    elif gu:
        where2.append(f'"A4" LIKE \'%{gu}%\'')
    if public:
        where2.append("(\"A9\" = '공공용시설' OR \"A9\" ILIKE '%공공%')")
    elif usage:
        where2.append(f'"A9" = \'{usage}\'')
    where_sql2 = " AND ".join(where2)
    return RoutedQuery(
        "facility_usage_list",
        (
            'SELECT "A9" AS usage, "A24" AS name, "A5" AS jibeon, COUNT(*) AS n\n'
            'FROM "AL_D010_26_20250704"\n'
            f"WHERE {where_sql2}\n"
            'GROUP BY "A9", "A24", "A5"\n'
            "ORDER BY n DESC NULLS LAST\n"
            "LIMIT 30;"
        ),
    )


_RANK_SUPERLATIVE = (
    "가장 큰",
    "제일 큰",
    "가장큰",
    "제일큰",
    "가장 넓은",
    "제일 넓은",
    "가장넓은",
    "제일넓은",
    "가장 높",
    "제일 높",
    "가장높은",
    "제일높은",
    "최대",
    "1등",
    "최고",
)


def _explicit_count_intent(q: str) -> bool:
    """이름/자료 질의와 구분되는 명시적 건수 의도."""
    if any(
        k in q
        for k in (
            "자료",
            "데이터",
            "데이터셋",
            "테이블",
            "컬럼",
            "속성",
            "이름",
            "명칭",
            "뭐야",
            "무엇",
            "설명",
        )
    ):
        # 「산업단지 수는?」은 허용, 「자료의 이름은?」은 제외
        if not any(k in q for k in ("몇", "개수", "건수", "수는", "수가", "개야", "몇 개", "몇개")):
            return False
    if any(
        k in q
        for k in ("몇", "개수", "건수", "채수", "개야", "몇 개", "몇개", "수는", "수가", "얼마")
    ):
        return True
    # 「산업단지 수?」「산업단지수는」
    if re.search(r"수\s*\??\s*$", q) or re.search(r"단지\s*수", q):
        return True
    return False


def _industrial_scope_sql(q: str) -> str:
    """산업단지 조회 범위 SQL (시군구코드/부산 전역)."""
    gu = extract_gu(q)
    code = busan_gu_code(gu)
    if code:
        return f"\"A4\" = '{code}'"
    if (
        is_busan_wide(q)
        or "부산" in q
        or re.search(r"\b26\b|26으로", q)
        or gu is None
    ):
        return "\"A4\" LIKE '26%'"
    return f"(\"A8\" ILIKE '%{gu}%' OR \"A9\" ILIKE '%{gu}%')"


def _industrial_distinct_names_sql(scope: str) -> str:
    return (
        "SELECT DISTINCT name FROM (\n"
        '  SELECT TRIM("A8") AS name FROM "AL_D060_00_20250804"\n'
        f"  WHERE {scope} AND \"A8\" ILIKE '%산업단지%'\n"
        "  UNION\n"
        '  SELECT TRIM("A9") AS name FROM "AL_D060_00_20250804"\n'
        f"  WHERE {scope} AND \"A9\" ILIKE '%산업단지%'\n"
        ") t\n"
        "WHERE name IS NOT NULL AND BTRIM(name) <> ''\n"
        "  AND name <> '일반산업단지'"
    )


def _industrial_names_sql(scope: str) -> str:
    return _industrial_distinct_names_sql(scope) + "\nORDER BY name;"


def _route_buildings_in_industrial(q: str) -> RoutedQuery | None:
    """구·동 건물 중 산업단지와 교차(단지 내)하는 건물 수."""
    if "산업단지" not in q:
        return None
    if "건물" not in q and "건축물" not in q:
        return None
    if not any(k in q for k in ("내", "안", "속한", "포함", "교차", "위치한", "있는")):
        return None
    if not _explicit_count_intent(q) and not _wants_count(q):
        return None
    # 자료명 질의 제외
    if any(k in q for k in ("자료", "데이터셋", "테이블", "이름", "명칭")):
        return None

    gu = extract_gu(q)
    place = extract_place(q)
    where_b: list[str] = [
        "EXISTS ("
        'SELECT 1 FROM "AL_D060_00_20250804" i '
        "WHERE ST_Intersects(b.geometry, i.geometry)"
        ")"
    ]
    if place and place.endswith("동"):
        where_b.append(
            f'(b."A4" LIKE \'% {place}\' OR b."A4" = \'{place}\')'
        )
        if gu:
            where_b.append(f'b."A4" LIKE \'%{gu}%\'')
    elif gu:
        where_b.append(f'b."A4" LIKE \'%{gu}%\'')

    where_sql = " AND ".join(where_b)
    return RoutedQuery(
        "buildings_in_industrial",
        (
            'SELECT COUNT(*) AS cnt\n'
            f'FROM "{_D010}" b\n'
            f"WHERE {where_sql};"
        ),
    )


def _route_industrial_count(q: str) -> RoutedQuery | None:
    """산업단지 개수(단지명 유니크). 도형 COUNT(*)가 아님."""
    if "산업단지" not in q:
        return None
    if _catalog_owns_industrial(q):
        return None
    if any(k in q for k in ("교차", "기초구역")):
        return None
    # 건물∩산업단지는 별도 라우트
    if ("건물" in q or "건축물" in q) and any(
        k in q for k in ("내", "안", "속한", "포함", "교차")
    ):
        return None
    # 이름/목록 질의는 건수가 아님
    if any(k in q for k in ("이름", "명칭", "목록", "리스트", "어떤")) and not any(
        k in q for k in ("몇", "개수", "건수", "수는", "수가", "개야")
    ):
        return None
    if not _explicit_count_intent(q):
        return None

    scope = _industrial_scope_sql(q)
    inner = _industrial_distinct_names_sql(scope)
    return RoutedQuery(
        "industrial_count",
        f"SELECT COUNT(*) AS cnt FROM (\n{inner}\n) u;",
    )


def _catalog_owns_industrial(q: str) -> bool:
    """산업단지 전용 필드가 있으면 카탈로그 속성 라우트에 맡긴다."""
    from llm2sql.catalog_attrs import match_catalog

    parsed = match_catalog(q)
    return bool(
        parsed is not None
        and parsed.dataset.key == "d060"
        and (parsed.filters or parsed.rank)
    )


def _route_industrial_names(q: str) -> RoutedQuery | None:
    """산업단지 명칭 목록."""
    if "산업단지" not in q:
        return None
    if _catalog_owns_industrial(q):
        return None
    if any(k in q for k in ("교차", "기초구역")):
        return None
    if ("건물" in q or "건축물" in q) and any(
        k in q for k in ("내", "안", "속한", "포함")
    ):
        return None
    if not any(k in q for k in ("이름", "명칭", "목록", "리스트", "어떤", "무엇")):
        return None
    # 순수 건수 질의 제외
    if _explicit_count_intent(q) and not any(
        k in q for k in ("이름", "명칭", "목록", "리스트")
    ):
        return None

    scope = _industrial_scope_sql(q)
    return RoutedQuery("industrial_names", _industrial_names_sql(scope))


def _route_building_name_lookup(q: str) -> RoutedQuery | None:
    """건물명(A24/A13) 부분일치로 특정 단지·건물 정보 조회."""
    if not looks_like_building_name_lookup(q):
        return None
    name = extract_building_name_candidate(q)
    if not name:
        return None

    name_tokens = [
        t
        for t in name.split()
        if t not in _NAME_STOP and t not in {"큰", "높은", "넓은", "많은"}
    ]
    if not name_tokens:
        return None

    place = extract_place(q)
    gu = extract_gu(q)
    if place and re.fullmatch(r"[가-힣]+\d+동", place):
        guessed = legal_dong_guess(place)
        if guessed:
            place = guessed
    where_d010 = _a4_place_filters(place, gu)
    where_d198 = list(where_d010)
    for token in name_tokens:
        safe = token.replace("'", "''")
        where_d010.append(f'"A24" ILIKE \'%{safe}%\'')
        where_d198.append(f'"A13" ILIKE \'%{safe}%\'')

    d010_sql = " AND ".join(where_d010) if where_d010 else "TRUE"
    d198_sql = " AND ".join(where_d198) if where_d198 else "TRUE"
    d010_select = (
        'SELECT "A0"::text AS "A0", "A4"::text AS "A4", "A5"::text AS "A5", '
        '"A9"::text AS "A9", "A11"::text AS "A11", "A12"::float8 AS "A12", '
        '"A13"::text AS "A13", '
        '"A14"::float8 AS "A14", "A16"::float8 AS "A16", "A19"::text AS "A19", '
        '"A24"::text AS "A24", "A25"::text AS "A25", "A26"::float8 AS "A26"\n'
        'FROM "AL_D010_26_20250704"\n'
        f"WHERE {d010_sql}"
    )
    d198_selects = []
    for tbl in D198_TABLES:
        d198_selects.append(
            'SELECT "A0"::text AS "A0", "A4"::text AS "A4", '
            '"A7"::text AS "A5", "A25"::text AS "A9", "A23"::text AS "A11", '
            '"A18"::float8 AS "A12", "A34"::text AS "A13", '
            '"A19"::float8 AS "A14", '
            '"A30"::float8 AS "A16", "A0"::text AS "A19", '
            '"A13"::text AS "A24", "A25"::text AS "A25", "A31"::float8 AS "A26"\n'
            f'FROM "{tbl}"\n'
            f"WHERE {d198_sql}"
        )
    inner = "\nUNION ALL\n".join([d010_select, *d198_selects])
    return RoutedQuery(
        "building_name_lookup",
        (
            "SELECT * FROM (\n"
            "  SELECT DISTINCT ON (\"A4\", \"A5\", \"A24\") *\n"
            "  FROM (\n"
            f"{inner}\n"
            "  ) AS named_hits\n"
            '  ORDER BY "A4", "A5", "A24", "A14" DESC NULLS LAST\n'
            ") AS named_dedup\n"
            'ORDER BY "A24" NULLS LAST, "A14" DESC NULLS LAST\n'
            "LIMIT 20;"
        ),
    )


def _route_building_rank(q: str) -> RoutedQuery | None:
    metric_col = None
    metric_name = None
    has_super = any(k in q for k in _RANK_SUPERLATIVE)
    top_n = _extract_top_n(q, default=1)
    if any(k in q for k in ("건물면적", "건축물면적", "건축면적")) and (
        has_super or top_n > 1
    ):
        metric_col, metric_name = "A12", "건물면적"
    elif "연면적" in q and (has_super or top_n > 1):
        metric_col, metric_name = "A14", "연면적"
    elif "대지면적" in q and (has_super or top_n > 1):
        metric_col, metric_name = "A15", "대지면적"
    elif any(k in q for k in ("가장 높", "제일 높", "가장높은", "제일높은")) or (
        "높" in q
        and any(k in q for k in ("가장", "제일", "최대", "1등", "최고", "상위"))
    ) or ("높은" in q and top_n > 1):
        metric_col, metric_name = "A16", "높이"
    elif ("지상층" in q or "층수" in q or "지상 층" in q) and any(
        k in q for k in ("가장 많", "제일 많", "가장 높", "최대", "1등", "제일 높", "상위")
    ):
        metric_col, metric_name = "A26", "지상층"
    elif any(
        k in q
        for k in (
            "가장 큰",
            "제일 큰",
            "가장큰",
            "제일큰",
            "가장 넓은",
            "제일 넓은",
            "가장넓은",
            "제일넓은",
        )
    ) or (
        top_n > 1
        and any(k in q for k in ("큰", "넓은"))
        and any(k in q for k in ("건물", "아파트", "주택", "건축물", "것물"))
    ):
        # 지표 미지정 시 연면적(규모)으로 해석
        metric_col, metric_name = "A14", "연면적"
    else:
        return None

    place = extract_place(q)
    gu = extract_gu(q)
    where = _a4_place_filters(place, gu)
    # 장소 없음·부산시 전체 → AL_D010 전역 (부산 DB)

    usage_sql = extract_usage(q)
    if usage_sql:
        where.append(f'"A9" = \'{usage_sql}\'')

    if metric_col == "A16":
        where.append(sane_height_sql("A16", "A26"))
    elif metric_col == "A12":
        where.append(sane_footprint_sql("A12", "A14"))
    elif metric_col == "A14":
        where.append(sane_floor_area_sql("A14"))
    elif metric_col == "A15":
        where.append('"A15" > 0 AND "A15" <= 2000000')

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    limit_n = max(1, min(top_n, 20))

    return RoutedQuery(
        f"building_rank_{metric_name}",
        (
            'SELECT "A0", "A4", "A5", "A9", "A12", "A14", "A15", "A16", "A19", "A24", "A25", "A26"\n'
            f'FROM "{_D010}"'
            f"{where_sql}\n"
            f'ORDER BY "{metric_col}" DESC NULLS LAST\n'
            f"LIMIT {limit_n};"
        ),
    )


def _extract_top_n(question: str, *, default: int = 1, max_n: int = 20) -> int:
    """『상위 3』『3개』『탑5』 등에서 N 추출. 여러 개면 마지막 값을 쓴다."""
    q = question.strip()
    patterns = (
        r"상위\s*(\d+)\s*개?",
        r"탑\s*(\d+)",
        r"top\s*(\d+)",
        r"(\d+)\s*개",
        r"(\d+)\s*곳",
        r"(\d+)\s*채",
        r"(\d+)\s*건(?!물)",  # '3건물'이 아닌 '3건'
    )
    found: list[tuple[int, int]] = []
    for pat in patterns:
        for m in re.finditer(pat, q, flags=re.IGNORECASE):
            n = int(m.group(1))
            if 1 <= n <= max_n:
                found.append((m.start(), n))
    if not found:
        return default
    found.sort()
    return found[-1][1]


def fix_common_sql_mistakes(sql: str, question: str | None = None) -> str:
    """LLM SQL의 고빈도 실수를 후처리로 교정."""
    out = re.sub(
        r'"A3"\s+LIKE\s+\'%([가-힣0-9]+(?:구|동))%\'',
        r'"A4" LIKE \'%\1%\'',
        sql,
    )
    if "ST_DWithin" in out or "ST_DWITHIN" in out.upper():
        out = _swap_d198_for_d010(out)

    q = (question or "").strip()
    if not q:
        return out

    # 동래/금정 주요용도명 종류 → D198 A25 고정
    kinds = _route_usage_kinds(q)
    if kinds is not None:
        return kinds.sql

    # 등록되지 않은 구/용도 COUNT인데 D198을 쓰면 AL_D010으로 교정
    gu = extract_gu(q)
    age_q = looks_like_age_question(q)
    if (
        gu
        and d198_table_for_gu(gu) is None
        and not age_q
        and "AL_D198_" in out
        and "주요용도" not in q
    ):
        out = _swap_d198_for_d010(out)
        # D198 컬럼 → D010 대응 컬럼
        out = re.sub(r'"A25"', '"A9"', out)
        out = re.sub(r'"A19"', '"A14"', out)
        out = re.sub(r'"A30"', '"A16"', out)
        out = re.sub(r'"A31"', '"A26"', out)

    # text 일자 < CURRENT_DATE → 명시적 date 캐스트 (실행 오류 방지)
    out = re.sub(
        r'"(A13|A22|A33|A34)"\s*([<>]=?)\s*(CURRENT_DATE)',
        r'"\1"::date \2 \3',
        out,
        flags=re.I,
    )

    # 동래/금정 사용승인·허가일 질의는 규칙 SQL로 고정 (D010 A13 오인 방지)
    d198_hit = _route_d198_attr(q, conn=None)
    if d198_hit is not None:
        return d198_hit.sql

    forced = _route_building_rank(q)
    if forced is not None:
        # 순위 질의는 규칙 SQL로 고정 (잘못된 ORDER BY/컬럼 별칭 방지)
        return forced.sql
    return out