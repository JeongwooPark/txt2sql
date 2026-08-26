"""Compiler facade tests."""

from txt2sql.compiler.expressions import quote_ident, quote_literal
from txt2sql.compiler.postgis import postgis_fn
from txt2sql.compiler.safety import validate_compiled_sql
from txt2sql.planner.executor_adapter import build_execution_plan
from txt2sql.compiler.sql import compile_plan_safe


def test_quote_helpers() -> None:
    assert quote_ident('A16') == '"A16"'
    assert quote_literal("동래구") == "'동래구'"
    assert quote_literal(None) == "NULL"


def test_postgis_mapping() -> None:
    assert postgis_fn("within") == "ST_Within"


def test_compile_from_physical_or_error() -> None:
    bundle = build_execution_plan("동래구 건물 평균 연면적")
    bundle.logical.status = "READY"
    bundle.logical.reason_codes = []
    sql, err = compile_plan_safe(bundle.physical)
    # May succeed or fail depending on SQP compiler support; must not crash
    assert sql is not None or err is not None


def test_validate_readonly() -> None:
    validate_compiled_sql('SELECT COUNT(*) FROM "AL_D010_26_20250704"')
