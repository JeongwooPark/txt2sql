"""Dataset / column grain policy (D010 building vs D198 ledger)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from txt2sql.query_ir.models import QueryIR

DatasetGrain = Literal["d010", "d198"]

_D198_METRIC_CUES = (
    "연면적",
    "건물면적",
    "대지면적",
    "높이",
    "지상층",
    "지하층",
    "층수",
    "건폐",
    "용적",
    "사용승인",
    "건축년",
    "허가일",
    "경과",
    "년 이상",
    "년 이하",
    "세부용도",
    "건축물종류",
    "구조",
    "대지",
)

_D198_PREDICATE_FIELDS = frozenset(
    {
        "detail_usage",
        "usage_class",
        "ledger_kind",
        "permit_date",
        "approval_date",
        "building_age_years",
        "height_m",
        "gross_floor_area_m2",
        "building_area_m2",
        "site_area_m2",
        "ground_floors",
        "basement_floors",
        "building_coverage_ratio",
        "floor_area_ratio",
        "structure",
    }
)

_D198_TEMPORAL_FIELDS = frozenset({"approval_date", "permit_date", "building_age_years"})


def needs_d198_building_grain(question: str) -> bool:
    """D198 세부대장 grain이 필요한지 (단순 대분류 용도 건수는 D010+A9)."""
    q = (question or "").strip()
    if not q:
        return False
    from txt2sql.domain import extract_detail_usages

    if extract_detail_usages(q):
        return True
    if any(cue in q for cue in _D198_METRIC_CUES):
        return True
    from txt2sql.intent_router import looks_like_age_question

    if looks_like_age_question(q):
        return True
    return False


def simple_building_usage_count(question: str) -> bool:
    """구/동 + 대분류 용도 건수 → D010 + A9."""
    return not needs_d198_building_grain(question)


def query_ir_needs_d198(ir: QueryIR, question: str = "") -> bool:
    """QueryIR slots + NL cues → D198 ledger grain."""
    fields = {p.field for p in ir.predicates if p.field}
    if fields & _D198_PREDICATE_FIELDS:
        return True
    if ir.temporal is not None and (
        ir.temporal.field in _D198_TEMPORAL_FIELDS or ir.temporal.age_years is not None
    ):
        return True
    if any(a.field in _D198_PREDICATE_FIELDS for a in ir.aggregations if a.field):
        return True
    bare_usage = "usage" in fields and "detail_usage" not in fields
    if bare_usage and ir.task in {"count", "list", "rank"}:
        if question and not needs_d198_building_grain(question):
            return False
    if question and needs_d198_building_grain(question):
        return True
    return False


def resolve_dataset_grain(ir: QueryIR, question: str = "") -> DatasetGrain:
    """Single entry point for D010 vs D198 selection."""
    return "d198" if query_ir_needs_d198(ir, question) else "d010"


def grain_to_assumption(grain: DatasetGrain) -> str:
    return "d198_ledger" if grain == "d198" else "d010_gis"
