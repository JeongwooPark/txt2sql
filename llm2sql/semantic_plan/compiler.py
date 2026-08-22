"""검증된 SemanticQueryPlan → PostgreSQL SELECT. LLM을 호출하지 않는다."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from llm2sql.domain import STRUCTURE_ALIASES
from llm2sql.gazetteer import uses_admin_boundary
from llm2sql.semantic_plan.catalog import (
    ADMIN_TABLE,
    ALLOWED_COLUMNS,
    ALLOWED_TABLES,
    get_entity,
    get_field,
)
from llm2sql.semantic_plan.models import (
    FilterSpec,
    SemanticCompileError,
    SemanticQueryPlan,
    UnknownSemanticFieldError,
)
from llm2sql.units import sql_number

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_OPS = {
    "eq": "=",
    "neq": "<>",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
}


@dataclass
class CompiledSemanticQuery:
    sql: str
    tables: list[str]
    route: str
    semantic_plan: dict
    uses_boundary: bool = False
    extra: dict = field(default_factory=dict)


def compile_semantic_plan(plan: SemanticQueryPlan) -> CompiledSemanticQuery:
    if plan.entity != "building":
        raise SemanticCompileError(f"v1 compiler supports building only: {plan.entity}")
    entity = get_entity(plan.entity)
    alias = "b"
    tables = [entity.default_table]
    joins: list[str] = []
    where: list[str] = []
    uses_boundary = False

    place = plan.scope.place if plan.scope else None
    spatial_mode = plan.scope.spatial_mode if plan.scope else "auto"

    spatial_places: set[str] = set()
    if plan.spatial_relations:
        spatial_boundary, spatial_places = _apply_spatial_relations(
            alias, plan, tables, joins, where
        )
        uses_boundary = uses_boundary or spatial_boundary

    if place and place.name.strip() and place.name.strip() not in spatial_places:
        name = place.name.strip()
        want_boundary = spatial_mode == "boundary" or (
            spatial_mode == "auto" and uses_admin_boundary(name)
        )
        if want_boundary:
            uses_boundary = True
            if ADMIN_TABLE not in tables:
                tables.append(ADMIN_TABLE)
            joins.append(
                f"JOIN {_ident(ADMIN_TABLE, physical=True)} a "
                f"ON ST_Intersects({alias}.geometry, a.geometry)"
            )
            where.append(_admin_name_sql("a", name))
            where.append("a.\"ADM_CD\" LIKE '21%'")
        else:
            where.append(_a4_place_sql(alias, name))

    height_used = False
    for spec in plan.filters:
        clause, used_height = _filter_sql(alias, plan.entity, spec)
        where.append(clause)
        height_used = height_used or used_height

    if plan.query_kind in {"rank", "list"} and any(
        item.field == "height_m" for item in plan.order_by
    ):
        height_used = True
    if height_used:
        where.append(_sane_height_sql(alias))

    select_sql = _select_sql(alias, plan)
    from_sql = f"FROM {_ident(entity.default_table, physical=True)} {alias}"
    if joins:
        from_sql = from_sql + "\n" + "\n".join(joins)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    group_sql = _group_sql(alias, plan)
    order_sql = _order_sql(alias, plan)
    limit_sql = f"LIMIT {int(plan.limit)}" if plan.limit else ""

    parts = [select_sql, from_sql]
    if where_sql:
        parts.append(where_sql)
    if group_sql:
        parts.append(group_sql)
    if order_sql:
        parts.append(order_sql)
    if limit_sql:
        parts.append(limit_sql)
    sql = "\n".join(parts) + ";"

    _assert_safe_sql(sql)
    return CompiledSemanticQuery(
        sql=sql,
        tables=tables,
        route=f"semantic_plan_{plan.query_kind}",
        semantic_plan=plan.model_dump(),
        uses_boundary=uses_boundary,
    )


def _select_sql(alias: str, plan: SemanticQueryPlan) -> str:
    if plan.query_kind == "count":
        return 'SELECT COUNT(*) AS "count"'
    if plan.query_kind in {"aggregate", "distribution"}:
        pieces: list[str] = []
        for key in plan.group_by:
            field = get_field(plan.entity, key)
            pieces.append(f"{_col(alias, field.column)} AS {_ident(key)}")
        aggs = list(plan.aggregations)
        if not aggs and plan.query_kind == "distribution":
            pieces.append('COUNT(*) AS "n"')
        for agg in aggs:
            pieces.append(_agg_sql(alias, plan.entity, agg.function, agg.field, agg.alias))
        if not pieces:
            raise SemanticCompileError("aggregate/distribution needs aggregations")
        return "SELECT " + ",\n       ".join(pieces)

    keys = list(plan.select)
    if not keys:
        keys = ["name", "legal_dong", "lot_address"]
    pieces = []
    for key in keys:
        field = get_field(plan.entity, key)
        expr = _col(alias, field.column)
        if field.data_type == "number":
            expr = f"{expr}::float8"
        pieces.append(f"{expr} AS {_ident(key)}")
    return "SELECT " + ",\n       ".join(pieces)


def _agg_sql(
    alias: str,
    entity: str,
    function: str,
    field_key: str | None,
    alias_name: str | None,
) -> str:
    out = alias_name or (f"{function}_{field_key}" if field_key else function)
    if not _IDENT_RE.fullmatch(out):
        raise SemanticCompileError(f"invalid aggregation alias: {out}")
    if function == "count" and not field_key:
        return f'COUNT(*) AS {_ident(out)}'
    if not field_key:
        raise SemanticCompileError(f"{function} requires a field")
    field = get_field(entity, field_key)
    if not field.aggregatable:
        raise SemanticCompileError(f"field is not aggregatable: {field_key}")
    expr = f"{_col(alias, field.column)}::float8"
    if function == "median":
        return f"PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {expr}) AS {_ident(out)}"
    fn = {"avg": "AVG", "sum": "SUM", "min": "MIN", "max": "MAX", "count": "COUNT"}
    sql_fn = fn.get(function)
    if sql_fn is None:
        raise SemanticCompileError(f"unsupported aggregation: {function}")
    return f"{sql_fn}({expr}) AS {_ident(out)}"


def _group_sql(alias: str, plan: SemanticQueryPlan) -> str:
    if not plan.group_by:
        return ""
    cols = []
    for key in plan.group_by:
        field = get_field(plan.entity, key)
        cols.append(_col(alias, field.column))
    return "GROUP BY " + ", ".join(cols)


def _order_sql(alias: str, plan: SemanticQueryPlan) -> str:
    if plan.query_kind == "distribution" and not plan.order_by:
        return 'ORDER BY "n" DESC NULLS LAST'
    if not plan.order_by:
        return ""
    bits = []
    for item in plan.order_by:
        field = get_field(plan.entity, item.field)
        expr = _col(alias, field.column)
        if field.data_type == "number":
            expr = f"{expr}::float8"
        direction = "DESC" if item.direction == "desc" else "ASC"
        nulls = "NULLS FIRST" if item.nulls == "first" else "NULLS LAST"
        bits.append(f"{expr} {direction} {nulls}")
    return "ORDER BY " + ", ".join(bits)


def _filter_sql(alias: str, entity: str, spec: FilterSpec) -> tuple[str, bool]:
    try:
        field = get_field(entity, spec.field)
    except UnknownSemanticFieldError as exc:
        raise SemanticCompileError(str(exc)) from exc
    col = _col(alias, field.column)
    height_used = spec.field == "height_m"
    if spec.operator == "is_null":
        return f"{col} IS NULL", height_used
    if spec.operator == "is_not_null":
        return f"{col} IS NOT NULL", height_used
    if spec.operator == "in":
        values = spec.value if isinstance(spec.value, (list, tuple)) else [spec.value]
        lits = ", ".join(_literal(v, field.data_type) for v in values)
        return f"{col} IN ({lits})", height_used
    if spec.operator == "contains":
        pattern = spec.value
        if spec.field == "structure" and isinstance(pattern, str):
            mapped = STRUCTURE_ALIASES.get(pattern)
            if mapped:
                return f"{col} ILIKE {_literal(mapped, 'text')}", height_used
        return f"{col} ILIKE {_literal(f'%{pattern}%', 'text')}", height_used
    if spec.operator == "between":
        left = _literal(spec.value, field.data_type)
        right = _literal(spec.value2, field.data_type)
        expr = f"{col}::float8" if field.data_type == "number" else col
        return f"{expr} BETWEEN {left} AND {right}", height_used
    op = _OPS.get(spec.operator)
    if op is None:
        raise SemanticCompileError(f"unknown operator: {spec.operator}")
    if spec.field == "structure" and spec.operator == "eq" and isinstance(spec.value, str):
        mapped = STRUCTURE_ALIASES.get(spec.value)
        if mapped:
            return f"{col} ILIKE {_literal(mapped, 'text')}", height_used
    expr = f"{col}::float8" if field.data_type == "number" else col
    return f"{expr} {op} {_literal(spec.value, field.data_type)}", height_used


def _apply_spatial_relations(
    alias: str,
    plan: SemanticQueryPlan,
    tables: list[str],
    joins: list[str],
    where: list[str],
) -> tuple[bool, set[str]]:
    """spatial_relations → JOIN/WHERE. 물리 함수명은 compiler만 고른다."""
    uses_boundary = False
    used_places: set[str] = set()
    admin_alias_used = False
    for index, rel in enumerate(plan.spatial_relations):
        target = rel.target
        place_name = (
            target.place.name.strip() if target.place and target.place.name else None
        )
        if rel.relation in {"within", "intersects"}:
            if not place_name:
                raise SemanticCompileError("within/intersects requires a place target")
            used_places.add(place_name)
            d_alias = "a" if not admin_alias_used else f"a{index}"
            admin_alias_used = True
            if ADMIN_TABLE not in tables:
                tables.append(ADMIN_TABLE)
            joins.append(
                f"JOIN {_ident(ADMIN_TABLE, physical=True)} {d_alias} "
                f"ON ST_Intersects({alias}.geometry, {d_alias}.geometry)"
            )
            where.append(_admin_name_sql(d_alias, place_name))
            where.append(f"{d_alias}.\"ADM_CD\" LIKE '21%'")
            uses_boundary = True
            continue
        if rel.relation in {"within_distance", "outside_distance"}:
            if rel.distance_m is None or rel.distance_m <= 0:
                raise SemanticCompileError("distance_m must be > 0")
            meters = sql_number(float(rel.distance_m))
            expand = sql_number(max(0.0015, float(rel.distance_m) / 111000.0 * 1.5))
            z_alias = "z" if index == 0 else f"z{index}"
            if place_name:
                used_places.add(place_name)
                if ADMIN_TABLE not in tables:
                    tables.append(ADMIN_TABLE)
                pred = f"{_admin_name_sql('d', place_name)} AND d.\"ADM_CD\" LIKE '21%'"
                joins.append(
                    "CROSS JOIN (\n"
                    "  SELECT ST_Union(d.geometry) AS geom\n"
                    f"  FROM {_ident(ADMIN_TABLE, physical=True)} d\n"
                    f"  WHERE {pred}\n"
                    f") {z_alias}"
                )
                where.append(f"{z_alias}.geom IS NOT NULL")
                where.append(f"{alias}.geometry && ST_Expand({z_alias}.geom, {expand})")
                where.append(
                    "ST_DWithin("
                    f"{alias}.geometry::geography, "
                    f"{z_alias}.geom::geography, "
                    f"{meters})"
                )
                if rel.relation == "outside_distance":
                    where.append(
                        f"NOT ST_Intersects({alias}.geometry, {z_alias}.geom)"
                    )
                uses_boundary = True
                continue
            if target.longitude is not None and target.latitude is not None:
                lon = sql_number(float(target.longitude))
                lat = sql_number(float(target.latitude))
                point = f"ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326)"
                where.append(
                    "ST_DWithin("
                    f"{alias}.geometry::geography, "
                    f"{point}::geography, "
                    f"{meters})"
                )
                continue
            raise SemanticCompileError("within_distance needs a place or lon/lat")
        raise SemanticCompileError(f"unsupported spatial relation: {rel.relation}")
    return uses_boundary, used_places


def _a4_place_sql(alias: str, place: str) -> str:
    col = f'{alias}."A4"'
    if place.endswith(("동", "가", "리", "로")):
        return f"({col} LIKE {_literal('% ' + place, 'text')} OR {col} = {_literal(place, 'text')})"
    return f"{col} LIKE {_literal('%' + place + '%', 'text')}"


def _admin_name_sql(alias: str, place: str) -> str:
    col = f'{alias}."ADM_NM"'
    if re.fullmatch(r"[가-힣]+\d+동", place):
        return f"{col} = {_literal(place, 'text')}"
    stem = place[:-1] if place.endswith("동") else place
    if not re.fullmatch(r"[가-힣0-9]+", stem):
        return f"{col} = {_literal(place, 'text')}"
    return (
        f"({col} = {_literal(place, 'text')} OR "
        f"{col} ~ {_literal('^' + stem + '[0-9]+동$', 'text')})"
    )


def _sane_height_sql(alias: str) -> str:
    col = f'{alias}."A16"::float8'
    floors = f'{alias}."A26"::float8'
    return (
        f"{col} > 0 AND {col} <= 600 AND "
        f"({alias}.\"A26\" IS NULL OR {col} <= ({floors} * 8 + 30))"
    )


def _col(alias: str, column: str) -> str:
    return f"{alias}.{_ident(column, physical=True)}"


_SQL_WORDS = frozenset(
    {
        "select",
        "from",
        "where",
        "join",
        "insert",
        "update",
        "delete",
        "drop",
        "table",
        "limit",
        "order",
        "group",
    }
)


def _ident(name: str, *, physical: bool = False) -> str:
    if not _IDENT_RE.fullmatch(name) or name.lower() in _SQL_WORDS:
        raise SemanticCompileError(f"invalid identifier: {name}")
    if physical and name not in ALLOWED_TABLES and name not in ALLOWED_COLUMNS:
        raise SemanticCompileError(f"rejected physical identifier: {name}")
    return '"' + name + '"'


def _literal(value: object, data_type: str) -> str:
    if value is None:
        return "NULL"
    if data_type == "number":
        try:
            number = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise SemanticCompileError(f"invalid number literal: {value!r}") from exc
        if number != number or number in (float("inf"), float("-inf")):
            raise SemanticCompileError("invalid number literal")
        return sql_number(number)
    text = str(value)
    return "'" + text.replace("'", "''") + "'"


def _assert_safe_sql(sql: str) -> str:
    lower = " ".join(sql.lower().split())
    if not lower.startswith("select"):
        raise SemanticCompileError("compiled SQL must be SELECT")
    for word in ("insert", "update", "delete", "drop", "alter", "truncate"):
        if f" {word} " in f" {lower} ":
            raise SemanticCompileError(f"forbidden keyword: {word}")
    if "select *" in lower:
        raise SemanticCompileError("SELECT * is not allowed")
    return sql
