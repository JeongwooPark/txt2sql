"""map_ui_gold500 runner / driver unit tests (no live server required)."""

from __future__ import annotations

from tests.map_ui_gold500.driver import parse_sse, sse_result
from tests.map_ui_gold500.run import _parse_args, resolve_driver, resolve_headed


def test_default_is_headless() -> None:
    args = _parse_args([])
    assert resolve_headed(args) is False


def test_headed_opt_in() -> None:
    args = _parse_args(["--headed"])
    assert resolve_headed(args) is True
    assert resolve_driver(args) == "browser"


def test_watch_enables_headed_browser() -> None:
    args = _parse_args(["--watch"])
    assert resolve_headed(args) is True
    assert resolve_driver(args) == "browser"


def test_headless_flag_keeps_headless() -> None:
    args = _parse_args(["--headless"])
    assert resolve_headed(args) is False


def test_headed_and_headless_prefers_headless() -> None:
    args = _parse_args(["--headed", "--headless"])
    assert resolve_headed(args) is False


def test_watch_and_headless_prefers_headless() -> None:
    args = _parse_args(["--watch", "--headless"])
    assert resolve_headed(args) is False


def test_driver_choices_default_auto() -> None:
    args = _parse_args([])
    assert args.driver == "auto"
    assert resolve_driver(args) == "auto"


def test_explicit_api_driver_kept_with_headed() -> None:
    args = _parse_args(["--headed", "--driver", "api"])
    assert resolve_headed(args) is True
    assert resolve_driver(args) == "api"


def test_parse_sse_and_result() -> None:
    body = (
        'data: {"type":"ready","session_id":"abc"}\n\n'
        'data: {"type":"token","text":"안"}\n\n'
        'data: {"type":"token","text":"녕"}\n\n'
        'data: {"type":"done","session_id":"abc","result":{"ok":true,"answer":"안녕","route":"x","rows":[]}}\n\n'
    )
    events = parse_sse(body)
    assert len(events) == 4
    parsed = sse_result(events)
    assert parsed["_session_id"] == "abc"
    assert parsed.get("ok") is True
    assert parsed.get("answer") == "안녕" or parsed.get("answer") == "안녕"


def test_sse_result_preserves_execution_trace() -> None:
    import json

    trace = {"execution_source": "semantic_v2", "trace_completeness": {"query_ir": True}}
    body = (
        'data: {"type":"done","session_id":"s1","result":'
        + json.dumps(
            {
                "ok": True,
                "answer": "2,537채",
                "route": "semantic_v2",
                "execution_trace": trace,
            },
            ensure_ascii=False,
        )
        + "}\n\n"
    )
    parsed = sse_result(parse_sse(body))
    assert parsed.get("execution_trace") == trace


def test_ask_result_roundtrip_execution_trace() -> None:
    from txt2sql.types import AskResult

    payload = {
        "ok": True,
        "answer": "test",
        "execution_trace": {"execution_source": "rag_sql"},
    }
    result = AskResult.from_dict(payload)
    dumped = result.to_dict()
    assert dumped.get("execution_trace") == {"execution_source": "rag_sql"}


def test_track_file_exclude_and_only() -> None:
    import json
    from pathlib import Path

    from tests.map_ui_gold500.run import _load_track_ids, _select

    track = {
        "tracks": {
            "data_quality": ["Q037", "Q038"],
            "operator_promote": ["Q040", "Q319"],
            "main": ["Q001", "Q040", "Q037"],
        }
    }
    path = Path("tests/map_ui_gold500/_tmp_tracks_test.json")
    path.write_text(json.dumps(track), encoding="utf-8")
    try:
        exclude = _load_track_ids(path, "data_quality")
        only = _load_track_ids(path, "operator_promote")
        assert exclude == {"Q037", "Q038"}
        assert only == {"Q040", "Q319"}
        questions = [{"id": i} for i in ("Q001", "Q037", "Q040", "Q319")]
        main = _select(questions, None, 0, exclude=exclude)
        assert [q["id"] for q in main] == ["Q001", "Q040", "Q319"]
        gated = _select(questions, only, 0)
        assert [q["id"] for q in gated] == ["Q040", "Q319"]
    finally:
        path.unlink(missing_ok=True)
