"""평가 레코드 JSON schema (Pydantic)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CaseStatus = Literal["draft", "verified", "deprecated"]
SplitName = Literal["train", "dev", "test", "adversarial", "conversation", "candidate"]


class GoldPlanCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    question: str
    status: CaseStatus = "draft"
    split: SplitName = "test"
    source: str = ""
    holdout: str | None = None
    gold_plan: dict[str, Any] | None = None
    gold_route: str | None = None
    gold_clarify: bool = False
    gold_result_hash: str | None = None
    result_mode: Literal["set", "sequence"] = "set"
    notes: str = ""
    verification: str = ""


class EvalItemResult(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    question: str
    status: CaseStatus
    pass_: bool = Field(alias="pass")
    error_codes: list[str] = Field(default_factory=list)
    predicted_route: str | None = None
    gold_route: str | None = None
    route_match: bool | None = None
    plan_match: bool | None = None
    result_match: bool | None = None
    clarify_match: bool | None = None
    predicted_clarify: bool | None = None
    gold_clarify: bool | None = None
    sql_executed: bool | None = None
    latency_ms: int | None = None
    notes: str = ""
    root_causes: list[str] = Field(default_factory=list)
    stage_latency_ms: dict[str, int] = Field(default_factory=dict)
    selected_route: str | None = None
    compiled_sql: str | None = None


class EvalSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    mode: str
    n: int
    n_verified: int
    passed: int
    failed: int
    error_counts: dict[str, int] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)
    env_blocked: bool = False
