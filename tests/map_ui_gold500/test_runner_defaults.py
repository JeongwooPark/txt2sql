"""map_ui_gold500 runner / driver unit tests (no live server required)."""

from __future__ import annotations

from tests.map_ui_gold500.driver import parse_sse, sse_result
from tests.map_ui_gold500.run import _parse_args, resolve_headed


def test_default_is_headless() -> None:
    args = _parse_args([])
    assert resolve_headed(args) is False


def test_headed_opt_in() -> None:
    args = _parse_args(["--headed"])
    assert resolve_headed(args) is True


def test_headless_flag_keeps_headless() -> None:
    args = _parse_args(["--headless"])
    assert resolve_headed(args) is False


def test_headed_and_headless_prefers_headless() -> None:
    args = _parse_args(["--headed", "--headless"])
    assert resolve_headed(args) is False


def test_driver_choices_default_auto() -> None:
    args = _parse_args([])
    assert args.driver == "auto"


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
