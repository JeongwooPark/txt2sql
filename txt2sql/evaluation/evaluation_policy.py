"""EvaluationPolicy — metric-specific comparators with semantic context guards.

Tolerance is NEVER applied globally. Before any tolerance comparison,
metric / unit / scope / grain must align between gold and prediction context.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Literal

ComparatorKind = Literal[
    "integer_exact",
    "scalar_float",
    "ratio",
    "distance_m",
    "area_m2",
    "geometry",
]

NUM_RE = re.compile(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+\.\d+|-?\d+")


@dataclass(frozen=True)
class SemanticEvalContext:
    """Semantic context required before tolerance may apply."""

    metric: str  # count | count_distinct | avg | sum | min | max | ratio | distance | area
    unit: str | None = None  # None | count | m2 | m | pct | coord
    scope: str | None = None  # canonical place if detectable
    grain: str | None = None  # building | admin_dong | legal_dong | sigungu | ...
    distinct: bool = False


@dataclass(frozen=True)
class ComparatorSpec:
    kind: ComparatorKind
    abs_tol: float = 0.0
    rel_tol: float = 0.0


# Metric-specific comparator defaults (not global).
COMPARATOR_DEFAULTS: dict[ComparatorKind, ComparatorSpec] = {
    "integer_exact": ComparatorSpec(kind="integer_exact"),
    "scalar_float": ComparatorSpec(kind="scalar_float", abs_tol=0.01, rel_tol=0.001),
    "ratio": ComparatorSpec(kind="ratio", abs_tol=0.01, rel_tol=0.005),
    "distance_m": ComparatorSpec(kind="distance_m", abs_tol=0.5, rel_tol=0.001),
    "area_m2": ComparatorSpec(kind="area_m2", abs_tol=0.1, rel_tol=0.001),
    "geometry": ComparatorSpec(kind="geometry", abs_tol=1e-6, rel_tol=1e-6),
}


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        m = re.search(r"[-+]?\d*\.?\d+", text)
        return float(m.group()) if m else None


def _is_integer_value(value: float) -> bool:
    return abs(value - round(value)) < 1e-6 and abs(value) < 1e15


def _as_int(value: float) -> int | None:
    if _is_integer_value(value):
        return int(round(value))
    return None


def parse_numbers(text: str) -> list[float]:
    out: list[float] = []
    for m in NUM_RE.findall(text or ""):
        v = _to_float(m)
        if v is not None:
            out.append(v)
    return out


def _detect_scope(text: str) -> str | None:
    for token in re.findall(r"[\w가-힣]+(?:구|군|동|시|도)", text or ""):
        if len(token) >= 2:
            return token
    return None


def _detect_unit(text: str, *, metric: str) -> str | None:
    t = text or ""
    if metric in {"count", "count_distinct"}:
        return "count"
    if "pct" in t.lower() or "%" in t or "비율" in t or "퍼센트" in t:
        return "pct"
    if "㎡" in t or "m2" in t.lower() or "연면적" in t or "면적" in t:
        return "m2"
    if re.search(r"\d+\s*m\b", t, re.I) or "거리" in t or "반경" in t:
        return "m"
    if "좌표" in t or "경위도" in t or "위도" in t or "경도" in t:
        return "coord"
    return None


def _metric_from_gold_text(gold: str) -> str | None:
    """Parse gold field keys (avg_h=, pct=, …) before question heuristics."""
    g = (gold or "").lower()
    if re.search(r"\bsum_", g):
        return "sum"
    if re.search(r"\bmedian_", g):
        return "median"
    if re.search(r"\bstd_", g):
        return "std"
    if re.search(r"\bavg_", g):
        return "avg"
    if re.search(r"_ratio\b", g):
        return "ratio"
    if re.search(r"\bpct\b", g) or g.strip().startswith("pct"):
        return "ratio"
    if re.search(r"\bcut=", g):
        return "avg"
    return None


def _unit_from_gold_text(gold: str, *, metric: str) -> str | None:
    g = (gold or "").lower()
    if metric == "ratio" or re.search(r"\bpct\b", g) or re.search(r"_ratio\b", g):
        return "pct" if "%" in gold or re.search(r"\bpct\b", g) else None
    if "avg_h" in g or "median_h" in g or "std_h" in g or "height" in g or "높이" in g:
        return "m"
    if "avg_gfa" in g or "sum_gfa" in g or "gfa" in g or "연면적" in g:
        return "m2"
    if metric in {"count", "count_distinct"}:
        return "count"
    return None


def _metric_from_answer_text(answer: str) -> str | None:
    a = (answer or "").lower()
    if re.search(r"sum_(?:gross_floor_area|gfa)", a):
        return "sum"
    if re.search(r"median_(?:height|h)", a):
        return "median"
    if re.search(r"std(?:dev)?_(?:height|h)", a):
        return "std"
    if re.search(r"avg_(?:height|gross_floor_area|building)", a):
        return "avg"
    if "ratio_pct" in a or re.search(r"\bpct\b", a):
        return "ratio"
    if re.search(r"\bavg_", a):
        return "avg"
    return None


def _unit_from_answer_text(answer: str, *, metric: str) -> str | None:
    a = (answer or "").lower()
    if metric == "ratio" or "ratio_pct" in a:
        return "pct"
    if any(tok in a for tok in ("avg_height", "median_height", "std_height", "height_m")):
        return "m"
    if any(tok in a for tok in ("sum_gross_floor_area", "avg_gross_floor_area", "gfa")):
        return "m2"
    return _detect_unit(answer, metric=metric)


def _metric_from_sql(sql: str | None, *, kind: str) -> str | None:
    upper = (sql or "").upper()
    if not upper:
        return None
    if "COUNT(DISTINCT" in upper:
        return "count_distinct"
    # Scalar answers often SELECT avg(...) and count(*) together — prefer aggregate intent.
    if kind == "scalar":
        for token, metric in (
            ("PERCENTILE", "median"),
            ("STDDEV", "std"),
            ("AVG(", "avg"),
            ("SUM(", "sum"),
            ("MIN(", "min"),
            ("MAX(", "max"),
        ):
            if token in upper:
                return metric
        if "RATIO" in upper or " AS \"RATIO_PCT\"" in upper:
            return "ratio"
    if kind == "count" or "COUNT(" in upper:
        return "count"
    if "AVG(" in upper:
        return "avg"
    return None


def infer_gold_context(*, kind: str, gold: str, question: str = "") -> SemanticEvalContext:
    """Infer semantic evaluation context from gold + question."""
    blob = f"{gold} {question}"
    metric = "unknown"
    distinct = False
    grain: str | None = None

    if kind == "count":
        metric = "count"
        grain = "building"
        if "행정동" in blob and "별" in blob:
            grain = "admin_dong"
            if "서로 다른" in blob or "distinct" in blob.lower():
                metric = "count_distinct"
                distinct = True
        elif "법정동" in blob:
            grain = "legal_dong"
    elif kind == "scalar":
        metric = _metric_from_gold_text(gold) or "scalar_float"
        if metric == "scalar_float":
            if re.search(r"\bpct\b", gold.lower()) or gold.strip().lower().startswith("pct"):
                metric = "ratio"
            elif "평균" in question or "avg" in gold.lower():
                metric = "avg"
            elif "거리" in question or re.search(r"\d+\s*m\b", question, re.I):
                metric = "distance"
            elif "㎡" in gold or "연면적" in gold or "면적" in question:
                metric = "area"
            elif "좌표" in question or "경위도" in question:
                metric = "geometry"
    elif kind == "group":
        metric = "count"
        grain = "group"
    else:
        metric = kind

    unit = _unit_from_gold_text(gold, metric=metric) or _detect_unit(gold, metric=metric)
    if unit is None and metric not in {"avg", "scalar_float"}:
        unit = _detect_unit(blob, metric=metric)
    scope = _detect_scope(question) or _detect_scope(gold)
    return SemanticEvalContext(
        metric=metric,
        unit=unit,
        scope=scope,
        grain=grain,
        distinct=distinct,
    )


def infer_pred_context(
    *,
    kind: str,
    answer: str,
    rows: list[dict[str, Any]] | None,
    sql: str | None = None,
    question: str = "",
) -> SemanticEvalContext | None:
    """Infer predicted semantic context from engine output."""
    scope = _detect_scope(answer) or _detect_scope(question)
    metric = _metric_from_answer_text(answer) or _metric_from_sql(sql, kind=kind)
    if metric is None:
        return infer_gold_context(kind=kind, gold="", question=question)

    distinct = metric == "count_distinct"
    unit = _unit_from_answer_text(answer, metric=metric)
    if unit is None:
        unit = _detect_unit(answer, metric=metric)
    if metric in {"count", "count_distinct"} and unit is None:
        unit = "count"

    grain: str | None = None
    if kind == "count":
        grain = infer_gold_context(kind=kind, gold="", question=question).grain

    return SemanticEvalContext(
        metric=metric,
        unit=unit,
        scope=scope,
        grain=grain,
        distinct=distinct,
    )


def contexts_align(gold: SemanticEvalContext, pred: SemanticEvalContext | None) -> bool:
    """All four semantic dimensions must match before tolerance applies."""
    if pred is None:
        return False
    if gold.metric != pred.metric:
        return False
    if gold.distinct != pred.distinct:
        return False
    if gold.unit is not None and pred.unit is not None and gold.unit != pred.unit:
        return False
    if gold.grain is not None and pred.grain is not None and gold.grain != pred.grain:
        return False
    if gold.scope is not None and pred.scope is not None and gold.scope != pred.scope:
        return False
    return True


def comparator_for_context(ctx: SemanticEvalContext) -> ComparatorSpec:
    """Map semantic context to comparator — never one global tolerance."""
    m = ctx.metric
    if m in {"count", "count_distinct"}:
        return COMPARATOR_DEFAULTS["integer_exact"]
    if m in {"min", "max"} and ctx.unit == "count":
        return COMPARATOR_DEFAULTS["integer_exact"]
    if m == "ratio":
        return COMPARATOR_DEFAULTS["ratio"]
    if m == "distance":
        return COMPARATOR_DEFAULTS["distance_m"]
    if m == "area":
        return COMPARATOR_DEFAULTS["area_m2"]
    if m == "geometry":
        return COMPARATOR_DEFAULTS["geometry"]
    if m == "avg":
        return COMPARATOR_DEFAULTS["scalar_float"]
    if m in {"sum", "min", "max", "median", "std", "scalar_float"}:
        return COMPARATOR_DEFAULTS["scalar_float"]
    return COMPARATOR_DEFAULTS["scalar_float"]


def compare_values(got: Any, expected: Any, spec: ComparatorSpec) -> bool:
    """Compare two values using metric-specific comparator."""
    g = _to_float(got)
    e = _to_float(expected)
    if g is None or e is None:
        return str(got).strip() == str(expected).strip()

    if spec.kind == "integer_exact":
        gi, ei = _as_int(g), _as_int(e)
        if gi is not None and ei is not None:
            return gi == ei
        return g == e

    if spec.kind in {"scalar_float", "ratio", "distance_m", "area_m2", "geometry"}:
        return math.isclose(g, e, rel_tol=spec.rel_tol, abs_tol=spec.abs_tol)

    return g == e


def compare_with_policy(
    got: Any,
    expected: Any,
    *,
    gold_ctx: SemanticEvalContext,
    pred_ctx: SemanticEvalContext | None,
) -> tuple[bool, str]:
    """Compare values only if semantic contexts align; otherwise exact fail."""
    if not contexts_align(gold_ctx, pred_ctx):
        return False, "semantic-context-mismatch"
    spec = comparator_for_context(gold_ctx)
    if compare_values(got, expected, spec):
        return True, f"policy-{spec.kind}"
    return False, f"policy-mismatch-{spec.kind}"


def match_numbers_in_haystack(
    hay: list[float],
    targets: list[float],
    *,
    gold_ctx: SemanticEvalContext,
    pred_ctx: SemanticEvalContext | None,
) -> tuple[bool, int, str]:
    """Match gold numbers in prediction haystack under evaluation policy."""
    if not targets:
        return False, 0, "no-targets"

    spec = comparator_for_context(gold_ctx)

    # integer_exact: no tolerance — safe to match without full context alignment
    if spec.kind == "integer_exact":
        hits = sum(1 for target in targets if any(compare_values(x, target, spec) for x in hay))
        ok = hits >= len(targets)
        reason = f"policy-{spec.kind} {hits}/{len(targets)}"
        if not ok:
            reason = f"policy-mismatch-{spec.kind} hits={hits} gold={targets[:4]}"
        return ok, hits, reason

    # tolerance comparators: require semantic context alignment first
    if not contexts_align(gold_ctx, pred_ctx):
        return False, 0, "semantic-context-mismatch"

    hits = 0
    for target in targets:
        if any(compare_values(x, target, spec) for x in hay):
            hits += 1

    need = max(1, min(2, len(targets) // 2 + 1))
    if len(targets) == 1:
        need = 1

    ok = hits >= need
    reason = f"policy-{spec.kind} {hits}/{len(targets)}"
    if not ok:
        reason = f"policy-mismatch-{spec.kind} hits={hits} gold={targets[:4]}"
    return ok, hits, reason
