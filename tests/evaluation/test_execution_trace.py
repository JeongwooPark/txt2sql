"""ExecutionTrace tests — Phase 2 observability."""

from __future__ import annotations

from txt2sql.evaluation.execution_trace import (
    attach_execution_trace,
    build_execution_trace,
    diagnose_from_trace,
)
from txt2sql.query_ir.models import AggregationIR, QueryIR, ScopeIR


class _FakeBinding:
    def __init__(self, dataset: str, concept: str, physical_field: str) -> None:
        self.dataset = dataset
        self.concept = concept
        self.physical_field = physical_field


class _FakeLogical:
    status = "READY"
    reason_codes: list[str] = []
    bindings = [_FakeBinding("building_gis_d010", "building.height", "A16")]

    class root:
        op = "aggregate"


class _FakePlanBundle:
    def __init__(self) -> None:
        self.query_ir = QueryIR(
            task="aggregate",
            scope=ScopeIR(place="금정구"),
            aggregations=[AggregationIR(function="avg", field="height_m")],
        )
        self.logical = _FakeLogical()


def test_build_trace_semantic_v2_path() -> None:
    bundle = _FakePlanBundle()
    payload = {
        "ok": True,
        "sql": "SELECT AVG(A16) FROM ...",
        "rows": [{"avg": 42.5}],
        "execution_source": "semantic_v2",
        "compiler_source": "deterministic_compiler_v2",
        "query_ir_task": "aggregate",
    }
    trace = build_execution_trace(
        payload,
        question="금정구 건물 평균 높이",
        plan_bundle=bundle,
    )
    assert trace.execution_source == "semantic_v2"
    assert trace.query_ir is not None
    assert trace.logical_plan is not None
    assert trace.generated_sql is not None
    assert trace.trace_completeness.query_ir is True


def test_build_trace_legacy_router_minimal() -> None:
    payload = {
        "ok": True,
        "sql": "SELECT COUNT(*) ...",
        "rows": [{"count": 100}],
        "route": "semantic_plan_count",
        "execution_source": "legacy_router",
    }
    trace = build_execution_trace(payload, question="금정구 건물 수")
    assert trace.execution_source == "legacy_router"
    assert trace.trace_completeness.generated_sql is True


def test_diagnose_from_trace_missing_query_ir() -> None:
    trace = {
        "execution_source": "legacy_router",
        "trace_completeness": {"query_ir": False, "logical_plan": False, "generated_sql": True},
        "evaluation": {"error_stage": "understanding", "match": False},
    }
    ec, sub, conf = diagnose_from_trace(trace)
    assert ec == "BINDING"
    assert sub == "IR_MISSING"
    assert conf >= 0.75


def test_attach_execution_trace_on_payload() -> None:
    payload = {"ok": True, "sql": "SELECT 1", "rows": [], "execution_source": "rag_sql"}
    out = attach_execution_trace(payload, question="test")
    assert "execution_trace" in out
    assert out["execution_trace"]["execution_source"] == "rag_sql"
