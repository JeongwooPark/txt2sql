"""결과 행이 Contract·Plan이 기대하는 형태인지 검사한다.

count 계약이 후속·구간별에서 잘못 남는 경우가 많다. 그때는 실행된 Plan의
query_kind(list/group)를 따른다. 진짜 건수 질의의 다중 숫자 행은 계속 거절한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from txt2sql.semantic_plan.models import SemanticQueryPlan

# SQP query_kind → Contract query_kind. aggregate/distribution 은 여러 행 그룹이다.
_PLAN_KIND = {
    "aggregate": "group",
    "distribution": "group",
}
_COUNT_ALIASES = {"n", "cnt", "count", "건수", "total_n"}
_LIST_ALIASES = {
    "name",
    "a24",
    "legal_dong",
    "lot_address",
    "a4",
    "a5",
    "usage",
    "a9",
}


@dataclass
class ResultVerify:
    ok: bool
    reasons: list[str] = field(default_factory=list)


def diagnose_result_shape(
    plan: SemanticQueryPlan,
    rows: list[dict[str, Any]] | None,
) -> list[str]:
    """Plan 기준 shape. Q03은 경고·재계획 신호이지 SQL 문법 오류가 아니다."""
    rows = rows or []
    errors: list[str] = []
    if plan.query_kind == "count":
        if len(rows) != 1:
            errors.append("Q03")
        elif rows and not _numeric_values(rows[0]):
            errors.append("Q03")
    if plan.query_kind == "rank" and plan.limit and len(rows) > plan.limit:
        errors.append("Q03")
    if plan.query_kind == "list" and len(rows) > 5000:
        errors.append("Q03")
    if plan.query_kind in {"aggregate", "distribution"} and plan.aggregations and rows:
        aliases = {
            item.alias
            or (f"{item.function}_{item.field}" if item.field else item.function)
            for item in plan.aggregations
        }
        row0 = rows[0]
        if aliases and not any(alias in row0 for alias in aliases):
            if len(_numeric_values(row0)) < len(plan.aggregations):
                errors.append("Q03")
        for key in plan.group_by:
            if key not in row0:
                errors.append("Q03")
                break
    if rows and all(all(v is None for v in row.values()) for row in rows):
        errors.append("Q03")
    return errors


def _numeric_values(row: dict[str, Any]) -> list[Any]:
    return [v for v in row.values() if isinstance(v, (int, float)) and v is not None]


def _mapped_plan_kind(plan: SemanticQueryPlan | None) -> str | None:
    if plan is None:
        return None
    raw = getattr(plan, "query_kind", None)
    return _PLAN_KIND.get(raw, raw) if raw else None


def _effective_kind(contract: Any | None, plan: SemanticQueryPlan | None) -> str | None:
    """실행 Plan이 list/group이면 계약의 stale count보다 우선한다."""
    plan_kind = _mapped_plan_kind(plan)
    contract_kind = getattr(contract, "query_kind", None) if contract is not None else None
    if plan_kind and plan_kind != "count":
        return plan_kind
    return contract_kind or plan_kind


def _rows_are_grouped_counts(rows: list[dict[str, Any]]) -> bool:
    """구간·연도별처럼 라벨 + 건수 열이 있는 여러 행."""
    if len(rows) < 2:
        return False
    keys = [str(k) for k in rows[0].keys()]
    if len(keys) < 2:
        return False
    lower = {k.lower() for k in keys}
    has_count = bool(lower & _COUNT_ALIASES) or bool(_numeric_values(rows[0]))
    has_label = any(k.lower() not in _COUNT_ALIASES for k in keys)
    return has_count and has_label


def _rows_are_entity_list(rows: list[dict[str, Any]]) -> bool:
    if not rows:
        return False
    return bool({str(k).lower() for k in rows[0].keys()} & _LIST_ALIASES)


def _is_bin_or_group_contract(contract: Any | None) -> bool:
    if contract is None:
        return False
    return bool(getattr(contract, "fixed_bins", False) or getattr(contract, "group_fields", None))


def _contract_allows_list_rows(contract: Any | None) -> bool:
    """목록 SQL인데 계약만 count로 남은 경우(출력 필드·비건수 질의)."""
    if contract is None:
        return False
    return bool(
        getattr(contract, "operation", None) == "list"
        or getattr(contract, "output_fields", None)
        or not getattr(contract, "wants_count", True)
    )


def _contract_has_extra_agg(contract: Any | None) -> bool:
    if contract is None:
        return False
    fns = {
        getattr(item, "function", None)
        for item in (getattr(contract, "aggregation_requests", None) or [])
    }
    return bool(fns - {"count", None})


def verify_result(
    contract: Any | None,
    rows: list[dict[str, Any]] | None,
    *,
    plan: SemanticQueryPlan | None = None,
) -> ResultVerify:
    """실패는 SQP 재계획 신호. Router는 plan=None이라 계약 kind만 본다."""
    rows = rows or []
    kind = _effective_kind(contract, plan)
    if kind == "count":
        return _verify_count(contract, rows, plan)
    if kind == "ratio":
        return _verify_ratio(rows)
    if kind == "rank":
        limit = getattr(contract, "limit", None) if contract is not None else None
        if plan is not None and limit is None:
            limit = plan.limit
        if limit is not None and len(rows) > int(limit):
            return ResultVerify(False, ["rank_over_limit"])
        return ResultVerify(True)
    if kind == "list" and len(rows) > 5000:
        return ResultVerify(False, ["list_too_many"])
    return ResultVerify(True)


def _verify_count(
    contract: Any | None,
    rows: list[dict[str, Any]],
    plan: SemanticQueryPlan | None,
) -> ResultVerify:
    if len(rows) != 1:
        # Router(plan 없음)에서 구간별·목록 SQL이 count 계약으로 들어온 경우만 통과
        mapped = _mapped_plan_kind(plan)
        if _rows_are_grouped_counts(rows) and (
            _is_bin_or_group_contract(contract) or mapped == "group"
        ):
            return ResultVerify(True)
        if _rows_are_entity_list(rows) and _contract_allows_list_rows(contract):
            return ResultVerify(True)
        return ResultVerify(False, ["count_row_count"])
    nums = _numeric_values(rows[0]) if rows else []
    if not nums:
        return ResultVerify(False, ["count_not_numeric"])
    if len(nums) > 2:
        # 평균+중앙값+건수처럼 한 행 다중 지표. 순수 건수의 3열 오답은 거절.
        if _contract_has_extra_agg(contract) or _mapped_plan_kind(plan) in {"group", "scalar"}:
            return ResultVerify(True)
        return ResultVerify(False, ["count_multi_numeric"])
    return ResultVerify(True)


def _verify_ratio(rows: list[dict[str, Any]]) -> ResultVerify:
    if not rows:
        return ResultVerify(False, ["ratio_empty"])
    nums = [v for row in rows for v in _numeric_values(row)]
    if not nums:
        return ResultVerify(False, ["ratio_not_numeric"])
    if not any(0 <= float(v) <= 100 for v in nums) and all(float(v) > 100 for v in nums):
        return ResultVerify(False, ["ratio_out_of_range"])
    return ResultVerify(True)
