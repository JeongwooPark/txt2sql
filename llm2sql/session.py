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
        # 순위/단일 건물 결과만 focus로 유지 (카탈로그·설명 제외)
        route = str(result.get("route") or "")
        keep_focus = bool(rows) and (
            route.startswith("building_rank_")
            or route in {"building_profile"}
            or (
                result.get("ok")
                and result.get("sql")
                and len(rows) >= 1
                and any(k in rows[0] for k in ("A0", "A14", "A12", "A4", "A24"))
            )
        )
        if keep_focus and route != "building_profile":
            self.focus_row = dict(rows[0])
            self.focus_index = 0
            self.table = (result.get("tables") or ["AL_D010_26_20250704"])[0]
        elif keep_focus and route == "building_profile":
            # 프로필은 집계라 focus 건물 없음
            self.focus_row = None
            self.focus_index = 0
        elif not keep_focus and route and route.startswith("clarify_"):
            # 모호 확인 중에는 기존 focus 유지
            pass
        else:
            if rows and any(k in rows[0] for k in ("A0", "A24", "A14", "A4")):
                self.focus_row = dict(rows[0])
                self.focus_index = 0
                self.table = (result.get("tables") or [None])[0]
            elif not rows:
                self.focus_row = None

        if place:
            self.place = place
        if usage:
            self.usage = usage

    def clear_focus(self) -> None:
        self.focus_row = None
        self.focus_index = 0
        self.last_rows = []
