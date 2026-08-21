"""공개 결과 타입."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any


@dataclass
class AskResult:
    """엔진 질의 결과 (dict 호환)."""

    ok: bool
    answer: str
    sql: str | None = None
    tables: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    route: str | None = None
    error: str | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    ambiguous_terms: list[str] | None = None
    diagnostics: str | None = None
    chart_offer: bool = False
    chart_spec: dict[str, Any] | None = None
    chart: dict[str, Any] | None = None
    table: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("ambiguous_terms", "diagnostics", "chart_spec", "chart", "table"):
            if data.get(key) is None:
                data.pop(key, None)
        if not data.get("chart_offer"):
            data.pop("chart_offer", None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AskResult:
        known = {f.name for f in fields(cls)}
        kwargs = {k: data[k] for k in known if k in data}
        kwargs.setdefault("ok", True)
        kwargs.setdefault("answer", "")
        return cls(**kwargs)
