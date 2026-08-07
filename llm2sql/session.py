"""대화 세션: 직전 질의 결과를 후속 질문에 사용."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionContext:
    last_question: str | None = None
    last_full_question: str | None = None
    last_route: str | None = None
    last_sql: str | None = None
    last_answer: str | None = None
    last_rows: list[dict[str, Any]] = field(default_factory=list)
    focus_row: dict[str, Any] | None = None
    focus_index: int = 0
    place: str | None = None
    usage: str | None = None
    table: str | None = None
    pending_chart: dict[str, Any] | None = None
    last_chart: dict[str, Any] | None = None

    def update_from_result(
        self,
        question: str,
        result: dict[str, Any],
        *,
        place: str | None = None,
        usage: str | None = None,
    ) -> None:
        self.last_question = question
        # 장소·연수 등이 있는 실질 질의는 full로 유지 (짧은 기준 보정용)
        if len(question.strip()) >= 12 or any(
            k in question
            for k in ("동", "구", "주택", "건물", "아파트", "년", "채", "몇")
        ):
            self.last_full_question = question
        self.last_route = result.get("route")
        self.last_sql = result.get("sql")
        self.last_answer = result.get("answer")
        rows = list(result.get("rows") or [])
        self.last_rows = rows
        route = str(result.get("route") or "")
        chart_payload = result.get("chart") or result.get("chart_spec")
        if result.get("chart_offer") and result.get("chart_spec"):
            self.pending_chart = dict(result["chart_spec"])
            self.last_chart = dict(result["chart_spec"])
        elif route == "chart_render" and chart_payload:
            # 표시 후에도 종류 변경(막대/도넛 등)이 가능하도록 유지
            self.pending_chart = None
            self.last_chart = dict(chart_payload)
        elif route == "chart_help":
            # 가능 종류 안내 후에도 직전 차트 맥락 유지
            pass
        elif route == "chart_decline":
            self.pending_chart = None
            self.last_chart = None
        elif route and not route.startswith("clarify_"):
            if not result.get("chart_offer"):
                self.pending_chart = None
                # 차트 후속이 아닌 새 질의면 last_chart도 해제
                if route not in {"chart_render", "chart_help"}:
                    self.last_chart = None
        # 순위/단일 건물 결과만 focus로 유지 (카탈로그·설명 제외)
        from llm2sql.followup_qa import _normalize_building_row

        norm_rows = [_normalize_building_row(r) for r in rows] if rows else []
        keep_focus = bool(norm_rows) and (
            route.startswith("building_rank_")
            or route in {"building_name_lookup"}
            or (
                result.get("ok")
                and result.get("sql")
                and len(norm_rows) == 1
                and any(
                    k in norm_rows[0] and norm_rows[0].get(k) is not None
                    for k in ("A0", "A1", "A14", "A12", "A4", "A24", "A5")
                )
                and "AL_D010" in str(result.get("sql") or "")
            )
        )
        if keep_focus and route != "building_profile":
            self.focus_row = dict(norm_rows[0])
            self.focus_index = 0
            tables = result.get("tables") or []
            d010 = next(
                (t for t in tables if str(t).startswith("AL_D010")),
                "AL_D010_26_20250704",
            )
            self.table = d010
        elif keep_focus and route == "building_profile":
            # 프로필은 집계라 focus 건물 없음
            self.focus_row = None
            self.focus_index = 0
        elif not keep_focus and route and route.startswith("clarify_"):
            # 모호 확인 중에는 기존 focus 유지
            pass
        elif not keep_focus and route and route.startswith(("meta_", "guide_", "chart_")):
            # 메타/안내/차트는 focus 유지 (지번? 같은 후속 대비)
            pass
        else:
            if norm_rows and len(norm_rows) == 1 and any(
                k in norm_rows[0] for k in ("A0", "A24", "A14", "A4", "A5")
            ):
                self.focus_row = dict(norm_rows[0])
                self.focus_index = 0
                self.table = (result.get("tables") or ["AL_D010_26_20250704"])[0]
            elif not rows:
                self.focus_row = None
            elif route and not route.startswith(("followup_", "clarify_")):
                # 다건·비건물 결과면 focus 해제
                if len(norm_rows) != 1:
                    self.focus_row = None

        if place:
            self.place = place
        if usage:
            self.usage = usage

    def clear_focus(self) -> None:
        self.focus_row = None
        self.focus_index = 0
        self.last_rows = []
