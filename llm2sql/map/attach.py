"""채팅 결과에 지도 레이어 정보를 붙인다."""

from __future__ import annotations

from typing import Any, Protocol

from llm2sql.config import Settings
from llm2sql.map.publish import layer_is_published, publish_query_layer
from llm2sql.map.sql import map_scope_key, plan_map_sql
from llm2sql.session import SessionContext


class _Progress(Protocol):
    steps: list[Any]

    def emit(self, stage: str, message: str, **extra: Any) -> None: ...


def attach_map(
    result: dict[str, Any],
    settings: Settings,
    question: str,
    session_id: str | None,
    progress: _Progress | None = None,
    session: SessionContext | None = None,
) -> dict[str, Any]:
    """SQL 성공 후 지도를 발행한다. 실패해도 채팅 답변은 유지한다."""
    if not result.get("ok"):
        return result
    try:
        mapped = _map_for_result(
            result,
            settings,
            question=question,
            session_id=session_id,
            session=session,
        )
        if mapped:
            result = dict(result)
            result["map"] = mapped
            if session is not None and mapped.get("available") and mapped.get("layer"):
                plan = plan_map_sql(
                    question=question,
                    sql=result.get("sql"),
                    route=result.get("route"),
                    ok=True,
                    map_limit=settings.map_max_features,
                )
                if plan is not None:
                    session.last_map_scope = map_scope_key(plan.sql)
                    session.last_map_payload = {
                        k: v
                        for k, v in mapped.items()
                        if k != "reused"
                    }
            if progress is not None:
                if mapped.get("reused"):
                    progress.emit("map", "같은 대상이라 기존 분석 레이어를 유지합니다.")
                elif mapped.get("available"):
                    progress.emit(
                        "map",
                        f"지도 레이어 {mapped.get('layer')} ({mapped.get('feature_count', 0)}건)",
                    )
                else:
                    progress.emit("map", mapped.get("error") or "지도 발행 실패")
    except Exception as exc:
        result = dict(result)
        result["map"] = {
            "available": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        if progress is not None:
            progress.emit("map", "지도 발행 중 오류 (채팅은 유지)")
    if progress is not None:
        result = dict(result)
        result["steps"] = progress.steps
    return result


def _map_for_result(
    result: dict[str, Any],
    settings: Settings,
    *,
    question: str,
    session_id: str | None,
    session: SessionContext | None,
) -> dict[str, Any] | None:
    reused = _reuse_map(settings, result, question, session)
    if reused is not None:
        return reused
    return publish_query_layer(
        settings,
        question=question,
        sql=result.get("sql"),
        route=result.get("route"),
        ok=bool(result.get("ok")),
        session_id=session_id,
    )


def _reuse_map(
    settings: Settings,
    result: dict[str, Any],
    question: str,
    session: SessionContext | None,
) -> dict[str, Any] | None:
    if session is None or not session.last_map_payload or not session.last_map_scope:
        return None
    plan = plan_map_sql(
        question=question,
        sql=result.get("sql"),
        route=result.get("route"),
        ok=bool(result.get("ok")),
        map_limit=settings.map_max_features,
    )
    if plan is None:
        return None
    if map_scope_key(plan.sql) != session.last_map_scope:
        return None
    prev = dict(session.last_map_payload)
    layer = str(prev.get("layer") or "")
    if not layer or not prev.get("available"):
        return None
    if settings.geoserver_url and not layer_is_published(settings, layer):
        return None
    prev["reused"] = True
    return prev
