"""NL→SQL 파이프라인 평가. 모드 A=off, B=hybrid.

실행 성공만으로 정답 처리하지 않는다. gold Plan/result hash/clarify가 있는
verified 사례만 공식 지표에 쓴다. DB 또는 Ollama가 없으면 ENV_BLOCKED.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _env_ready() -> tuple[bool, str]:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    alt = Path(r"D:\py_workspace\llm2sql\.env")
    if alt.exists():
        load_dotenv(alt)
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return False, "DATABASE_URL missing"
    try:
        import psycopg
        import urllib.request
        from txt2sql.config import load_settings

        with psycopg.connect(url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        settings = load_settings()
        host = settings.ollama_host.rstrip("/")
        urllib.request.urlopen(f"{host}/api/tags", timeout=3).read()
    except Exception as exc:  # noqa: BLE001
        return False, type(exc).__name__
    return True, "ok"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate NL2SQL pipeline")
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument("--mode", choices=("off", "hybrid", "shadow"), default="off")
    parser.add_argument("--verified-only", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--official", action="store_true")
    args = parser.parse_args(argv)

    from txt2sql.evaluation.jsonl import load_jsonl
    from txt2sql.evaluation.harness import evaluate_case
    from txt2sql.evaluation.schema import EvalSummary

    cases = load_jsonl(args.gold)
    if args.verified_only:
        cases = [c for c in cases if c.status == "verified"]
    if args.limit is not None:
        cases = cases[: args.limit]

    ready, reason = _env_ready()
    if not ready:
        summary = EvalSummary(
            name="eval_nl2sql",
            mode=args.mode,
            n=len(cases),
            n_verified=sum(1 for c in cases if c.status == "verified"),
            passed=0,
            failed=len(cases),
            metrics={},
            env_blocked=True,
            error_counts={"ENV_BLOCKED": 1},
        )
        payload = {"summary": summary.model_dump(), "items": [], "block_reason": reason}
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
        print(text)
        return 2

    from txt2sql import Txt2SqlEngine
    from txt2sql.config import load_settings
    from txt2sql.observability import official_benchmark_allowed

    settings = load_settings().with_overrides(semantic_plan_mode=args.mode)
    if args.official:
        allowed, why = official_benchmark_allowed(
            settings.planner_model(), settings.ollama_embed_model
        )
        if not allowed:
            payload = {
                "summary": {"name": "eval_nl2sql", "env_blocked": True, "error": why},
                "items": [],
                "block_reason": why,
            }
            text = json.dumps(payload, ensure_ascii=False, indent=2)
            if args.out:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(text, encoding="utf-8")
            print(text)
            return 2
    engine = Txt2SqlEngine.from_settings(settings)
    items = []
    errors: Counter[str] = Counter()
    try:
        for case in cases:
            t0 = time.perf_counter()
            result = None
            error = None
            try:
                result = engine.ask(case.question, include_map=False)
            except Exception as exc:  # noqa: BLE001
                error = f"{type(exc).__name__}: {exc}"
            ms = int((time.perf_counter() - t0) * 1000)
            extra = (
                result.semantic_plan
                if result is not None and isinstance(result.semantic_plan, dict)
                else {}
            )
            plan = extra or None
            clarify = bool(extra.get("requires_clarification")) if extra else False
            route = result.route if result is not None else None
            if route == "semantic_plan_clarify":
                clarify = True
            scored = evaluate_case(
                case,
                predicted_plan=plan,
                predicted_route=route,
                predicted_rows=list((result.rows if result is not None else None) or []),
                predicted_clarify=clarify,
                sql_executed=bool(result.sql) if result is not None else False,
                latency_ms=ms,
            )
            print(
                f"{case.id} pass={scored.pass_} route={route} ms={ms} {error or ''}".strip(),
                flush=True,
            )
            items.append(scored.model_dump(by_alias=True))
            errors.update(scored.error_codes)
    finally:
        engine.close()

    passed = sum(1 for item in items if item["pass"])
    summary = EvalSummary(
        name="eval_nl2sql",
        mode=args.mode,
        n=len(cases),
        n_verified=sum(1 for c in cases if c.status == "verified"),
        passed=passed,
        failed=len(cases) - passed,
        error_counts=dict(errors),
        metrics={"semantic_accuracy": passed / len(cases) if cases else 0.0},
        env_blocked=False,
    )
    digests = {}
    try:
        import urllib.request

        host = settings.ollama_host.rstrip("/")
        tags = json.loads(urllib.request.urlopen(f"{host}/api/tags", timeout=5).read())
        digests = {
            str(item.get("name") or ""): str(item.get("digest") or "")[:16]
            for item in tags.get("models") or []
        }
    except Exception:  # noqa: BLE001
        digests = {}
    payload = {
        "summary": summary.model_dump(),
        "items": items,
        "official": args.official,
        "models": {
            "plan": settings.planner_model(),
            "embed": settings.ollama_embed_model,
            "plan_digest": digests.get(settings.planner_model())
            or digests.get(f"{settings.planner_model()}:latest"),
            "embed_digest": digests.get(settings.ollama_embed_model)
            or digests.get(f"{settings.ollama_embed_model}:latest"),
            "note": ":latest tag in use; official flag omitted; digests recorded from ollama /api/tags",
        },
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
