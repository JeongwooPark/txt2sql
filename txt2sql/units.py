"""질문의 면적·길이 단위를 스키마 단위(㎡, m)로 바꾼다."""

from __future__ import annotations

import re
from dataclasses import dataclass

# 법정 1평 = 400/121 ㎡ ≈ 3.3058㎡
PYEONG_TO_M2 = 400.0 / 121.0

NUM_TOKEN = r"(\d+(?:\.\d+)?)"
# 긴 표기 우선. 평수·평형·평방은 면적 단위 '평'이 아님.
UNIT_TOKEN = (
    r"(제곱킬로미터|제곱미터|평방미터|킬로미터|센티미터|밀리미터|"
    r"헥타르|㎢|km²|km2|㎡|m²|m2|㎞|km|cm|mm|ha|"
    r"평(?!수|형|방)|미터|m|층|%|퍼센트)?"
)

_UNIT_NORM: dict[str, str] = {
    "제곱킬로미터": "km2",
    "㎢": "km2",
    "km²": "km2",
    "km2": "km2",
    "제곱미터": "m2",
    "평방미터": "m2",
    "㎡": "m2",
    "m²": "m2",
    "m2": "m2",
    "헥타르": "ha",
    "ha": "ha",
    "평": "pyeong",
    "킬로미터": "km",
    "㎞": "km",
    "km": "km",
    "센티미터": "cm",
    "cm": "cm",
    "밀리미터": "mm",
    "mm": "mm",
    "미터": "m",
    "m": "m",
    "층": "floor",
    "%": "percent",
    "퍼센트": "percent",
}

_KIND_FACTOR: dict[str, tuple[str, float]] = {
    "km2": ("area", 1_000_000.0),
    "m2": ("area", 1.0),
    "ha": ("area", 10_000.0),
    "pyeong": ("area", PYEONG_TO_M2),
    "km": ("length", 1000.0),
    "m": ("length", 1.0),
    "cm": ("length", 0.01),
    "mm": ("length", 0.001),
    "floor": ("floor", 1.0),
    "percent": ("percent", 1.0),
}

_SCHEMA_KIND: dict[str, str] = {
    "㎡": "area",
    "m2": "area",
    "m²": "area",
    "m": "length",
    "미터": "length",
    "층": "floor",
    "%": "percent",
}

_DISPLAY_UNIT: dict[str, str] = {
    "km2": "㎢",
    "m2": "㎡",
    "ha": "ha",
    "pyeong": "평",
    "km": "km",
    "m": "m",
    "cm": "cm",
    "mm": "mm",
    "floor": "층",
    "percent": "%",
}

_PYEONG_THRESHOLD = re.compile(
    rf"{NUM_TOKEN}\s*평(?!수|형|방)\s*(이상|이하|초과|미만|넘는)"
)
_BIN_QTY = re.compile(
    rf"{NUM_TOKEN}\s*{UNIT_TOKEN}\s*(?:단위로|단위|간격|별|씩|으로)?\s*묶?"
)


@dataclass(frozen=True)
class ConvertedAmount:
    sql: str
    canonical: float
    label: str
    source_unit: str | None
    original: float


def sql_number(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text or "0"


def display_unit(unit_key: str | None) -> str:
    if not unit_key:
        return ""
    return _DISPLAY_UNIT.get(unit_key, unit_key)


def mentions_pyeong(text: str) -> bool:
    """면적 단위 '평'이 질문에 있는지. 평수·평형·평방은 제외."""
    return bool(re.search(r"평(?!수|형|방)", text or ""))


def format_pyeong_from_m2(m2: float) -> str:
    """㎡ → '373평' 또는 '373.2평'."""
    py = float(m2) / PYEONG_TO_M2
    if abs(py - round(py)) < 0.05:
        return f"{int(round(py))}평"
    return f"{sql_number(round(py, 1))}평"


def with_pyeong(m2_label: str, m2_value: object, *, question: str) -> str:
    """질문에 평이 있으면 이미 만든 ㎡ 표기에 평 환산을 붙인다."""
    if not mentions_pyeong(question):
        return m2_label
    try:
        val = float(m2_value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return m2_label
    return f"{m2_label} ({format_pyeong_from_m2(val)})"


def _norm_unit(raw: str | None) -> str | None:
    token = (raw or "").strip()
    if not token:
        return None
    return _UNIT_NORM.get(token, token)


def schema_kind(schema_unit: str) -> str:
    return _SCHEMA_KIND.get(schema_unit.strip(), "other")


def convert_for_schema(
    number: str | float,
    unit: str | None,
    schema_unit: str,
) -> ConvertedAmount | None:
    """질문 수치를 컬럼 단위로 환산. 단위가 맞지 않으면 None."""
    try:
        original = float(number)
    except (TypeError, ValueError):
        return None
    kind = schema_kind(schema_unit)
    if kind == "other":
        return None
    key = _norm_unit(unit)
    if key is None:
        return ConvertedAmount(
            sql=sql_number(original),
            canonical=original,
            label=f"{sql_number(original)}{schema_unit}",
            source_unit=None,
            original=original,
        )
    mapped = _KIND_FACTOR.get(key)
    if mapped is None:
        return None
    src_kind, factor = mapped
    if src_kind != kind:
        return None
    canonical = original * factor
    shown = sql_number(canonical)
    label = f"{shown}{schema_unit}"
    if key not in {"m2", "m"} and factor != 1.0:
        label = f"{shown}{schema_unit} ({sql_number(original)}{_DISPLAY_UNIT.get(key, key)})"
    elif key == "pyeong":
        label = f"{shown}{schema_unit} ({sql_number(original)}평)"
    return ConvertedAmount(
        sql=shown,
        canonical=canonical,
        label=label,
        source_unit=key,
        original=original,
    )


def pyeong_threshold(question: str) -> tuple[ConvertedAmount, str] | None:
    """'30평 이상'처럼 지표명 없이 평만 있는 임계. 연면적으로 본다."""
    match = _PYEONG_THRESHOLD.search(question)
    if not match:
        return None
    converted = convert_for_schema(match.group(1), "평", "㎡")
    if converted is None:
        return None
    return converted, match.group(2)


def find_bin_width(question: str, schema_unit: str) -> ConvertedAmount | None:
    """구간 폭(100㎡, 30평, 5m, 1km). 연·층만 있는 표현은 건너뛴다."""
    kind = schema_kind(schema_unit)
    for match in _BIN_QTY.finditer(question):
        unit = match.group(2) or ""
        if not unit:
            continue
        if unit in {"층", "%", "퍼센트"} and kind != "floor":
            continue
        converted = convert_for_schema(match.group(1), unit, schema_unit)
        if converted is not None:
            return converted
    return None


def has_convertible_area_unit(question: str) -> bool:
    return bool(
        re.search(r"㎡|제곱미터|평방미터|m2|m²|㎢|km²|km2|헥타르|(?<![가-힣])ha\b|평(?!수|형|방)", question)
    )
