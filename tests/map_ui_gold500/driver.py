"""맵 UI 대화창에 질문을 입력하고 답·과정을 수집한다.

브라우저(Playwright Chromium) 또는 동일 서버의 `/api/chat` HTTP SSE 드라이버를
지원한다. Chromium 미설치·headed UI 정지 문제를 피하려면 기본은 headless browser
이며, 브라우저 기동 실패 시 API 드라이버로 폴백할 수 있다.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright


class BrowserUnavailableError(RuntimeError):
    """Playwright Chromium을 기동할 수 없음."""


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


def _chromium_missing_message(exc: BaseException) -> bool:
    text = str(exc).lower()
    needles = (
        "executable doesn't exist",
        "browserType.launch",
        "chromium",
        "playwright install",
        "browser has been closed",
        "not found",
    )
    # Prefer specific install hints
    if "executable doesn't exist" in text:
        return True
    if "playwright install" in text:
        return True
    if "chromium" in text and ("missing" in text or "doesn't exist" in text or "not found" in text):
        return True
    return any(n in text for n in ("executable doesn't exist", "playwright install"))


def ensure_playwright_chromium(*, auto_install: bool = True) -> str:
    """Return Chromium executable path; optionally install if missing."""
    last: BaseException | None = None
    pw = sync_playwright().start()
    try:
        exe = Path(pw.chromium.executable_path)
        if exe.is_file():
            return str(exe)
        last = FileNotFoundError(f"Chromium executable missing: {exe}")
    except Exception as exc:  # noqa: BLE001 — probe only
        last = exc
    finally:
        pw.stop()

    if not auto_install:
        raise BrowserUnavailableError(
            "Playwright Chromium이 없습니다. "
            "`uv run playwright install chromium` 후 다시 실행하세요. "
            f"detail={last}"
        )

    print("[browser] Playwright Chromium 미설치 → 설치 시도…", flush=True)
    cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-800:]
        raise BrowserUnavailableError(
            "Playwright Chromium 자동 설치 실패. "
            "수동 실행: uv run playwright install chromium\n"
            f"{tail}"
        )

    pw = sync_playwright().start()
    try:
        exe = Path(pw.chromium.executable_path)
        if not exe.is_file():
            raise BrowserUnavailableError(
                f"설치 후에도 Chromium을 찾지 못했습니다: {exe}"
            )
        print(f"[browser] Chromium 준비됨: {exe}", flush=True)
        return str(exe)
    finally:
        pw.stop()


def _pack_ask_result(
    *,
    ms: int,
    timed_out: bool,
    error: str | None,
    events: list[dict[str, Any]],
    ui: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parsed = sse_result(events)
    ui = ui or {}
    if parsed.get("execution_trace"):
        ui = {**ui, "execution_trace": parsed.get("execution_trace")}
    if parsed.get("_error") and not error:
        error = parsed["_error"]
    if parsed.get("ok") is False and not error:
        error = str(parsed.get("error") or "engine-not-ok")
    answer = str(parsed.get("answer") or ui.get("answer") or "")
    sql = parsed.get("sql") or ui.get("sql") or ""
    rows = parsed.get("rows") if isinstance(parsed.get("rows"), list) else []
    return {
        "ms": ms,
        "timed_out": timed_out,
        "error": error,
        "answer": answer,
        "sql": sql,
        "rows": rows,
        "route": parsed.get("route"),
        "execution_source": parsed.get("execution_source"),
        "compiler_source": parsed.get("compiler_source"),
        "fallback_source": parsed.get("fallback_source"),
        "query_ir_task": parsed.get("query_ir_task"),
        "logical_status": parsed.get("logical_status"),
        "physical_strategy": parsed.get("physical_strategy"),
        "execution_trace": parsed.get("execution_trace"),
        "ui": ui,
        "process": parsed.get("_process") or events,
        "sse_ok": parsed.get("ok"),
        "row_count": parsed.get("row_count"),
        "session_id": parsed.get("_session_id"),
    }


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
        self.mode = "browser"

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
        ui: dict[str, Any] = {}
        try:
            ui = self.snapshot_ui()
        except Exception as exc:
            ui = {"error": f"snapshot:{type(exc).__name__}: {exc}"}
        return _pack_ask_result(
            ms=ms, timed_out=timed_out, error=error, events=events, ui=ui
        )


class ApiChatDriver:
    """맵 UI 서버 `/api/chat` SSE를 직접 호출 (브라우저 창 없음)."""

    def __init__(self, *, base_url: str, timeout_ms: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_ms = timeout_ms
        self._session_id: str | None = None
        self.mode = "api"

    def open(self) -> None:
        wait_health(self.base_url, timeout_s=5)
        # warm session endpoint if present
        try:
            req = Request(
                self.base_url + "/api/session",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=10) as res:
                payload = json.loads(res.read().decode("utf-8"))
                self._session_id = payload.get("session_id") or self._session_id
        except Exception:
            pass

    def start_new_chat(self) -> None:
        self._session_id = None
        try:
            req = Request(
                self.base_url + "/api/session",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=10) as res:
                payload = json.loads(res.read().decode("utf-8"))
                self._session_id = payload.get("session_id")
        except Exception:
            self._session_id = None

    def ask(self, question: str, *, new_session: bool) -> dict[str, Any]:
        if new_session:
            self.start_new_chat()
        body = {
            "question": question,
            "session_id": self._session_id,
            "include_map": True,
        }
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = Request(
            self.base_url + "/api/chat",
            data=raw,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "text/event-stream",
            },
            method="POST",
        )
        t0 = time.perf_counter()
        timed_out = False
        error: str | None = None
        events: list[dict[str, Any]] = []
        try:
            with urlopen(req, timeout=max(1.0, self.timeout_ms / 1000.0)) as res:
                text = res.read().decode("utf-8", errors="replace")
            events = parse_sse(text)
            parsed = sse_result(events)
            if parsed.get("_session_id"):
                self._session_id = parsed["_session_id"]
        except TimeoutError:
            timed_out = True
            error = f"timeout>{self.timeout_ms // 1000}s"
            events = [{"type": "error", "message": error}]
            self._session_id = None
        except HTTPError as exc:
            error = f"HTTPError:{exc.code}"
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:300]
                error = f"{error}:{detail}"
            except Exception:
                pass
            events = [{"type": "error", "message": error}]
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"[:300]
            events = [{"type": "error", "message": error}]
        ms = int((time.perf_counter() - t0) * 1000)
        return _pack_ask_result(
            ms=ms,
            timed_out=timed_out,
            error=error,
            events=events,
            ui={"mode": "api", "note": "browser UI snapshot skipped"},
        )


def launch_browser(
    *,
    headed: bool,
    slow_mo_ms: int = 0,
    auto_install: bool = True,
):
    """Launch Chromium. Defaults to headless; headed only when explicitly requested."""
    try:
        ensure_playwright_chromium(auto_install=auto_install)
    except BrowserUnavailableError:
        raise
    except Exception as exc:
        if _chromium_missing_message(exc):
            ensure_playwright_chromium(auto_install=auto_install)
        else:
            raise BrowserUnavailableError(str(exc)) from exc

    pw = sync_playwright().start()
    launch_kwargs: dict[str, Any] = {
        "headless": not headed,
        "args": [
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ],
    }
    if headed:
        # Visible watch mode: bring window to front (do NOT start minimized).
        launch_kwargs["args"].extend(
            [
                "--start-maximized",
                "--window-position=40,40",
            ]
        )
    else:
        launch_kwargs["args"].append("--disable-gpu")
    if slow_mo_ms:
        launch_kwargs["slow_mo"] = slow_mo_ms
    try:
        browser = pw.chromium.launch(**launch_kwargs)
    except PlaywrightError as exc:
        pw.stop()
        if auto_install and _chromium_missing_message(exc):
            ensure_playwright_chromium(auto_install=True)
            pw = sync_playwright().start()
            try:
                browser = pw.chromium.launch(**launch_kwargs)
            except Exception as retry_exc:
                pw.stop()
                raise BrowserUnavailableError(str(retry_exc)) from retry_exc
        else:
            raise BrowserUnavailableError(str(exc)) from exc
    except Exception as exc:
        pw.stop()
        raise BrowserUnavailableError(str(exc)) from exc

    context = browser.new_context(
        **(
            {"no_viewport": True}
            if headed
            else {"viewport": {"width": 1440, "height": 900}}
        ),
        locale="ko-KR",
    )
    page = context.new_page()
    page.set_default_timeout(15_000)
    return pw, browser, context, page
