"""Canonical QueryIR package."""

from txt2sql.query_ir.adapters import contract_to_query_ir, plan_to_query_ir, query_ir_to_semantic_plan
from txt2sql.query_ir.completeness import CompletenessReport, assess_completeness
from txt2sql.query_ir.models import QueryIR, QueryIRError
from txt2sql.query_ir.normalize import assert_no_physical_names, normalize_query_ir

__all__ = [
    "CompletenessReport",
    "QueryIR",
    "QueryIRError",
    "assert_no_physical_names",
    "assess_completeness",
    "contract_to_query_ir",
    "normalize_query_ir",
    "plan_to_query_ir",
    "query_ir_to_semantic_plan",
]
