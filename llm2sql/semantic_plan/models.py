"""Semantic Query Plan 데이터 모델.

LLM은 물리 테이블/컬럼이 아니라 canonical semantic field만 출력한다.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

QueryKind = Literal["count", "list", "rank", "aggregate", "distribution"]
EntityName = Literal["building", "admin_area", "basic_zone", "industrial_complex"]
FilterOperator = Literal[
    "eq",
    "neq",
    "gt",
    "gte",
    "lt",
    "lte",
    "contains",
    "in",
    "not_in",
    "between",
    "is_null",
    "is_not_null",
]
PredicateOp = Literal["and", "or", "not", "cmp"]
OperandKind = Literal["field", "literal"]
SpatialRelationName = Literal[
    "within",
    "intersects",
    "within_distance",
    "outside_distance",
    "touches",
    "covered_by",
    "buffer",
    "nearest",
    "overlap_ratio",
]
AggregateFunction = Literal["count", "avg", "sum", "min", "max", "median"]
PlaceKind = Literal[
    "sido",
    "gu",
    "legal_dong",
    "admin_dong",
    "basic_zone",
    "unknown",
]


class SemanticPlanError(Exception):
    """SQP 계층 공통 예외."""


class SemanticPlanGenerationError(SemanticPlanError):
    """Plan JSON 생성·파싱 실패."""


class SemanticCompileError(SemanticPlanError):
    """검증된 Plan을 SQL로 컴파일하지 못함."""


class UnknownSemanticFieldError(SemanticPlanError):
    """catalog에 없는 semantic field."""


UnknownSemanticFieldError = UnknownSemanticFieldError
SemanticCompileError = SemanticCompileError


class PlaceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    kind: PlaceKind = "unknown"


class ScopeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    place: PlaceSpec | None = None
    spatial_mode: Literal["auto", "attribute", "boundary"] = "auto"


class FilterSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    operator: FilterOperator
    value: Any | None = None
    value2: Any | None = None
    unit: str | None = None
    value_field: str | None = None


class OperandSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: OperandKind
    field: str | None = None
    value: Any | None = None
    unit: str | None = None


class PredicateSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: PredicateOp
    args: list[PredicateSpec] | None = None
    operator: FilterOperator | None = None
    left: OperandSpec | None = None
    right: OperandSpec | None = None


class ProjectionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    alias: str | None = None


class HavingSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    predicate: PredicateSpec


class JoinSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edge_id: str
    extra: dict[str, Any] | None = None


class PlanEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    span_start: int | None = None
    span_end: int | None = None
    source: str = "heuristic"
    note: str = ""


class PlanConfidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity: float = 0.0
    scope: float = 0.0
    fields: float = 0.0
    predicates: float = 0.0
    aggregation: float = 0.0
    spatial: float = 0.0
    overall: float = 0.0


class AggregationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    function: AggregateFunction
    field: str | None = None
    alias: str | None = None


class OrderSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    direction: Literal["asc", "desc"] = "asc"
    nulls: Literal["first", "last"] = "last"


class SpatialTargetSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity: EntityName | None = None
    place: PlaceSpec | None = None
    longitude: float | None = None
    latitude: float | None = None


class SpatialRelationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation: SpatialRelationName
    target: SpatialTargetSpec
    distance_m: float | None = None
    min_ratio: float | None = Field(default=None, ge=0.0, le=1.0)


class SemanticQueryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["1.0", "1.1"] = "1.0"
    query_kind: QueryKind
    entity: EntityName

    scope: ScopeSpec | None = None

    filters: list[FilterSpec] = Field(default_factory=list)
    predicate: PredicateSpec | None = None
    select: list[str] = Field(default_factory=list)
    projections: list[ProjectionSpec] = Field(default_factory=list)
    aggregations: list[AggregationSpec] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    having: HavingSpec | None = None
    joins: list[JoinSpec] = Field(default_factory=list)
    order_by: list[OrderSpec] = Field(default_factory=list)
    limit: int | None = Field(default=None, ge=1, le=1000)

    spatial_relations: list[SpatialRelationSpec] = Field(default_factory=list)

    requires_clarification: bool = False
    ambiguities: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    unsupported_reason: str | None = None
    model_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence: list[PlanEvidence] = Field(default_factory=list)
    slot_confidence: PlanConfidence | None = None


class PlanValidationResult:
    __slots__ = ("status", "score", "errors", "warnings", "plan")

    def __init__(
        self,
        *,
        status: str,
        score: float,
        errors: list[str],
        warnings: list[str],
        plan: SemanticQueryPlan,
    ) -> None:
        self.status = status  # ready | clarify | fallback
        self.score = score
        self.errors = errors
        self.warnings = warnings
        self.plan = plan


PredicateSpec.model_rebuild()
HavingSpec.model_rebuild()
SemanticQueryPlan.model_rebuild()
SemanticQueryPlanV11 = SemanticQueryPlan
