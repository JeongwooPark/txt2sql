"""100문항 자연어 스모크 — Llm2SqlEngine.from_env() (CLI/웹과 동일 경로)."""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from pathlib import Path
from typing import Any

from llm2sql import Llm2SqlEngine, SessionContext

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).with_name("smoke_nl100.json")
OUT = Path(__file__).with_name("_out_nl100.json")
TIMEOUT_S = 75


def _clip(text: str, n: int = 220) -> str:
    t = (text or "").replace("\n", " / ")
    return t if len(t) <= n else t[: n - 3] + "..."


def _ask(engine: Llm2SqlEngine, q: str, session: SessionContext | None):
    return engine.ask(q, session=session)


def _diagnose() -> dict[str, Any]:
    info: dict[str, Any] = {"db": None, "ollama": None}
    try:
        from dotenv import load_dotenv
        import os
        import psycopg

        load_dotenv(ROOT / ".env")
        url = os.environ.get("DATABASE_URL", "")
        with psycopg.connect(url, connect_timeout=8) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), version()")
                db, ver = cur.fetchone()
                info["db"] = {"ok": True, "database": db, "version": str(ver)[:80]}
    except Exception as exc:
        info["db"] = {"ok": False, "error": str(exc)[:200]}
    try:
        from llm2sql.config import load_settings
        import urllib.request

        settings = load_settings()
        host = settings.ollama_host.rstrip("/")
        with urllib.request.urlopen(f"{host}/api/tags", timeout=5) as resp:
            info["ollama"] = {
                "ok": resp.status == 200,
                "host": host,
                "model": settings.ollama_model,
            }
    except Exception as exc:
        info["ollama"] = {"ok": False, "error": str(exc)[:200]}
    return info


def main() -> int:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    questions = fixture["questions"]
    diag = _diagnose()
    print("=== 진단 ===")
    print("DB:", diag.get("db"))
    print("Ollama:", diag.get("ollama"))
    if not (diag.get("db") or {}).get("ok"):
        payload = {
            "when": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total": len(questions),
            "ok": 0,
            "fail": len(questions),
            "elapsed_s": 0,
            "timeout_s": TIMEOUT_S,
            "diagnose": diag,
            "error": "DB 연결 실패 — 스모크를 실행하지 않음",
            "rows": [],
        }
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print("DB 불가. JSON만 기록:", OUT)
        return 2

    sessions: dict[str, SessionContext] = {}
    rows: list[dict[str, Any]] = []
    t0 = time.perf_counter()
    passed = 0
    engine = Llm2SqlEngine.from_env()
    try:
        print(f"=== 신규 100문항 자연어 스모크 (timeout={TIMEOUT_S}s) ===\n")
        for i, case in enumerate(questions, 1):
            qid = case["id"]
            q = case["q"]
            cat = case.get("category") or case.get("expected_category")
            sid = case.get("session")
            session = sessions.setdefault(sid, SessionContext()) if sid else None
            t1 = time.perf_counter()
            timed_out = False
            error = None
            r = None
            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    fut = pool.submit(_ask, engine, q, session)
                    r = fut.result(timeout=TIMEOUT_S)
            except FuturesTimeout:
                timed_out = True
                error = f"timeout>{TIMEOUT_S}s"
                try:
                    engine.close()
                except Exception:
                    pass
                engine = Llm2SqlEngine.from_env()
            except Exception as exc:
                error = str(exc)[:300]
                try:
                    engine.close()
                except Exception:
                    pass
                engine = Llm2SqlEngine.from_env()
            ms = int((time.perf_counter() - t1) * 1000)
            ok = bool(r and r.ok and str(r.answer or "").strip() and not timed_out)
            if ok:
                passed += 1
            answer = "" if r is None else (r.answer or "")
            route = None if r is None else r.route
            sql = None if r is None else r.sql
            map_obj = None if r is None else r.map
            rec = {
                "id": qid,
                "cat": cat,
                "q": q,
                "ok": ok,
                "route": route,
                "error": error or (None if r is None else r.error),
                "latency_ms": ms,
                "answer": _clip(answer),
                "sql_present": bool(sql),
                "map_available": bool(map_obj),
                "row_count": 0 if r is None else (r.row_count or 0),
                "session": sid,
                "timed_out": timed_out,
                "map_eligible_expected": case.get("map_eligible"),
            }
            rows.append(rec)
            status = "OK" if ok else "FAIL"
            print(f"[{qid}] {status}  {cat}  {ms}ms  route={route}")
            print(f"  Q: {q}")
            print(f"  A: {_clip(answer, 160)}")
            if rec["error"]:
                print(f"  err: {rec['error']}")
            print()
            if i % 5 == 0 or i == len(questions):
                elapsed = time.perf_counter() - t0
                interim = {
                    "when": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "elapsed_s": round(elapsed, 1),
                    "timeout_s": TIMEOUT_S,
                    "total": len(questions),
                    "ran": i,
                    "ok": passed,
                    "fail": i - passed,
                    "diagnose": diag,
                    "rows": rows,
                    "partial": i < len(questions),
                }
                OUT.write_text(
                    json.dumps(interim, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
    finally:
        try:
            engine.close()
        except Exception:
            pass

    elapsed = time.perf_counter() - t0
    total = len(questions)
    payload = {
        "when": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_s": round(elapsed, 1),
        "timeout_s": TIMEOUT_S,
        "total": total,
        "ok": passed,
        "fail": total - passed,
        "pass_rate": round(passed / total, 4) if total else 0,
        "avg_latency_ms": int(sum(r["latency_ms"] for r in rows) / len(rows)) if rows else 0,
        "diagnose": diag,
        "questions_file": str(FIXTURE),
        "source": fixture.get("source"),
        "generated_at": fixture.get("generated_at"),
        "rows": rows,
        "partial": False,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"=== 결과: {passed}/{total} OK  {elapsed:.1f}s ===")
    print(f"JSON: {OUT}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
