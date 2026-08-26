"""맵 UI 골드 테스트 실행기.

맵 화면(`/map`) 또는 동일 서버 `/api/chat`로 문항을 실행하고, 답·과정(SSE)을
저장한 다음 골드 수치와 대조한다.

기본은 **headless Chromium** (창을 띄우지 않음). 브라우저 창이 필요하면
`--headed`를 명시한다. Chromium 미설치 시 자동 설치를 시도하고, 실패하면
맵 UI 서버의 API SSE로 폴백한다 (`--require-browser`로 폴백 금지 가능).

    uv run python -m tests.map_ui_gold500.run --start-server
    uv run python -m tests.map_ui_gold500.run --headless --start-server
    uv run python -m tests.map_ui_gold500.run --headed
    uv run python -m tests.map_ui_gold500.run --driver api --start-server
    uv run python -m tests.map_ui_gold500.run --limit 10
    uv run python -m tests.map_ui_gold500.run --ids N001,N004
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RESULTS_DIR = HERE / "results"
DEFAULT_BASE = "http://127.0.0.1:8000"
DEFAULT_MAP = DEFAULT_BASE + "/map"


def _utf8_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="맵 UI 대화창 골드 테스트")
    p.add_argument(
        "--questions",
        type=Path,
        default=HERE / "questions.json",
        help="교체 가능한 문항 JSON (include 또는 questions 배열)",
    )
    p.add_argument("--ids", default="", help="쉼표로 구분한 문항 id만 실행")
    p.add_argument("--limit", type=int, default=0, help="앞에서 N문항만 (0=전체)")
    p.add_argument("--url", default=DEFAULT_MAP, help="맵 UI URL")
    p.add_argument("--timeout", type=int, default=60, help="문항당 초")
    # Default: headless. Only --headed opens a visible window.
    p.add_argument(
        "--headed",
        action="store_true",
        help="브라우저 창 표시 (기본은 headless — 창을 띄우지 않음)",
    )
    p.add_argument(
        "--headless",
        action="store_true",
        help="브라우저 숨김 (기본값, 명시용 호환 플래그)",
    )
    p.add_argument(
        "--driver",
        choices=("auto", "browser", "api"),
        default="auto",
        help="browser=Playwright, api=/api/chat SSE, auto=browser 실패 시 api 폴백",
    )
    p.add_argument(
        "--require-browser",
        action="store_true",
        help="브라우저 기동 실패 시 api 폴백하지 않고 종료",
    )
    p.add_argument(
        "--no-install-browsers",
        action="store_true",
        help="Chromium 자동 설치를 하지 않음",
    )
    p.add_argument("--slow-mo", type=int, default=0, help="입력 지연 ms (browser only)")
    p.add_argument("--start-server", action="store_true", help="서버가 없으면 기동")
    p.add_argument("--out", type=Path, default=RESULTS_DIR / "latest.json")
    p.add_argument("--transcript", type=Path, default=RESULTS_DIR / "transcript.jsonl")
    return p.parse_args(argv)


def resolve_headed(args: argparse.Namespace) -> bool:
    """Headless is default. --headed wins; bare --headless keeps headless."""
    if args.headed and args.headless:
        # Explicit conflict: prefer headless for automation safety.
        return False
    if args.headed:
        return True
    return False


def _select(
    questions: list[dict[str, Any]], ids: set[str] | None, limit: int
) -> list[dict[str, Any]]:
    selected = questions
    if ids:
        sessions = {c["id"]: c.get("session") for c in questions}
        wanted_sessions = {sessions[i] for i in ids if sessions.get(i)}
        selected = [
            c
            for c in questions
            if c["id"] in ids or (c.get("session") and c["session"] in wanted_sessions)
        ] or [c for c in questions if c["id"] in ids]
    if limit and limit > 0:
        selected = selected[:limit]
    return selected


def _base_url(map_url: str) -> str:
    parsed = urlparse(map_url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _ensure_server(base: str, start: bool) -> subprocess.Popen[Any] | None:
    from tests.map_ui_gold500.driver import health_ok, wait_health

    if health_ok(base):
        print(f"[server] 기존 맵 UI 사용 {base}", flush=True)
        return None
    if not start:
        raise SystemExit(
            f"맵 UI 서버가 없습니다 ({base}/api/health). "
            "uv run txt2sql-web 후 다시 실행하거나 --start-server 를 쓰세요."
        )
    print(f"[server] {base} 기동 중…", flush=True)
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "txt2sql.webapp.app:app",
            "--host",
            urlparse(base).hostname or "127.0.0.1",
            "--port",
            str(urlparse(base).port or 8000),
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_health(base, timeout_s=90)
    except Exception:
        proc.terminate()
        raise
    print("[server] 기동 완료", flush=True)
    return proc


def _dump(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, rec: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    slim = {
        "id": rec.get("id"),
        "q": rec.get("q"),
        "pass": rec.get("pass"),
        "reason": rec.get("reason"),
        "answer": rec.get("answer"),
        "gold": rec.get("gold"),
        "route": rec.get("route"),
        "ms": rec.get("ms"),
        "process": rec.get("process"),
        "ui": rec.get("ui"),
        "sql": rec.get("sql"),
        "timed_out": rec.get("timed_out"),
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(slim, ensure_ascii=False) + "\n")


def _make_api_driver(base: str, timeout_s: int):
    from tests.map_ui_gold500.driver import ApiChatDriver

    return ApiChatDriver(base_url=base, timeout_ms=timeout_s * 1000)


def main(argv: list[str] | None = None) -> int:
    _utf8_stdio()
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    args = _parse_args(argv)
    headed = resolve_headed(args)
    from tests.map_ui_gold500.driver import (
        BrowserUnavailableError,
        MapUiDriver,
        launch_browser,
    )
    from tests.map_ui_gold500.questions_loader import load_questions
    from tests.map_ui_gold500.scoring import score_case, summarize

    meta, questions = load_questions(args.questions)
    wanted = {x.strip() for x in args.ids.split(",") if x.strip()} or None
    questions = _select(questions, wanted, args.limit)
    if not questions:
        raise SystemExit("실행할 문항이 없습니다. questions.json 을 확인하세요.")

    base = _base_url(args.url)
    server = _ensure_server(base, args.start_server)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if args.transcript.exists():
        args.transcript.unlink()

    driver_mode = args.driver
    pw = browser = context = page = None
    driver: Any = None

    try:
        if driver_mode in {"browser", "auto"}:
            try:
                pw, browser, context, page = launch_browser(
                    headed=headed,
                    slow_mo_ms=args.slow_mo,
                    auto_install=not args.no_install_browsers,
                )
                driver = MapUiDriver(
                    page, map_url=args.url, timeout_ms=args.timeout * 1000
                )
                driver_mode = "browser"
            except BrowserUnavailableError as exc:
                if args.driver == "browser" or args.require_browser:
                    raise SystemExit(
                        f"브라우저 기동 실패: {exc}\n"
                        "uv run playwright install chromium\n"
                        "또는 --driver api 로 맵 UI 서버 SSE만 사용하세요."
                    ) from exc
                print(
                    f"[browser] 사용 불가 → API 드라이버로 폴백\n  reason: {exc}",
                    flush=True,
                )
                driver = _make_api_driver(base, args.timeout)
                driver_mode = "api"
        else:
            driver = _make_api_driver(base, args.timeout)
            driver_mode = "api"

        print(
            f"=== 맵 UI 골드 테스트 questions={meta.get('path')} "
            f"n={len(questions)} url={args.url} timeout={args.timeout}s "
            f"driver={driver_mode} "
            f"{'headed' if headed and driver_mode == 'browser' else 'headless/cli'} ===\n",
            flush=True,
        )

        rows: list[dict[str, Any]] = []
        t0 = time.perf_counter()
        prev_session: object | None = object()
        driver.open()
        for i, case in enumerate(questions, 1):
            sid = case.get("session")
            # session이 없으면 문항마다 새 대화. 같은 session 키만 후속으로 이어간다.
            new_session = sid is None or sid != prev_session
            prev_session = sid
            print(f"[{i:03d}/{len(questions)}] … {case['id']} {case['q'][:48]}", flush=True)
            raw = driver.ask(case["q"], new_session=new_session)
            rec = score_case(
                case,
                answer=raw.get("answer") or "",
                rows=raw.get("rows"),
                sql=raw.get("sql"),
                route=raw.get("route"),
                error=raw.get("error"),
                timed_out=bool(raw.get("timed_out")),
                ms=int(raw.get("ms") or 0),
                ui=raw.get("ui") or {},
                process=list(raw.get("process") or []),
            )
            rows.append(rec)
            _append_jsonl(args.transcript, rec)
            mark = "OK" if rec["pass"] else "FAIL"
            print(
                f"[{i:03d}/{len(questions)}] {mark} {case['id']} "
                f"{rec['ms']}ms {case.get('kind')} {rec['reason']}",
                flush=True,
            )
            if i % 5 == 0 or i == len(questions):
                payload = summarize(rows, time.perf_counter() - t0)
                payload["partial"] = i < len(questions)
                payload["timeout_s"] = args.timeout
                payload["gold_file"] = meta.get("included") or meta.get("path")
                payload["ui"] = {
                    "url": args.url,
                    "headed": headed if driver_mode == "browser" else False,
                    "driver": driver_mode,
                    "questions_file": meta.get("path"),
                    "questions_name": meta.get("name"),
                    "included": meta.get("included"),
                    "mode": "map-ui-chat" if driver_mode == "browser" else "map-ui-api",
                }
                _dump(args.out, payload)
                print(
                    f"  .. saved {payload['passed']}/{payload['total']} "
                    f"acc={payload['accuracy_pct']}% elapsed={payload['elapsed_s']}s",
                    flush=True,
                )

        payload = summarize(rows, time.perf_counter() - t0)
        payload["partial"] = False
        payload["timeout_s"] = args.timeout
        payload["gold_file"] = meta.get("included") or meta.get("path")
        payload["ui"] = {
            "url": args.url,
            "headed": headed if driver_mode == "browser" else False,
            "driver": driver_mode,
            "questions_file": meta.get("path"),
            "questions_name": meta.get("name"),
            "included": meta.get("included"),
            "mode": "map-ui-chat" if driver_mode == "browser" else "map-ui-api",
            "transcript": str(args.transcript),
        }
        _dump(args.out, payload)
        print(
            f"\n=== 결과 {payload['passed']}/{payload['total']} "
            f"({payload['accuracy_pct']}%) {payload['elapsed_s']}s ===",
            flush=True,
        )
        print("wrote", args.out, flush=True)
        print("wrote", args.transcript, flush=True)
        return 0 if payload.get("failed", 1) == 0 else 1
    finally:
        # Ordered Playwright teardown avoids TargetClosedError noise on Windows.
        try:
            if page is not None:
                page.close()
        except Exception:
            pass
        try:
            if context is not None:
                context.close()
        except Exception:
            pass
        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass
        try:
            if pw is not None:
                pw.stop()
        except Exception:
            pass
        if server is not None:
            try:
                server.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
