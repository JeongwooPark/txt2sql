"""레거시 라우트가 질문 슬롯을 100% 커버할 때만 실행하도록 한다."""

from __future__ import annotations

from dataclasses import dataclass, field

from llm2sql.query_understanding.contract import QueryContract


@dataclass(frozen=True)
class RouteCapability:
    route: str
    entities: frozenset[str] = field(default_factory=lambda: frozenset({"building"}))
    supports_or: bool = False
    supports_not: bool = False
    supports_between: bool = False
    supports_field_compare: bool = False
    supports_multiple_predicates: bool = False
    supports_group_by: bool = False
    supports_multiple_aggregates: bool = False
    supports_spatial: bool = False
    supported_fields: frozenset[str] = field(default_factory=frozenset)


SIMPLE_COUNT = RouteCapability(
    route="legacy_simple_count",
    supports_multiple_predicates=False,
)
PLAN_ROUTE = RouteCapability(
    route="semantic_plan",
    entities=frozenset(
        {"building", "admin_area", "basic_zone", "industrial_complex"}
    ),
    supports_or=True,
    supports_not=True,
    supports_between=True,
    supports_field_compare=True,
    supports_multiple_predicates=True,
    supports_group_by=True,
    supports_multiple_aggregates=True,
    supports_spatial=True,
)


def missing_slots(capability: RouteCapability, contract: QueryContract) -> list[str]:
    missing: list[str] = []
    if any(span.kind == "or" for span in contract.boolean_ops) and not capability.supports_or:
        missing.append("or")
    if any(span.kind == "not" for span in contract.boolean_ops) and not capability.supports_not:
        missing.append("not")
    if contract.ranges and not capability.supports_between:
        missing.append("between")
    if contract.comparisons and not capability.supports_field_compare:
        missing.append("field_compare")
    n_pred = len(contract.ranges) + len(contract.comparisons) + len(contract.metrics)
    if n_pred >= 2 and not capability.supports_multiple_predicates:
        missing.append("multiple_predicates")
    if len(contract.aggregations) >= 2 and not capability.supports_multiple_aggregates:
        missing.append("multiple_aggregates")
    if contract.groups and not capability.supports_group_by:
        missing.append("group_by")
    return missing


def legacy_route_eligible(contract: QueryContract) -> bool:
    return not missing_slots(SIMPLE_COUNT, contract)
