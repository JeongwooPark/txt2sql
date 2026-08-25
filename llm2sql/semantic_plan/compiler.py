"""검증된 SemanticQueryPlan → PostgreSQL SELECT. LLM을 호출하지 않는다."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from llm2sql.domain import STRUCTURE_ALIASES, BUSAN_GU_CODES, d198_table_for_gu
from llm2sql.gazetteer import uses_admin_boundary
from llm2sql.semantic_plan.catalog import (
    ADMIN_TABLE,
    ALLOWED_COLUMNS,
    ALLOWED_TABLES,
    BASIC_ZONE_TABLE,
    BUILDING_TABLE,
    INDUSTRIAL_TABLE,
    get_entity,
    get_field,
)
from llm2sql.semantic_plan.migrate import validate_predicate
from llm2sql.semantic_plan.models import (
    ExpressionSpec,
    FilterSpec,
    PredicateSpec,
    SemanticCompileError,
    SemanticQueryPlan,
    UnknownSemanticFieldError,
)
from llm2sql.semantic_plan.predicate_utils import effective_predicate
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
    params: list[object] = field(default_factory=list)


_ENTITY_ALIAS = {
    "building": "b",
    "admin_area": "a",
    "basic_zone": "z",
    "industrial_complex": "i",
}

# D198 물리 컬럼. D010 A27은 지하층수, D198 A27은 세부용도.
D198_BUILDING_COLUMNS = {
    "id": "A1",
    "name": "A13",
    "legal_dong": "A4",
    "lot_address": "A7",
    "usage": "A25",
    "structure": "A23",
    "building_area_m2": "A18",
    "gross_floor_area_m2": "A19",
    "site_area_m2": "A17",
    "height_m": "A30",
    "ground_floors": "A31",
    "basement_floors": "A32",
    "building_coverage_ratio": "A21",
    "floor_area_ratio": "A20",
    "building_dong_name": "A14",
    "special_land": "A6",
    "approval_date": "A34",
    "permit_date": "A33",
    "detail_usage": "A27",
    "usage_class": "A29",
    "ledger_kind": "A12",
}


def compile_semantic_plan(plan: SemanticQueryPlan) -> CompiledSemanticQuery:
    entity = get_entity(plan.entity)
    alias = _ENTITY_ALIAS.get(plan.entity, "t")
    col_map = _column_override(plan)
    d198_table = _d198_table_for_plan(plan)
    default_table = d198_table or entity.default_table
    tables = [default_table]
    joins: list[str] = []
    where: list[str] = []
    uses_boundary = False
    compiled_nodes: list[str] = []

    place = plan.scope.place if plan.scope else None
    spatial_mode = plan.scope.spatial_mode if plan.scope else "auto"

    spatial_places: set[str] = set()
    spatial_order: list[str] = []
    if plan.spatial_relations:
        spatial_boundary, spatial_places = _apply_spatial_relations(
            alias, plan, tables, joins, where, spatial_order
        )
        uses_boundary = uses_boundary or spatial_boundary

    if plan.joins:
        _apply_canonical_joins(alias, plan, tables, joins, where)

    if place and place.name.strip() and place.name.strip() not in spatial_places:
        name = place.name.strip()
        if place.kind == "sido" or name in {"부산광역시", "부산시", "부산"}:
            name = ""
        if not name:
            pass
        elif plan.entity != "building":
            where.append(_entity_place_sql(alias, plan.entity, name))
        else:
            want_boundary = spatial_mode == "boundary" or (
                spatial_mode == "auto" and uses_admin_boundary(name)
            )
            if want_boundary:
                uses_boundary = True
                if ADMIN_TABLE not in tables:
                    tables.append(ADMIN_TABLE)
                joins.append(
                    f"JOIN {_ident(ADMIN_TABLE, physical=True)} adm "
                    f"ON ST_Intersects({alias}.geometry, adm.geometry)"
                )
                where.append(_admin_name_sql("adm", name))
                where.append('adm."ADM_CD" LIKE \'21%\'')
            else:
                where.append(_a4_place_sql(alias, name))

    params: list[object] = []
    pred = effective_predicate(plan)
    if pred is not None:
        validate_predicate(pred)
        clause, _, pred_params = _predicate_sql(
            alias, plan.entity, pred, col_map=col_map
        )
        where.append(clause)
        params.extend(pred_params)
        compiled_nodes.extend(_predicate_node_ids(pred))

    gap_assump = next(
        (a for a in (plan.assumptions or []) if a.startswith("permit_year_gap:")),
        None,
    )
    if gap_assump and plan.entity == "building":
        n = int(gap_assump.split(":", 1)[1])
        a33 = _col(alias, "A33")
        a34 = _col(alias, "A34")
        y33 = f"LEFT(regexp_replace({a33}::text, '[^0-9]', '', 'g'), 4)::int"
        y34 = f"LEFT(regexp_replace({a34}::text, '[^0-9]', '', 'g'), 4)::int"
        where.append(f"{a33}::text ~ '^[0-9]{{4}}'")
        where.append(f"{a34}::text ~ '^[0-9]{{4}}'")
        where.append(f"ABS({y33} - {y34}) >= {n}")

    select_sql = _select_sql(alias, plan, col_map=col_map)
    from_sql = f"FROM {_ident(default_table, physical=True)} {alias}"
    if joins:
        from_sql = from_sql + "\n" + "\n".join(joins)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    group_sql = _group_sql(alias, plan, col_map=col_map)
    having_sql = ""
    if plan.having and plan.having.predicate:
        having_clause, _, having_params = _predicate_sql(
            alias, plan.entity, plan.having.predicate, col_map=col_map
        )
        having_sql = f"HAVING {having_clause}"
        params.extend(having_params)
    order_sql = _order_sql(alias, plan, col_map=col_map)
    if spatial_order:
        extra_order = ", ".join(spatial_order)
        order_sql = f"{order_sql}, {extra_order}" if order_sql else f"ORDER BY {extra_order}"
    limit_sql = f"LIMIT {int(plan.limit)}" if plan.limit else ""

    parts = [select_sql, from_sql]
    if where_sql:
        parts.append(where_sql)
    if group_sql:
        parts.append(group_sql)
    if having_sql:
        parts.append(having_sql)
    if order_sql:
        parts.append(order_sql)
    if limit_sql:
        parts.append(limit_sql)
    sql = "\n".join(parts) + ";"

    _assert_safe_sql(sql)
    _assert_table_columns(sql, plan.entity, tables)
    extra = dict(plan.model_dump().get("extra") or {})
    extra["compile_trace"] = {
        "entity": plan.entity,
        "predicate_nodes": compiled_nodes,
        "aggregations": [item.function for item in plan.aggregations],
        "group_fields": list(plan.group_by),
        "spatial_relations": [item.relation for item in plan.spatial_relations],
        "filters_merged": bool(plan.filters) and plan.predicate is not None,
    }
    if plan.spatial_relations:
        extra.setdefault("distinct_policy", "identity_if_spatial_join")
    return CompiledSemanticQuery(
        sql=sql,
        tables=tables,
        route=f"semantic_plan_{plan.query_kind}",
        semantic_plan=plan.model_dump(),
        uses_boundary=uses_boundary,
        extra=extra,
        params=params,
    )


def _field_col(
    alias: str,
    entity: str,
    key: str,
    col_map: dict[str, str] | None = None,
):
    field = get_field(entity, key)
    column = (col_map or {}).get(key) or field.column
    return field, _col(alias, column)


def _select_sql(
    alias: str,
    plan: SemanticQueryPlan,
    col_map: dict[str, str] | None = None,
) -> str:
    if plan.query_kind == "count" and not plan.ratios:
        industrial_join = any(
            getattr(rel.target, "entity", None) == "industrial_complex"
            for rel in plan.spatial_relations
        )
        if industrial_join:
            pk = {
                "building": "A0",
                "basic_zone": "BAS_ID",
                "industrial_complex": "A0",
            }.get(plan.entity, "A0")
            return f'SELECT COUNT(DISTINCT {alias}."{pk}") AS "count"'
        return 'SELECT COUNT(*) AS "count"'
    if plan.query_kind in {"aggregate", "distribution"} or plan.ratios:
        pieces: list[str] = []
        for key in plan.group_by:
            _field, col = _field_col(alias, plan.entity, key, col_map)
            if key == "approval_date" and "approval_decade" in (plan.assumptions or []):
                pieces.append(f"{_approval_decade_expr(col)} AS {_ident('decade')}")
            elif key == "sigungu_name" and plan.entity == "building":
                pieces.append(f"{_sigungu_name_sql(alias)} AS {_ident(key)}")
            else:
                pieces.append(f"{col} AS {_ident(key)}")
        for ratio in plan.ratios:
            pieces.append(_ratio_sql(alias, plan, ratio, col_map=col_map))
        aggs = list(plan.aggregations)
        if not aggs and not plan.ratios and plan.query_kind == "distribution":
            pieces.append('COUNT(*) AS "n"')
        for agg in aggs:
            pieces.append(_agg_sql(alias, plan.entity, agg, col_map=col_map))
        if not pieces:
            raise SemanticCompileError("aggregate/distribution needs aggregations")
        return "SELECT " + ",\n       ".join(pieces)

    keys = list(plan.select)
    if not keys:
        if plan.entity == "admin_area":
            keys = ["name"]
        elif plan.entity == "basic_zone":
            keys = ["id", "gu_name"]
        elif plan.entity == "industrial_complex":
            keys = ["name"]
        else:
            keys = ["name", "legal_dong", "lot_address"]
    pieces = []
    for key in keys:
        field, expr = _field_col(alias, plan.entity, key, col_map)
        if field.data_type == "number":
            expr = f"{expr}::float8"
        pieces.append(f"{expr} AS {_ident(key)}")
    return "SELECT " + ",\n       ".join(pieces)


def _compile_expression(
    alias: str,
    entity: str,
    expr: ExpressionSpec,
    col_map: dict[str, str] | None = None,
) -> str:
    if expr.kind == "field":
        if not expr.field:
            raise SemanticCompileError("expression field missing")
        field, col = _field_col(alias, entity, expr.field, col_map)
        return f"{col}::float8" if field.data_type == "number" else col
    if expr.left is None or expr.right is None:
        raise SemanticCompileError("expression operands required")
    left = _compile_expression(alias, entity, expr.left, col_map)
    right = _compile_expression(alias, entity, expr.right, col_map)
    if expr.kind == "divide":
        return f"({left} / NULLIF({right}, 0))"
    if expr.kind == "multiply":
        return f"({left} * {right})"
    if expr.kind == "add":
        return f"({left} + {right})"
    if expr.kind == "subtract":
        return f"({left} - {right})"
    raise SemanticCompileError(f"unsupported expression kind: {expr.kind}")


def _ratio_sql(
    alias: str,
    plan: SemanticQueryPlan,
    ratio,
    col_map: dict[str, str] | None = None,
) -> str:
    num, _, _ = _predicate_sql(
        alias, plan.entity, ratio.numerator_predicate, col_map=col_map
    )
    if ratio.denominator_predicate is not None:
        den, _, _ = _predicate_sql(
            alias, plan.entity, ratio.denominator_predicate, col_map=col_map
        )
        den_count = f"COUNT(*) FILTER (WHERE {den})"
    else:
        den_count = "COUNT(*)"
    out = ratio.alias or "ratio_pct"
    if not _IDENT_RE.fullmatch(out):
        raise SemanticCompileError(f"invalid ratio alias: {out}")
    return (
        f"{sql_number(float(ratio.multiplier))} * COUNT(*) FILTER "
        f"(WHERE {num})::float8 / NULLIF({den_count}, 0) AS {_ident(out)}"
    )


def _agg_sql(
    alias: str,
    entity: str,
    agg,
    col_map: dict[str, str] | None = None,
) -> str:
    function = agg.function
    field_key = agg.field
    out = agg.alias or (f"{function}_{field_key}" if field_key else function)
    if not _IDENT_RE.fullmatch(out):
        raise SemanticCompileError(f"invalid aggregation alias: {out}")
    filter_parts: list[str] = []
    if getattr(agg, "filter_field", None):
        extra, _ = _filter_sql(
            alias,
            entity,
            FilterSpec(
                field=agg.filter_field,
                operator=agg.filter_operator or "eq",
                value=agg.filter_value,
            ),
            col_map=col_map,
        )
        filter_parts.append(extra)
    if agg.predicate is not None:
        clause, _, _ = _predicate_sql(alias, entity, agg.predicate, col_map=col_map)
        filter_parts.append(clause)
    filter_sql = f" FILTER (WHERE {' AND '.join(filter_parts)})" if filter_parts else ""
    if agg.expression is not None:
        expr = _compile_expression(alias, entity, agg.expression, col_map)
    elif function == "count" and not field_key:
        return f"COUNT(*){filter_sql} AS {_ident(out)}"
    elif not field_key:
        raise SemanticCompileError(f"{function} requires a field")
    else:
        field, col = _field_col(alias, entity, field_key, col_map)
        if not field.aggregatable:
            raise SemanticCompileError(f"field is not aggregatable: {field_key}")
        expr = f"{col}::float8"
    if function == "percentile":
        if agg.percentile is None:
            raise SemanticCompileError("percentile requires a value")
        return (
            f"PERCENTILE_CONT({sql_number(float(agg.percentile))}) "
            f"WITHIN GROUP (ORDER BY {expr}){filter_sql} AS {_ident(out)}"
        )
    if function == "median":
        return (
            f"PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {expr})"
            f"{filter_sql} AS {_ident(out)}"
        )
    if function == "stddev":
        return f"STDDEV_POP({expr}){filter_sql} AS {_ident(out)}"
    fn = {"avg": "AVG", "sum": "SUM", "min": "MIN", "max": "MAX", "count": "COUNT"}
    sql_fn = fn.get(function)
    if sql_fn is None:
        raise SemanticCompileError(f"unsupported aggregation: {function}")
    return f"{sql_fn}({expr}){filter_sql} AS {_ident(out)}"


def _group_sql(
    alias: str, plan: SemanticQueryPlan, col_map: dict[str, str] | None = None
) -> str:
    if not plan.group_by:
        return ""
    cols = []
    for key in plan.group_by:
        _field, col = _field_col(alias, plan.entity, key, col_map)
        if key == "approval_date" and "approval_decade" in (plan.assumptions or []):
            cols.append(_approval_decade_expr(col))
        elif key == "sigungu_name" and plan.entity == "building":
            cols.append(_sigungu_name_sql(alias))
        else:
            cols.append(col)
    return "GROUP BY " + ", ".join(cols)


def _order_sql(
    alias: str, plan: SemanticQueryPlan, col_map: dict[str, str] | None = None
) -> str:
    if not plan.order_by:
        return ""
    bits = []
    agg_aliases = {item.alias for item in plan.aggregations if item.alias}
    agg_aliases.update(item.alias for item in plan.ratios if item.alias)
    for item in plan.order_by:
        if item.field in agg_aliases or item.field in {"count", "n"}:
            expr = _ident(item.field)
        else:
            field, expr = _field_col(alias, plan.entity, item.field, col_map)
            if item.field == "approval_date" and "approval_decade" in (plan.assumptions or []):
                expr = _approval_decade_expr(
                    _field_col(alias, plan.entity, "approval_date", col_map)[1]
                )
            elif field.data_type == "number":
                expr = f"{expr}::float8"
        direction = "DESC" if item.direction == "desc" else "ASC"
        nulls = "NULLS FIRST" if item.nulls == "first" else "NULLS LAST"
        bits.append(f"{expr} {direction} {nulls}")
    return "ORDER BY " + ", ".join(bits)


def _operand_sql(
    alias: str,
    entity: str,
    operand,
    col_map: dict[str, str] | None = None,
) -> tuple[str, bool, list[object]]:
    from llm2sql.semantic_plan.models import OperandSpec

    if operand is None:
        raise SemanticCompileError("missing operand")
    if operand.kind == "field":
        if not operand.field:
            raise SemanticCompileError("field operand missing name")
        field, col = _field_col(alias, entity, operand.field, col_map)
        expr = f"{col}::float8" if field.data_type == "number" else col
        return expr, operand.field == "height_m", []
    field_type = "number" if isinstance(operand.value, (int, float)) else "text"
    lit = _literal(operand.value, field_type)
    return lit, False, [operand.value]


def _predicate_sql(
    alias: str,
    entity: str,
    pred: PredicateSpec,
    col_map: dict[str, str] | None = None,
) -> tuple[str, bool, list[object]]:
    if pred.op == "and":
        parts = [
            _predicate_sql(alias, entity, child, col_map=col_map)
            for child in (pred.args or [])
        ]
        sql = "(" + " AND ".join(item[0] for item in parts) + ")"
        return sql, any(item[1] for item in parts), [p for item in parts for p in item[2]]
    if pred.op == "or":
        parts = [
            _predicate_sql(alias, entity, child, col_map=col_map)
            for child in (pred.args or [])
        ]
        sql = "(" + " OR ".join(item[0] for item in parts) + ")"
        return sql, any(item[1] for item in parts), [p for item in parts for p in item[2]]
    if pred.op == "not":
        if not pred.args:
            raise SemanticCompileError("not predicate missing args")
        inner, height_used, params = _predicate_sql(
            alias, entity, pred.args[0], col_map=col_map
        )
        return f"(NOT {inner})", height_used, params
    if pred.op != "cmp" or pred.operator is None:
        raise SemanticCompileError(f"unsupported predicate op: {pred.op}")
    if pred.left and pred.left.field in {"special_land", "structure"}:
        spec = FilterSpec(
            field=pred.left.field,
            operator=pred.operator,
            value=pred.right.value if pred.right else None,
        )
        sql, height_used = _filter_sql(alias, entity, spec, col_map=col_map)
        return sql, height_used, []
    if pred.left and pred.left.field in {"approval_date", "permit_date"}:
        raw = pred.right.value if pred.right else None
        value2 = None
        value = raw
        if pred.operator == "between":
            if isinstance(raw, (list, tuple)) and len(raw) >= 2:
                value, value2 = raw[0], raw[1]
            else:
                raise SemanticCompileError("between requires [low, high] literal")
        spec = FilterSpec(
            field="approval_date",
            operator=pred.operator,
            value=value,
            value2=value2,
        )
        _field, col = _field_col(alias, entity, "approval_date", col_map)
        return _approval_date_sql(col, spec), False, []
    if pred.operator in {"is_null", "is_not_null"}:
        left, height_used, params = _operand_sql(
            alias, entity, pred.left, col_map=col_map
        )
        sql = f"{left} IS NULL" if pred.operator == "is_null" else f"{left} IS NOT NULL"
        return sql, height_used, params
    if pred.operator == "between":
        left, height_used, params = _operand_sql(
            alias, entity, pred.left, col_map=col_map
        )
        raw = pred.right.value if pred.right else None
        if isinstance(raw, (list, tuple)) and len(raw) >= 2:
            low, high = raw[0], raw[1]
        else:
            raise SemanticCompileError("between requires [low, high] literal")
        params.extend([low, high])
        return (
            f"{left} BETWEEN {_literal(low, 'number')} AND {_literal(high, 'number')}",
            height_used,
            params,
        )
    if pred.operator in {"in", "not_in"}:
        left, height_used, params = _operand_sql(
            alias, entity, pred.left, col_map=col_map
        )
        values = pred.right.value if pred.right else []
        if not isinstance(values, (list, tuple)):
            values = [values]
        lits = ", ".join(_literal(v, "text") for v in values)
        params.extend(list(values))
        kw = "IN" if pred.operator == "in" else "NOT IN"
        return f"{left} {kw} ({lits})", height_used, params
    left_sql, h1, p1 = _operand_sql(alias, entity, pred.left, col_map=col_map)
    right_sql, h2, p2 = _operand_sql(alias, entity, pred.right, col_map=col_map)
    op = _OPS.get(pred.operator)
    if op is None:
        if pred.operator == "neq":
            op = "<>"
        elif pred.operator == "contains":
            return f"{left_sql} ILIKE {_literal('%' + str(pred.right.value if pred.right else '') + '%', 'text')}", h1 or h2, p1 + p2
        else:
            raise SemanticCompileError(f"unknown operator: {pred.operator}")
    return f"{left_sql} {op} {right_sql}", h1 or h2, p1 + p2


def _filter_sql(
    alias: str,
    entity: str,
    spec: FilterSpec,
    col_map: dict[str, str] | None = None,
) -> tuple[str, bool]:
    try:
        field, col = _field_col(alias, entity, spec.field, col_map)
    except UnknownSemanticFieldError as exc:
        raise SemanticCompileError(str(exc)) from exc
    height_used = spec.field == "height_m"
    if spec.field in {"approval_date", "permit_date"}:
        return _approval_date_sql(col, spec), height_used
    if spec.operator == "is_null":
        return f"{col} IS NULL", height_used
    if spec.operator == "is_not_null":
        return f"{col} IS NOT NULL", height_used
    if spec.operator == "not_in":
        values = spec.value if isinstance(spec.value, (list, tuple)) else [spec.value]
        lits = ", ".join(_literal(v, field.data_type) for v in values)
        return f"{col} NOT IN ({lits})", height_used
    if spec.operator == "in":
        values = spec.value if isinstance(spec.value, (list, tuple)) else [spec.value]
        lits = ", ".join(_literal(v, field.data_type) for v in values)
        return f"{col} IN ({lits})", height_used
    if spec.field == "special_land" and not col_map:
        a6 = _col(alias, "A6")
        a7 = _col(alias, "A7")
        raw = str(spec.value or "").strip()
        if raw in {"산", "산지"}:
            inner = f"({a6}::text = '2' OR TRIM(COALESCE({a7}::text, '')) = '산')"
        elif raw in {"일반", "일반지번"}:
            inner = f"({a6}::text = '1' OR TRIM(COALESCE({a7}::text, '')) = '일반')"
        else:
            inner = f"TRIM(COALESCE({a7}::text, '')) = {_literal(raw, 'text')}"
        if spec.operator == "neq":
            return f"(NOT {inner})", height_used
        return inner, height_used
    if spec.operator == "contains":
        pattern = spec.value
        if spec.field == "structure" and isinstance(pattern, str):
            mapped = STRUCTURE_ALIASES.get(pattern)
            if mapped:
                return f"{col} ILIKE {_literal(mapped, 'text')}", height_used
        return f"{col} ILIKE {_literal(f'%{pattern}%', 'text')}", height_used
    if spec.field == "structure" and spec.operator == "neq" and isinstance(spec.value, str):
        mapped = STRUCTURE_ALIASES.get(spec.value) or f"%{spec.value}%"
        return f"NOT ({col} ILIKE {_literal(mapped, 'text')})", height_used
    if spec.operator == "between":
        left = _literal(spec.value, field.data_type)
        right = _literal(spec.value2, field.data_type)
        expr = f"{col}::float8" if field.data_type == "number" else col
        return f"{expr} BETWEEN {left} AND {right}", height_used
    if spec.value_field:
        other, right = _field_col(alias, entity, spec.value_field, col_map)
        left = f"{col}::float8" if field.data_type == "number" else col
        if other.data_type == "number":
            right = f"{right}::float8"
        op = _OPS.get(spec.operator)
        if op is None:
            raise SemanticCompileError(f"unknown operator: {spec.operator}")
        return f"{left} {op} {right}", height_used
    if spec.field == "structure" and spec.operator == "eq" and isinstance(spec.value, str):
        mapped = STRUCTURE_ALIASES.get(spec.value)
        if mapped:
            return f"{col} ILIKE {_literal(mapped, 'text')}", height_used
    op = _OPS.get(spec.operator)
    if op is None:
        raise SemanticCompileError(f"unknown operator: {spec.operator}")
    expr = f"{col}::float8" if field.data_type == "number" else col
    return f"{expr} {op} {_literal(spec.value, field.data_type)}", height_used


def _apply_spatial_relations(
    alias: str,
    plan: SemanticQueryPlan,
    tables: list[str],
    joins: list[str],
    where: list[str],
    spatial_order: list[str],
) -> tuple[bool, set[str]]:
    """spatial_relations → JOIN/WHERE. 물리 함수명은 compiler 정책만 고른다."""
    from llm2sql.semantic_plan.spatial_policy import resolve_spatial_policy

    uses_boundary = False
    used_places: set[str] = set()
    admin_alias_used = False
    for index, rel in enumerate(plan.spatial_relations):
        policy = resolve_spatial_policy(rel.relation)
        target = rel.target
        place_name = (
            target.place.name.strip() if target.place and target.place.name else None
        )
        target_entity = getattr(target, "entity", None) or "admin_area"
        if policy.kind == "predicate":
            target_entity = getattr(target, "entity", None) or "admin_area"
            if not place_name and target_entity != "industrial_complex":
                raise SemanticCompileError(f"{rel.relation} requires a place target")
            if place_name:
                used_places.add(place_name)
            if target_entity == "industrial_complex":
                d_alias = "ind" if index == 0 else f"ind{index}"
            else:
                d_alias = "a" if not admin_alias_used else f"a{index}"
                admin_alias_used = True
            table, name_clause = _spatial_target_sql(
                target_entity, d_alias, place_name or ""
            )
            if table not in tables:
                tables.append(table)
            if target_entity == "industrial_complex":
                exists = (
                    f"EXISTS (SELECT 1 FROM {_ident(table, physical=True)} {d_alias} "
                    f"WHERE {policy.postgis_fn}({alias}.geometry, {d_alias}.geometry)"
                )
                if name_clause and name_clause != "TRUE":
                    exists += f" AND {name_clause}"
                exists += ")"
                where.append(exists)
            else:
                joins.append(
                    f"JOIN {_ident(table, physical=True)} {d_alias} "
                    f"ON {policy.postgis_fn}({alias}.geometry, {d_alias}.geometry)"
                )
                if name_clause and name_clause != "TRUE":
                    where.append(name_clause)
            uses_boundary = True
            continue
        if policy.kind in {"distance", "distance_outside"}:
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
                    f"{_distance_origin_sql(z_alias, plan)}::geography, "
                    f"{meters})"
                )
                if policy.kind == "distance_outside":
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
        if policy.kind == "nearest":
            if not place_name:
                raise SemanticCompileError("nearest requires a place target")
            used_places.add(place_name)
            z_alias = "z" if index == 0 else f"z{index}"
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
            spatial_order.append(f"ST_Distance({alias}.geometry, {z_alias}.geom)")
            uses_boundary = True
            continue
        if policy.kind == "ratio":
            if not place_name:
                raise SemanticCompileError("overlap_ratio requires a place target")
            used_places.add(place_name)
            d_alias = "a" if not admin_alias_used else f"a{index}"
            admin_alias_used = True
            if ADMIN_TABLE not in tables:
                tables.append(ADMIN_TABLE)
            ratio = rel.min_ratio if rel.min_ratio is not None else 0.5
            joins.append(
                f"JOIN {_ident(ADMIN_TABLE, physical=True)} {d_alias} "
                f"ON ST_Intersects({alias}.geometry, {d_alias}.geometry)"
            )
            where.append(_admin_name_sql(d_alias, place_name))
            where.append(f"{d_alias}.\"ADM_CD\" LIKE '21%'")
            where.append(
                "ST_Area(ST_Intersection("
                f"{alias}.geometry, {d_alias}.geometry)) "
                f"/ NULLIF(ST_Area({alias}.geometry), 0) >= {sql_number(float(ratio))}"
            )
            uses_boundary = True
            continue
        raise SemanticCompileError(f"unsupported spatial relation: {rel.relation}")
    return uses_boundary, used_places


def _apply_canonical_joins(
    alias: str,
    plan: SemanticQueryPlan,
    tables: list[str],
    joins: list[str],
    where: list[str],
) -> None:
    from llm2sql.semantic_catalog.registry import get_edge

    sql_pat = re.compile(r"(?i)\b(select|insert|update|delete|st_[a-z]+)\b")
    for spec in plan.joins:
        extra = spec.extra or {}
        if sql_pat.search(str(extra)):
            raise SemanticCompileError("join extra cannot contain SQL")
        try:
            edge = get_edge(spec.edge_id)
        except KeyError as exc:
            raise SemanticCompileError(f"unknown join edge: {spec.edge_id}") from exc
        if edge.edge_id == "building_in_admin":
            if ADMIN_TABLE not in tables:
                tables.append(ADMIN_TABLE)
            if not any(ADMIN_TABLE in item for item in joins):
                joins.append(
                    f"JOIN {_ident(ADMIN_TABLE, physical=True)} adm "
                    f"ON ST_Intersects({alias}.geometry, adm.geometry)"
                )
        elif edge.edge_id == "building_in_basic_zone":
            if BASIC_ZONE_TABLE not in tables:
                tables.append(BASIC_ZONE_TABLE)
            if not any(BASIC_ZONE_TABLE in item for item in joins):
                joins.append(
                    f"JOIN {_ident(BASIC_ZONE_TABLE, physical=True)} bas "
                    f"ON ST_Intersects({alias}.geometry, bas.geometry)"
                )
        elif edge.edge_id == "building_in_industrial":
            if INDUSTRIAL_TABLE not in tables:
                tables.append(INDUSTRIAL_TABLE)
            if not any(INDUSTRIAL_TABLE in item for item in joins):
                joins.append(
                    f"JOIN {_ident(INDUSTRIAL_TABLE, physical=True)} ind "
                    f"ON ST_Intersects({alias}.geometry, ind.geometry)"
                )
        else:
            raise SemanticCompileError(f"uncompiled join edge: {edge.edge_id}")


def _sigungu_name_sql(alias: str) -> str:
    whens = " ".join(
        f"WHEN {alias}.\"A3\" LIKE {_literal(code + '%', 'text')} THEN {_literal(name, 'text')}"
        for name, code in BUSAN_GU_CODES.items()
    )
    return f"(CASE {whens} ELSE NULL END)"


def _distance_origin_sql(z_alias: str, plan: SemanticQueryPlan) -> str:
    if "distance_from_centroid" in (plan.assumptions or []):
        return f"ST_Centroid({z_alias}.geom)"
    return f"{z_alias}.geom"


def _a4_place_sql(alias: str, place: str) -> str:
    col = f'{alias}."A4"'
    if place.endswith(("동", "가", "리", "로")):
        return f"({col} LIKE {_literal('% ' + place, 'text')} OR {col} = {_literal(place, 'text')})"
    code = BUSAN_GU_CODES.get(place)
    if code:
        return f'{alias}."A3" LIKE {_literal(code + "%", "text")}'
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


def _entity_place_sql(alias: str, entity: str, place: str) -> str:
    if entity == "admin_area":
        return _admin_name_sql(alias, place)
    if entity == "basic_zone":
        return f'{alias}."SIG_KOR_NM" LIKE {_literal("%" + place + "%", "text")}'
    if entity == "industrial_complex":
        if not (place or "").strip():
            return "TRUE"
        parts = [p.strip() for p in re.split(r"[·･、,/|]", place) if p.strip()]
        if len(parts) >= 2:
            clauses = []
            for part in parts:
                pat = _literal("%" + part + "%", "text")
                clauses.append(
                    f'({alias}."A8" ILIKE {pat} OR {alias}."A9" ILIKE {pat})'
                )
            return "(" + " OR ".join(clauses) + ")"
        pat = _literal("%" + place + "%", "text")
        return f'({alias}."A8" ILIKE {pat} OR {alias}."A9" ILIKE {pat})'
    return _a4_place_sql(alias, place)


def _spatial_target_sql(entity: str, alias: str, place: str) -> tuple[str, str]:
    if entity == "basic_zone":
        return BASIC_ZONE_TABLE, _entity_place_sql(alias, entity, place)
    if entity == "industrial_complex":
        return INDUSTRIAL_TABLE, _entity_place_sql(alias, entity, place)
    if entity == "building":
        return BUILDING_TABLE, _a4_place_sql(alias, place)
    clause = _admin_name_sql(alias, place)
    if entity == "admin_area":
        clause = f"{clause} AND {alias}.\"ADM_CD\" LIKE '21%'"
    return ADMIN_TABLE, clause


def _predicate_node_ids(pred: PredicateSpec) -> list[str]:
    from llm2sql.semantic_plan.predicate_utils import walk_predicate

    out: list[str] = []
    for index, node in enumerate(walk_predicate(pred)):
        if node.op == "cmp" and node.left and node.left.field:
            out.append(f"{node.left.field}:{node.operator}:{index}")
        else:
            out.append(f"{node.op}:{index}")
    return out


def _plan_uses_d198_slots(plan: SemanticQueryPlan) -> bool:
    fields = {item.field for item in plan.filters}
    from llm2sql.semantic_plan.predicate_utils import walk_predicate

    pred = effective_predicate(plan)
    if pred is not None:
        for node in walk_predicate(pred):
            if node.op == "cmp" and node.left and node.left.field:
                fields.add(node.left.field)
    return bool(
        fields & {"detail_usage", "usage_class", "ledger_kind", "permit_date"}
    ) or (
        "d198_ledger" in (plan.assumptions or [])
    )


def _d198_table_for_plan(plan: SemanticQueryPlan) -> str | None:
    if plan.entity != "building" or not _plan_uses_d198_slots(plan):
        return None
    place = plan.scope.place.name.strip() if plan.scope and plan.scope.place else ""
    gu = place if place.endswith(("구", "군")) else None
    table = d198_table_for_gu(gu) if gu else None
    if table is None:
        raise SemanticCompileError(
            "detail_usage/usage_class require a D198-covered district"
        )
    return table


def _column_override(plan: SemanticQueryPlan) -> dict[str, str]:
    if _d198_table_for_plan(plan):
        return dict(D198_BUILDING_COLUMNS)
    return {}


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


def _approval_year_expr(col: str) -> str:
    return f"LEFT(regexp_replace({col}::text, '[^0-9]', '', 'g'), 4)"


def _approval_decade_expr(col: str) -> str:
    return f"(({_approval_year_expr(col)})::int / 10 * 10)"


def _approval_date_sql(col: str, spec: FilterSpec) -> str:
    """사용승인일 텍스트 컬럼을 연도 또는 날짜로 비교한다."""
    year_expr = _approval_year_expr(col)
    valid = f"({col}::text ~ '^[0-9]{{4}}')"
    op = _OPS.get(spec.operator)
    if spec.operator == "between":
        lo, hi = spec.value, spec.value2
        return f"{valid} AND {year_expr}::int BETWEEN {int(lo)} AND {int(hi)}"
    raw = spec.value
    if isinstance(raw, str) and re.match(r"^\d{4}-\d{2}-\d{2}", raw):
        year = int(raw[:4])
        iso = raw[:10]
        date_ok = f"{col}::text ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}'"
        year_ok = f"{col}::text ~ '^[0-9]{{4}}$'"
        if op is None:
            raise SemanticCompileError(f"unknown operator: {spec.operator}")
        return (
            f"{valid} AND ("
            f"({date_ok} AND {col}::date {op} DATE '{iso}') OR "
            f"({year_ok} AND {year_expr}::int {op} {year})"
            f")"
        )
    if op is None:
        raise SemanticCompileError(f"unknown operator: {spec.operator}")
    return f"{valid} AND {year_expr}::int {op} {int(float(raw))}"


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


def _assert_table_columns(sql: str, entity: str, tables: list[str]) -> str:
    """D010에 D198 전용 컬럼(A33/A34/A30)을 붙이지 않는다."""
    from llm2sql.sql_d010_guard import rewrite_d198_columns_on_d010, uses_d010_only

    using_d010 = entity == "building" or any("AL_D010" in (t or "") for t in tables)
    using_d198 = any("AL_D198" in (t or "") for t in tables)
    if using_d010 and not using_d198:
        sql = rewrite_d198_columns_on_d010(sql)
        if uses_d010_only(sql) and re.search(r'"(A33|A34|A30)"', sql):
            raise SemanticCompileError("D198 columns cannot be used on D010")
    return sql
