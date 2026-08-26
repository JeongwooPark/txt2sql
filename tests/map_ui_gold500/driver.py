"""맵 UI 대화창에 질문을 입력하고 답·과정을 수집한다."""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright


def parse_sse(body: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for part in (body or "").split("\n\n"):
        line = next(
            (ln for ln in part.split("\n") if ln.startswith("data: ")),
            "",
        )
        if not line:
            continue
        try:
            events.append(json.loads(line[6:]))
        except json.JSONDecodeError:
            continue
    return events


def sse_result(events: list[dict[str, Any]]) -> dict[str, Any]:
    process: list[dict[str, Any]] = []
    result: dict[str, Any] = {}
    error: str | None = None
    session_id: str | None = None
    streamed: list[str] = []
    for evt in events:
        et = evt.get("type")
        if et == "ready":
            session_id = evt.get("session_id") or session_id
            process.append({"type": "ready", "session_id": session_id})
        elif et == "progress":
            process.append(
                {
                    "type": "progress",
                    "stage": evt.get("stage"),
                    "message": evt.get("message"),
                }
            )
        elif et == "token":
            streamed.append(str(evt.get("text") or ""))
        elif et == "done":
            session_id = evt.get("session_id") or session_id
            result = dict(evt.get("result") or {})
            process.append(
                {
                    "type": "done",
                    "session_id": session_id,
                    "ok": result.get("ok"),
                    "route": result.get("route"),
                }
            )
        elif et == "error":
            error = str(evt.get("message") or "sse-error")
            process.append({"type": "error", "message": error})
    if streamed and "answer" not in result:
        result["answer"] = "".join(streamed)
    result["_session_id"] = session_id
    result["_error"] = error
    result["_process"] = process
    return result


def health_ok(base_url: str, timeout_s: float = 3.0) -> bool:
    url = base_url.rstrip("/") + "/api/health"
    try:
        with urlopen(url, timeout=timeout_s) as res:
            return 200 <= res.status < 300
    except (URLError, OSError, TimeoutError):
        return False


def wait_health(base_url: str, timeout_s: float = 60.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if health_ok(base_url):
            return
        time.sleep(0.5)
    raise RuntimeError(f"맵 UI 서버가 응답하지 않습니다: {base_url}/api/health")


class MapUiDriver:
    def __init__(
        self,
        page: Page,
        *,
        map_url: str,
        timeout_ms: int,
    ) -> None:
        self.page = page
        self.map_url = map_url
        self.timeout_ms = timeout_ms
        self._current_session: str | None = None

    def open(self) -> None:
        self.page.goto(self.map_url, wait_until="domcontentloaded", timeout=60_000)
        self.page.wait_for_selector("#question", timeout=30_000)
        self.page.wait_for_selector("#send", timeout=30_000)
        try:
            self.page.wait_for_selector("#map", timeout=15_000)
        except PlaywrightTimeout:
            pass

    def start_new_chat(self) -> None:
        btn = self.page.locator("#new-chat")
        if btn.count() == 0:
            return
        btn.click()
        try:
            self.page.wait_for_selector("#messages .welcome", timeout=15_000)
        except PlaywrightTimeout:
            pass
        self.page.wait_for_selector("#question:not([disabled])", timeout=15_000)
        self._current_session = None

    def _wait_idle(self) -> None:
        self.page.wait_for_function(
            "() => { const s = document.querySelector('#send'); return s && !s.disabled; }",
            timeout=self.timeout_ms,
        )

    def snapshot_ui(self) -> dict[str, Any]:
        return self.page.evaluate(
            """() => {
              const lastBot = [...document.querySelectorAll('.row.bot')].at(-1);
              const lastUser = [...document.querySelectorAll('.row.user')].at(-1);
              const layers = [...document.querySelectorAll(
                '#analysis-layers-list .layer-item, #analysis-layers-list li, #analysis-layers-list button'
              )].map((el) => (el.innerText || '').trim()).filter(Boolean);
              return {
                user: lastUser?.innerText || '',
                answer: lastBot?.querySelector('.answer')?.innerText || '',
                meta: lastBot?.querySelector('.meta')?.innerText || '',
                sql: lastBot?.querySelector('.sql-block')?.innerText || '',
                status: lastBot?.querySelector('.status-text')?.innerText || '',
                error: Boolean(lastBot?.querySelector('.bubble.error')),
                analysis_layers: layers.slice(0, 12),
              };
            }"""
        )

    def ask(self, question: str, *, new_session: bool) -> dict[str, Any]:
        if new_session:
            self.start_new_chat()
        self._wait_idle()
        box = self.page.locator("#question")
        box.fill(question)
        t0 = time.perf_counter()
        timed_out = False
        error: str | None = None
        events: list[dict[str, Any]] = []
        try:
            with self.page.expect_response(
                lambda r: "/api/chat" in r.url and r.request.method == "POST",
                timeout=self.timeout_ms,
            ) as pending:
                self.page.locator("#send").click()
            response = pending.value
            body = response.text()
            events = parse_sse(body)
            self._wait_idle()
        except PlaywrightTimeout as exc:
            timed_out = True
            error = f"timeout>{self.timeout_ms // 1000}s"
            try:
                self.page.reload(wait_until="domcontentloaded", timeout=30_000)
                self.page.wait_for_selector("#question", timeout=15_000)
                self._current_session = None
            except Exception:
                pass
            events = [{"type": "error", "message": f"{error}: {exc}"}]
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"[:300]
            events = [{"type": "error", "message": error}]
        ms = int((time.perf_counter() - t0) * 1000)
        parsed = sse_result(events)
        ui = {}
        try:
            ui = self.snapshot_ui()
        except Exception as exc:
            ui = {"error": f"snapshot:{type(exc).__name__}: {exc}"}
        answer = str(parsed.get("answer") or ui.get("answer") or "")
        sql = parsed.get("sql") or ui.get("sql") or ""
        rows = parsed.get("rows") if isinstance(parsed.get("rows"), list) else []
        route = parsed.get("route")
        if parsed.get("_error") and not error:
            error = parsed["_error"]
        if parsed.get("ok") is False and not error:
            error = str(parsed.get("error") or "engine-not-ok")
        return {
            "ms": ms,
            "timed_out": timed_out,
            "error": error,
            "answer": answer,
            "sql": sql,
            "rows": rows,
            "route": route,
            "ui": ui,
            "process": parsed.get("_process") or events,
            "sse_ok": parsed.get("ok"),
            "row_count": parsed.get("row_count"),
        }


def launch_browser(*, headed: bool, slow_mo_ms: int = 0):
    pw = sync_playwright().start()
    launch_kwargs: dict[str, Any] = {
        "headless": not headed,
        "args": ["--disable-dev-shm-usage"],
    }
    if slow_mo_ms:
        launch_kwargs["slow_mo"] = slow_mo_ms
    browser = pw.chromium.launch(**launch_kwargs)
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        locale="ko-KR",
    )
    page = context.new_page()
    page.set_default_timeout(15_000)
    return pw, browser, context, page
