"""Canonical QueryIR v2 — semantic meaning source of truth.

Physical table/column names and raw SQL must never appear in QueryIR fields.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TaskName = Literal[
    "count",
    "list",
    "aggregate",
    "group",
    "rank",
    "compare",
    "distribution",
    "ratio",
    "meta",
    "unknown",
]
EntityName = Literal["building", "admin_area", "basic_zone", "industrial_complex", "unknown"]
ResultShape = Literal["scalar", "list", "table", "map", "chart", "text", "unknown"]
PredicateOperator = Literal[
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
AggFunction = Literal[
    "count",
    "avg",
    "sum",
    "min",
    "max",
    "median",
    "stddev",
    "percentile",
    "ratio",
    "derived",
]


class QueryIRError(ValueError):
    """QueryIR validation / adapter error."""


class ProvenanceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = ""
    start: int | None = None
    end: int | None = None
    kind: str | None = None
    value: Any | None = None


class ScopeIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    place: str | None = None
    place_kind: str | None = None
    spatial_mode: Literal["auto", "attribute", "boundary"] = "auto"


class PredicateIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str | None = None
    operator: PredicateOperator | None = None
    value: Any | None = None
    value2: Any | None = None
    unit: str | None = None
    value_field: str | None = None
    negated: bool = False
    logical_group: Literal["and", "or"] | None = None
    children: list[PredicateIR] = Field(default_factory=list)
    provenance: ProvenanceSpan | None = None


class TemporalIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str | None = None
    operator: str | None = None
    value: Any | None = None
    value2: Any | None = None
    grain: str | None = None
    age_years: float | None = None


class SpatialIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation: str | None = None
    target_place: str | None = None
    target_entity: str | None = None
    distance_m: float | None = None
    min_ratio: float | None = None
    longitude: float | None = None
    latitude: float | None = None


class MeasureIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept: str
    alias: str | None = None
    unit: str | None = None
    provenance: ProvenanceSpan | None = None


class GrainIR(BaseModel):
    """Aggregation grain — what entity/unit is being counted or grouped."""

    model_config = ConfigDict(extra="forbid")

    entity: str | None = None
    distinct_key: str | None = None
    level: str | None = None


class AggregationIR(BaseModel):
    """Semantic aggregation contract — extends v2 without duplicating measures."""

    model_config = ConfigDict(extra="forbid")

    function: AggFunction
    field: str | None = None
    alias: str | None = None
    distinct: bool = False
    grain: GrainIR | None = None
    null_policy: Literal["EXCLUDE_NULL", "INCLUDE_NULL"] = "EXCLUDE_NULL"
    unit: str | None = None
    rounding: int | None = None
    percentile: float | None = None
    derived_kind: str | None = None
    left: str | None = None
    right: str | None = None
    has_denominator: bool | None = None


class DimensionIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    bins: bool = False


class ComparisonIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left_field: str | None = None
    right_field: str | None = None
    operator: PredicateOperator | None = None
    value: Any | None = None


class OrderingIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str | None = None
    direction: Literal["asc", "desc"] = "desc"


class InteractionIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal[
        "new_query",
        "refine_query",
        "explain_result",
        "visualize",
        "metadata",
        "help",
        "none",
    ] = "none"
    presentation: Literal["answer", "table", "map", "chart", "none"] | None = None
    deltas: list[dict[str, Any]] = Field(default_factory=list)


class UnresolvedIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str = ""
    span: ProvenanceSpan | None = None


class ProvenanceIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_text: str = ""
    source: Literal["contract", "semantic_plan", "manual", "merged"] = "manual"
    confidence: float | None = None
    notes: list[str] = Field(default_factory=list)
    legacy_hints: dict[str, Any] = Field(default_factory=dict)


class QueryIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: TaskName = "unknown"
    entity: EntityName = "building"
    scope: ScopeIR | None = None
    predicates: list[PredicateIR] = Field(default_factory=list)
    temporal: TemporalIR | None = None
    spatial: list[SpatialIR] = Field(default_factory=list)
    measures: list[MeasureIR] = Field(default_factory=list)
    aggregations: list[AggregationIR] = Field(default_factory=list)
    dimensions: list[DimensionIR] = Field(default_factory=list)
    comparisons: list[ComparisonIR] = Field(default_factory=list)
    ordering: list[OrderingIR] = Field(default_factory=list)
    limit: int | None = None
    outputs: list[str] = Field(default_factory=list)
    result_shape: ResultShape = "unknown"
    interaction: InteractionIR = Field(default_factory=InteractionIR)
    unresolved: list[UnresolvedIR] = Field(default_factory=list)
    provenance: ProvenanceIR = Field(default_factory=ProvenanceIR)

    @field_validator("limit")
    @classmethod
    def _limit_range(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value < 1 or value > 1000:
            raise QueryIRError(f"limit out of range: {value}")
        return value
