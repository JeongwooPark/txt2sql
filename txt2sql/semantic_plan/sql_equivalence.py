"""Plan predicate tree와 SQL WHERE boolean tree의 canonical 동등성."""

from __future__ import annotations

import re
from typing import Any

import sqlglot
from sqlglot import exp

from txt2sql.semantic_plan.models import PredicateSpec, SemanticQueryPlan
from txt2sql.semantic_plan.predicate_utils import effective_predicate


def _norm_ident(name: str) -> str:
    return name.strip('"').lower()


def sql_boolean_tree(sql: str) -> dict[str, Any] | None:
    parsed = sqlglot.parse_one(sql, read="postgres")
    where = parsed.find(exp.Where) if parsed else None
    if where is None:
        return None
    return _node(where.this)


def _node(node: exp.Expression | None) -> dict[str, Any] | None:
    if node is None:
        return None
    if isinstance(node, exp.Paren):
        return _node(node.this)
    if isinstance(node, exp.And):
        return {"op": "and", "args": [_node(node.left), _node(node.right)]}
    if isinstance(node, exp.Or):
        return {"op": "or", "args": [_node(node.left), _node(node.right)]}
    if isinstance(node, exp.Not):
        return {"op": "not", "args": [_node(node.this)]}
    if isinstance(node, (exp.GT, exp.GTE, exp.LT, exp.LTE, exp.EQ, exp.NEQ)):
        mapping = {
            exp.GT: "gt",
            exp.GTE: "gte",
            exp.LT: "lt",
            exp.LTE: "lte",
            exp.EQ: "eq",
            exp.NEQ: "neq",
        }
        return {
            "op": "cmp",
            "operator": mapping[type(node)],
            "sql": node.sql(dialect="postgres"),
        }
    if isinstance(node, exp.Between):
        return {"op": "cmp", "operator": "between", "sql": node.sql(dialect="postgres")}
    return {"op": "other", "sql": node.sql(dialect="postgres")}


def plan_boolean_tree(plan: SemanticQueryPlan) -> dict[str, Any] | None:
    pred = effective_predicate(plan)
    if pred is None:
        return None
    return _pred(pred)


def _pred(pred: PredicateSpec) -> dict[str, Any]:
    if pred.op in {"and", "or", "not"}:
        return {"op": pred.op, "args": [_pred(child) for child in (pred.args or [])]}
    return {"op": "cmp", "operator": pred.operator}


def _flatten_ops(tree: dict[str, Any] | None) -> list[str]:
    if not tree:
        return []
    if tree.get("op") == "cmp":
        return [str(tree.get("operator"))]
    out: list[str] = [str(tree.get("op"))]
    for child in tree.get("args") or []:
        if isinstance(child, dict):
            out.extend(_flatten_ops(child))
    return out


def verify_plan_sql_equivalence(plan: SemanticQueryPlan, sql: str) -> list[str]:
    errors: list[str] = []
    upper = sql.upper()
    if plan.query_kind == "count" and "COUNT(" not in upper:
        errors.append("P05")
    if plan.aggregations:
        for item in plan.aggregations:
            fn = item.function.upper()
            if fn == "SUM" and "SUM(" not in upper:
                errors.append("P05")
            if fn == "AVG" and "AVG(" not in upper:
                errors.append("P05")
            if fn == "MAX" and "MAX(" not in upper:
                errors.append("P05")
            if fn == "MIN" and "MIN(" not in upper:
                errors.append("P05")
            if fn == "COUNT" and "COUNT(" not in upper:
                errors.append("P05")
    if plan.order_by:
        want = "ASC" if plan.order_by[0].direction == "asc" else "DESC"
        if want not in upper:
            errors.append("P06")
    if plan.limit is not None and not re.search(rf"LIMIT\s+{plan.limit}\b", upper):
        errors.append("P06")
    plan_ops = set(_flatten_ops(plan_boolean_tree(plan)))
    sql_ops = set(_flatten_ops(sql_boolean_tree(sql)))
    if "or" in plan_ops and "or" not in sql_ops:
        errors.append("P04")
    if "not" in plan_ops and "not" not in sql_ops:
        errors.append("P04")
    return list(dict.fromkeys(errors))
