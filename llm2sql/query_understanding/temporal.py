"""사용승인·허가·경과년수 표현을 approval_date 필터로 정규화한다."""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from llm2sql.semantic_plan.models import FilterSpec

_DECADE = re.compile(r"((?:19|20)\d)0\s*년대")
_DECADE_SPAN = re.compile(
    r"((?:19|20)\d)0s\s*[~～\-]\s*((?:19|20)\d)0s"
)
_YEAR_REL = re.compile(
    r"((?:19|20)\d{2})\s*년\s*(이후|이전|이래|까지|부터)?"
)
_YEAR_SPAN = re.compile(
    r"((?:19|20)\d{2})\s*(?:년\s*)?[~～\-]\s*((?:19|20)\d{2})"
)
_YEAR_BETWEEN = re.compile(
    r"((?:19|20)\d{2})\s*년\s*(?:이상|이후|부터|이래)\s*"
    r"((?:19|20)\d{2})\s*년\s*(?:이하|까지|이전)?"
)
_AGE = re.compile(
    r"(?:지어진\s*지|건축\s*(?:후|된\s*지)?|사용승인\s*(?:후|된\s*지)?|"
    r"경과|된\s*지)?\s*(\d+)\s*년\s*"
    r"(?:이\s*)?(넘|이상|이하|미만|초과|이내|된|지남|경과|전|이상된)?"
)


def parse_reference_date(raw: str | None) -> date:
    text = (raw or "2025-07-04").strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return date(2025, 7, 4)


def parse_temporal_filters(
    question: str,
    *,
    reference_date: str | date | None = None,
) -> list[FilterSpec]:
    """질문의 연대·연도·경과년수를 approval_date 필터로 바꾼다.

    모호한 '오래된'만 있고 숫자가 없으면 빈 리스트를 반환한다.
    """
    q = question or ""
    if "차이" in q and "허가" in q and "사용승인" in q:
        return []
    ref = (
        reference_date
        if isinstance(reference_date, date)
        else parse_reference_date(str(reference_date) if reference_date else None)
    )
    found: list[FilterSpec] = []

    span = _YEAR_SPAN.search(q)
    if span:
        lo, hi = int(span.group(1)), int(span.group(2))
        if lo > hi:
            lo, hi = hi, lo
        found.append(
            FilterSpec(field="approval_date", operator="between", value=lo, value2=hi)
        )
        return found

    year_between = _YEAR_BETWEEN.search(q)
    if year_between:
        lo, hi = int(year_between.group(1)), int(year_between.group(2))
        if lo > hi:
            lo, hi = hi, lo
        found.append(
            FilterSpec(field="approval_date", operator="between", value=lo, value2=hi)
        )
        return found

    decade_span = _DECADE_SPAN.search(q)
    if decade_span:
        lo = int(decade_span.group(1) + "0")
        hi = int(decade_span.group(2) + "0") + 9
        if lo > hi:
            lo, hi = hi, lo
        found.append(
            FilterSpec(field="approval_date", operator="between", value=lo, value2=hi)
        )
        return found

    decade = _DECADE.search(q)
    if decade:
        start = int(decade.group(1) + "0")
        found.append(
            FilterSpec(
                field=_temporal_date_field(q),
                operator="between",
                value=start,
                value2=start + 9,
            )
        )
        return found

    year_rel = _YEAR_REL.search(q)
    if year_rel and "년대" not in q[max(0, year_rel.start() - 1) : year_rel.end() + 2]:
        year = int(year_rel.group(1))
        rel = year_rel.group(2)
        if rel in {"이후", "이래", "부터"}:
            found.append(FilterSpec(field=_temporal_date_field(q), operator="gte", value=year))
        elif rel in {"이전", "까지"}:
            found.append(FilterSpec(field=_temporal_date_field(q), operator="lt", value=year))
        else:
            found.append(
                FilterSpec(
                    field=_temporal_date_field(q), operator="between", value=year, value2=year
                )
            )
        return found

    age = _AGE.search(q)
    if age and not _YEAR_REL.search(age.group(0)):
        years = int(age.group(1))
        if 1 <= years <= 200:
            cutoff_year = ref.year - years
            rel = age.group(2) or "이상"
            if rel in {"미만", "이내"}:
                found.append(
                    FilterSpec(
                        field="approval_date",
                        operator="gt",
                        value=cutoff_year,
                    )
                )
            elif rel in {"이하"}:
                found.append(
                    FilterSpec(
                        field="approval_date",
                        operator="gte",
                        value=cutoff_year,
                    )
                )
            else:
                found.append(
                    FilterSpec(
                        field="approval_date",
                        operator="lte",
                        value=cutoff_year,
                    )
                )
    return found


def _shift_years(day: date, delta_years: int) -> date:
    try:
        return day.replace(year=day.year + delta_years)
    except ValueError:
        return day + timedelta(days=365 * delta_years)


def _temporal_date_field(question: str) -> str:
    if "허가" in question and "사용승인" not in question:
        return "permit_date"
    return "approval_date"


def temporal_meta(question: str) -> dict[str, Any]:
    filters = parse_temporal_filters(question)
    return {
        "n": len(filters),
        "fields": [item.field for item in filters],
        "operators": [item.operator for item in filters],
    }
