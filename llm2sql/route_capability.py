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
    supports_basement: bool = False
    supports_temporal: bool = False
    supported_fields: frozenset[str] = field(default_factory=frozenset)


_THRESHOLD_FIELDS = frozenset(
    {
        "height_m",
        "gross_floor_area_m2",
        "building_area_m2",
        "site_area_m2",
        "ground_floors",
        "basement_floors",
        "building_coverage_ratio",
        "floor_area_ratio",
    }
)
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
THRESHOLD_COUNT = RouteCapability(
    route="building_threshold_count",
    supports_between=True,
    supported_aggregations=_COUNT_ONLY,
)
THRESHOLD_LIST = RouteCapability(
    route="building_threshold_list",
    supports_between=True,
    supports_output_projection=True,
    supports_rank=True,
    supports_top_n=True,
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
    supports_temporal=True,
)
BAS = RouteCapability(
    route="bas",
    entities=frozenset({"basic_zone"}),
    supports_rank=True,
    supports_top_n=True,
    supported_aggregations=_COUNT_ONLY,
)
SPATIAL = RouteCapability(
    route="spatial",
    supports_spatial=True,
    supported_aggregations=_COUNT_ONLY,
    supports_output_projection=True,
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
    supports_basement=True,
    supports_temporal=True,
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
    if (
        intent.startswith("spatial_")
        or intent.startswith("place_buffer")
        or intent.startswith("buffer_")
        or intent in {
            "building_in_dong_spatial",
            "building_in_dong_spatial_list",
        }
    ):
        return SPATIAL
    if intent == "building_rank_compare":
        return RANK
    if intent in {
        "building_place_count",
        "building_usage_count",
        "building_structure_count",
        "building_special_land_count",
        "building_admin_dong_usage_count",
    }:
        return SIMPLE_COUNT
    if intent in {
        "building_height_count",
        "building_floor_count",
        "building_attr_count",
        "building_area_threshold_count",
    }:
        return THRESHOLD_COUNT
    if intent in {
        "building_area_threshold_list",
        "building_height_threshold_list",
        "building_floor_threshold_list",
        "building_attr_list",
        "building_structure_list",
        "building_special_land_list",
        "building_area_topn",
        "building_area_top1_value",
    }:
        return THRESHOLD_LIST
    return SIMPLE_COUNT


def _constraint_fields(contract: QueryContract) -> set[str]:
    fields: set[str] = set()
    for span in contract.metrics:
        if span.value:
            fields.add(str(span.value))
    for span in contract.numbers + contract.ranges:
        field = span.meta.get("field")
        if field:
            fields.add(str(field))
    return fields


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
    pred_fields = _constraint_fields(contract)
    n_pred = len(pred_fields) + len(contract.comparisons)
    if n_pred >= 2 and not capability.supports_multiple_predicates:
        missing.append("multiple_predicates")
    needed_aggs = {item.function for item in contract.aggregation_requests}
    if len(needed_aggs) >= 2 and not capability.supports_multiple_aggregates:
        missing.append("multiple_aggregates")
    unsupported = needed_aggs - set(capability.supported_aggregations)
    if unsupported:
        missing.append("unsupported_aggregation")
        missing.extend(f"aggregation:{fn}" for fn in sorted(unsupported))
    group_fields = list(contract.group_fields)
    if group_fields:
        if not capability.supports_group_by:
            missing.append("group_by")
            missing.extend(f"group_by:{item}" for item in group_fields)
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
    metric_vals = {str(span.value) for span in contract.metrics if span.value}
    projection_needed = [
        field
        for field in contract.output_fields
        if field not in metric_vals or contract.operation in {"list", "rank", "group_rank"}
    ]
    if projection_needed and not capability.supports_output_projection:
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
    if contract.wants_spatial and not capability.supports_spatial:
        missing.append("spatial")
    if (
        contract.wants_basement or "basement_floors" in pred_fields
    ) and not capability.supports_basement:
        missing.append("basement")
    if contract.wants_temporal and not capability.supports_temporal:
        missing.append("temporal")
    threshold_fields = pred_fields & _THRESHOLD_FIELDS
    if (
        threshold_fields
        and capability.route in {"legacy_simple_count", "building_threshold_count"}
        and not contract.wants_count
    ):
        missing.append("explicit_count")
    if capability.supported_fields:
        extra = (pred_fields | set(contract.output_fields)) - set(capability.supported_fields)
        extra -= {"usage", "structure", "special_land", "legal_dong", "name"}
        if extra:
            missing.append("unsupported_field")
    return list(dict.fromkeys(missing))


def missing_slots(capability: RouteCapability, contract: QueryContract) -> list[str]:
    return missing_requirements(capability, contract)


def contract_is_complete(contract: QueryContract) -> bool:
    return contract.is_sufficient()


def fully_supports(capability: RouteCapability, contract: QueryContract) -> bool:
    return len(missing_requirements(capability, contract)) == 0


def legacy_route_eligible(route: str, contract: QueryContract) -> bool:
    if not contract_is_complete(contract):
        return False
    return not missing_requirements(capability_for(route), contract)


def route_allowed(intent: str, contract: QueryContract) -> bool:
    return legacy_route_eligible(intent, contract)


def detect_route_candidates(
    question: str,
    contract: QueryContract | None = None,
    *,
    conn=None,
) -> list[str]:
    from llm2sql.intent_router import try_route
    from llm2sql.profile_qa import is_profile_question
    from llm2sql.route_dispatch import match_route

    match = match_route(question, conn=conn, contract=contract)
    candidates: list[str] = []
    if match.early is not None:
        candidates.append(match.early.intent)
    if is_profile_question(question):
        candidates.append("building_profile")
    deferred = match.deferred
    if deferred is None and match.early is None:
        deferred = try_route(question, conn=conn)
    if deferred is not None and deferred.intent not in candidates:
        candidates.append(deferred.intent)
    return candidates


def select_execution_path(
    question: str,
    *,
    conn=None,
    contract: QueryContract | None = None,
) -> str:
    """Contract → candidate routes → 전부 지원하는 첫 경로, 아니면 semantic_plan."""
    contract = contract or extract_contract(question)
    if not contract_is_complete(contract):
        return "semantic_plan"
    for intent in detect_route_candidates(question, contract, conn=conn):
        if legacy_route_eligible(intent, contract):
            return intent
    return "semantic_plan"
