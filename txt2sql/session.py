"""대화 세션: 직전 질의 결과를 후속 질문에 사용."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResultAnchor:
    entity: str = "building"
    identity: str | None = None
    row: dict[str, Any] = field(default_factory=dict)
    rank: int | None = None
    label: str | None = None


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
    last_map_scope: str | None = None
    last_map_payload: dict[str, Any] | None = None
    last_semantic_plan: dict[str, Any] | None = None
    last_semantic_plan_route: str | None = None
    last_plan_base: dict[str, Any] | None = None
    last_plan_events: list[dict[str, Any]] = field(default_factory=list)
    last_contract: dict[str, Any] | None = None
    result_anchors: list[ResultAnchor] = field(default_factory=list)

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
        n_m = re.search(r"(\d+)\s*(개|곳|채)", question)
        if (
            re.search(rf"\d+\s*년\s*(단위|간격|별|씩)", question)
            or re.search(r"[가-힣]+\s*년\s*(단위|간격|별|씩)", question)
            or re.search(r"(연대별|년대별)", question)
            or re.search(
                r"\d+\s*(?:㎡|제곱미터|m2|평|km|킬로미터|층)?\s*(단위|간격|별|씩)",
                question,
            )
            or re.search(r"\d+\s*(?:단위로|으로)?\s*묶", question)
            or any(
                k in question
                for k in ("크기별", "구간별", "단위별", "크기 단위")
            )
        ) and self.last_full_question:
            pass
        elif n_m and self.last_full_question and len(question.strip()) < 16:
            # '5개는'처럼 건수만 바꿀 때, 예전 '3개'가 full에 남지 않게 치환
            replaced = re.sub(
                r"\d+\s*(개|곳|채)",
                n_m.group(0),
                self.last_full_question,
                count=1,
            )
            self.last_full_question = replaced
        elif len(question.strip()) >= 12 or any(
            k in question
            for k in ("동", "구", "주택", "건물", "아파트", "년", "채", "몇")
        ):
            self.last_full_question = question
        self.last_route = result.get("route")
        self.last_sql = result.get("sql")
        plan = result.get("semantic_plan")
        route = str(result.get("route") or "")
        if isinstance(plan, dict):
            self.last_semantic_plan = dict(plan)
            self.last_semantic_plan_route = route or self.last_semantic_plan_route
            self._coerce_count_display_plan(
                self.last_semantic_plan,
                str(result.get("sql") or ""),
                str(result.get("answer") or ""),
            )
            followup_like = any(k in question for k in ("그중", "그 중", "이 중", "그중에"))
            if not followup_like:
                self.last_plan_base = dict(self.last_semantic_plan)
                self.last_plan_events = []
        elif route and not route.startswith(("clarify_", "semantic_plan_")):
            heur_plan = None
            if result.get("ok") and (
                (result.get("sql") or "").find("AL_D010") >= 0
                or (result.get("sql") or "").find("AL_D198") >= 0
            ):
                try:
                    from txt2sql.semantic_plan.generator import try_heuristic_plan

                    heur = try_heuristic_plan(question)
                    if heur is not None:
                        usable = (not heur.requires_clarification) or bool(
                            heur.filters or heur.scope or heur.predicate
                        )
                        if usable:
                            heur_plan = heur.model_dump()
                            heur_plan["requires_clarification"] = False
                            heur_plan["ambiguities"] = []
                except Exception:
                    heur_plan = None
            if heur_plan is not None:
                self._coerce_count_display_plan(
                    heur_plan,
                    str(result.get("sql") or ""),
                    str(result.get("answer") or ""),
                )
                self.last_semantic_plan = heur_plan
                self.last_semantic_plan_route = (
                    "semantic_plan_" + str(heur_plan.get("query_kind") or "count")
                )
                if not any(k in question for k in ("그중", "그 중", "이 중", "그중에")):
                    self.last_plan_base = dict(heur_plan)
                    self.last_plan_events = []
            else:
                self.last_semantic_plan = None
                self.last_semantic_plan_route = None
        self.last_answer = result.get("answer")
        rows = list(result.get("rows") or [])
        # 차트/확인 후속은 rows가 비어 있어도 직전 집계를 유지해 지표 재선택에 쓴다
        keep_prev_rows = str(route or "").startswith(("chart_", "clarify_", "guide_"))
        if rows or not keep_prev_rows:
            self.last_rows = rows
            self.result_anchors = [
                ResultAnchor(
                    entity="building",
                    identity=str(row.get("A0") or row.get("id") or "") or None,
                    row=dict(row),
                    rank=i + 1,
                    label=str(row.get("A24") or row.get("name") or "") or None,
                )
                for i, row in enumerate(rows[:20])
            ]
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
        from txt2sql.followup_qa import _normalize_building_row

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
                sql = str(result.get("sql") or "")
                tables = result.get("tables") or []
                if "AL_D198" in sql:
                    d198 = next(
                        (t for t in tables if str(t).startswith("AL_D198")),
                        None,
                    )
                    if d198:
                        self.table = str(d198)
                    else:
                        m = re.search(r'"(AL_D198_[^"]+)"', sql)
                        if m:
                            self.table = m.group(1)

        from txt2sql.domain import extract_gu, extract_place, extract_usage

        if place:
            self.place = place
        else:
            guessed = extract_place(question) or extract_gu(question)
            if guessed:
                self.place = guessed
        if usage:
            self.usage = usage
        else:
            guessed_u = extract_usage(question)
            if guessed_u:
                self.usage = guessed_u

    @staticmethod
    def _coerce_count_display_plan(
        plan: dict[str, Any], sql: str, answer: str
    ) -> None:
        """목록 SQL이 COUNT(*) OVER 또는 'N동입니다'면 후속용 count로 본다."""
        if not isinstance(plan, dict):
            return
        over = bool(re.search(r"COUNT\s*\(\s*\*\s*\)\s+OVER", sql or "", re.I))
        spoken = bool(
            re.search(r"(모두\s*)?\d[\d,]*\s*(동|채|건)입니다", answer or "")
        )
        if not (over or spoken):
            return
        plan["query_kind"] = "count"
        plan["select"] = []
        plan["limit"] = None
        plan["order_by"] = []

    def clear_focus(self) -> None:
        self.focus_row = None
        self.focus_index = 0
        self.last_rows = []
