"""레거시 라우트가 Query Contract를 100% 지원할 때만 실행한다."""

from __future__ import annotations

from dataclasses import dataclass, field

from llm2sql.query_understanding.contract import QueryContract, extract_contract


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
    supported_group_fields: frozenset[str] = field(default_factory=frozenset)
    supports_multiple_aggregates: bool = False
    supported_aggregations: frozenset[str] = field(default_factory=frozenset)
    supports_spatial: bool = False
    supports_rank: bool = False
    supports_top_n: bool = False
    supports_output_projection: bool = False
    supports_ratio: bool = False
    supports_conditional_ratio: bool = False
    supports_multiple_ratios: bool = False
    supports_percentile: bool = False
    supports_derived_metric: bool = False
    supports_fixed_bins: bool = False
    supported_fields: frozenset[str] = field(default_factory=frozenset)


_COUNT_ONLY = frozenset({"count"})
_BASIC_AGGS = frozenset({"count", "avg", "sum", "min", "max", "median"})
_ALL_AGGS = _BASIC_AGGS | frozenset({"stddev", "percentile"})
_ALL_GROUPS = frozenset(
    {"usage", "structure", "legal_dong", "sigungu_name", "ground_floors"}
)

SIMPLE_COUNT = RouteCapability(
    route="legacy_simple_count",
    supports_multiple_predicates=False,
    supported_aggregations=_COUNT_ONLY,
)
PROFILE = RouteCapability(
    route="building_profile",
    supported_aggregations=frozenset(),
)
RANK = RouteCapability(
    route="building_rank",
    supports_rank=True,
    supports_top_n=True,
    supports_output_projection=True,
    supported_fields=frozenset(
        {
            "height_m",
            "gross_floor_area_m2",
            "building_area_m2",
            "site_area_m2",
            "ground_floors",
            "name",
            "legal_dong",
            "lot_address",
            "usage",
        }
    ),
)
NAME_LOOKUP = RouteCapability(
    route="building_name_lookup",
    supports_output_projection=True,
)
INDUSTRIAL = RouteCapability(
    route="industrial",
    entities=frozenset({"industrial_complex", "building"}),
    supports_spatial=True,
    supported_aggregations=_COUNT_ONLY,
)
D198 = RouteCapability(
    route="d198",
    supports_between=True,
    supports_multiple_predicates=True,
    supports_rank=True,
    supports_top_n=True,
    supports_fixed_bins=True,
    supported_aggregations=_COUNT_ONLY,
)
BAS = RouteCapability(
    route="bas",
    entities=frozenset({"basic_zone"}),
    supports_rank=True,
    supports_top_n=True,
    supported_aggregations=_COUNT_ONLY,
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
    supported_group_fields=_ALL_GROUPS,
    supports_multiple_aggregates=True,
    supported_aggregations=_ALL_AGGS,
    supports_spatial=True,
    supports_rank=True,
    supports_top_n=True,
    supports_output_projection=True,
    supports_ratio=True,
    supports_conditional_ratio=True,
    supports_multiple_ratios=True,
    supports_percentile=True,
    supports_derived_metric=True,
    supports_fixed_bins=True,
)


def capability_for(route: str) -> RouteCapability:
    intent = (route or "").strip()
    if intent == "semantic_plan" or intent.startswith("semantic_plan"):
        return PLAN_ROUTE
    if intent == "building_profile" or intent == "building_profile_compare":
        return PROFILE
    if intent.startswith("building_rank_"):
        return RANK
    if intent == "building_name_lookup":
        return NAME_LOOKUP
    if intent.startswith("industrial_") or intent == "buildings_in_industrial":
        return INDUSTRIAL
    if intent.startswith("d198_") or intent.startswith("building_age"):
        return D198
    if intent.startswith("bas_") or intent.startswith("bas_area"):
        return BAS
    if intent in {
        "building_place_count",
        "building_usage_count",
        "building_height_count",
        "building_floor_count",
        "building_structure_count",
        "building_special_land_count",
        "building_attr_count",
        "building_admin_dong_usage_count",
    }:
        return SIMPLE_COUNT
    return SIMPLE_COUNT


def missing_requirements(capability: RouteCapability, contract: QueryContract) -> list[str]:
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
    needed_aggs = {item.function for item in contract.aggregation_requests}
    if len(needed_aggs) >= 2 and not capability.supports_multiple_aggregates:
        missing.append("multiple_aggregates")
    unsupported = needed_aggs - set(capability.supported_aggregations)
    if unsupported:
        missing.append("unsupported_aggregation")
    group_fields = list(contract.group_fields)
    if group_fields:
        if not capability.supports_group_by:
            missing.append("group_by")
        elif capability.supported_group_fields and not set(group_fields) <= set(
            capability.supported_group_fields
        ):
            missing.append("unsupported_group_field")
    requires_rank = contract.operation in {"rank", "group_rank"} or bool(
        contract.order_requests
    )
    if requires_rank and not capability.supports_rank:
        missing.append("rank")
    if contract.limit is not None and requires_rank and not capability.supports_top_n:
        missing.append("top_n")
    if contract.output_fields and not capability.supports_output_projection:
        missing.append("output_projection")
    if contract.ratios and not capability.supports_ratio:
        missing.append("ratio")
    if any(item.has_denominator for item in contract.ratios) and not capability.supports_conditional_ratio:
        missing.append("conditional_ratio")
    if len(contract.ratios) >= 2 and not capability.supports_multiple_ratios:
        missing.append("multiple_ratios")
    if contract.percentile_requests and not capability.supports_percentile:
        missing.append("percentile")
    if contract.derived_metrics and not capability.supports_derived_metric:
        missing.append("derived_metric")
    if contract.fixed_bins and not capability.supports_fixed_bins:
        missing.append("fixed_bins")
    return list(dict.fromkeys(missing))


def missing_slots(capability: RouteCapability, contract: QueryContract) -> list[str]:
    return missing_requirements(capability, contract)


def fully_supports(capability: RouteCapability, contract: QueryContract) -> bool:
    return len(missing_requirements(capability, contract)) == 0


def legacy_route_eligible(contract: QueryContract) -> bool:
    return fully_supports(SIMPLE_COUNT, contract)


def route_allowed(intent: str, contract: QueryContract) -> bool:
    return fully_supports(capability_for(intent), contract)


def select_execution_path(
    question: str,
    *,
    conn=None,
    contract: QueryContract | None = None,
) -> str:
    """Contract → candidate routes → 전부 지원하는 첫 경로, 아니면 semantic_plan."""
    from llm2sql.intent_router import try_route
    from llm2sql.profile_qa import is_profile_question
    from llm2sql.route_dispatch import match_route

    contract = contract or extract_contract(question)
    match = match_route(question, conn=conn)
    candidates: list[str] = []
    if match.early is not None:
        candidates.append(match.early.intent)
    if is_profile_question(question):
        candidates.append("building_profile")
    deferred = match.deferred
    if deferred is None:
        deferred = try_route(question, conn=conn)
    if deferred is not None and deferred.intent not in candidates:
        candidates.append(deferred.intent)
    for intent in candidates:
        if fully_supports(capability_for(intent), contract):
            return intent
    return "semantic_plan"
