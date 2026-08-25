from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from txt2sql.engine import Txt2SqlEngine
from txt2sql.keyboard import is_exit_command
from txt2sql.session import SessionContext


def _print_progress(stage: str, message: str, detail: dict[str, Any] | None) -> None:
    print(f"[{stage}] {message}", flush=True)
    if not detail:
        return
    if "sql" in detail and detail["sql"]:
        sql = str(detail["sql"]).strip()
        preview = sql if len(sql) <= 200 else sql[:197] + "..."
        print(f"         sql: {preview}", flush=True)
    if "tables" in detail and detail["tables"]:
        print(f"         tables: {', '.join(detail['tables'])}", flush=True)
    if "intent" in detail and detail["intent"]:
        print(f"         intent: {detail['intent']}", flush=True)
    if "row_count" in detail and detail["row_count"] is not None:
        print(f"         rows: {detail['row_count']}", flush=True)


def _ensure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8")
            except Exception:
                pass


def _print_result(result: Any, *, verbose: bool, progress: bool) -> None:
    data = result.to_dict() if hasattr(result, "to_dict") else result
    if progress:
        print("---", flush=True)
    print(data.get("answer") or "(답변 없음)")
    if not verbose:
        return
    if data.get("route"):
        print(f"\n[route] {data['route']}")
    if data.get("tables"):
        print("[tables]", ", ".join(data["tables"]))
    if data.get("sql"):
        print("[sql]")
        print(data["sql"])
    if data.get("ok") and data.get("rows"):
        print(f"[rows] {data['row_count']}")
        for i, row in enumerate(data["rows"][:20], start=1):
            print(f"{i}. {dict(row)}")


def main() -> None:
    _ensure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="자연어 질의를 PostgreSQL SQL로 변환해 실행합니다."
    )
    parser.add_argument(
        "question",
        nargs="?",
        help="자연어 질의 (없으면 대화형 입력)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="결과를 JSON으로 출력",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="SQL·원본 행도 함께 출력",
    )
    parser.add_argument(
        "--progress",
        "-p",
        action="store_true",
        help="단계별 진행상황을 실시간 출력",
    )
    parser.add_argument(
        "--chat",
        action="store_true",
        help="대화형 모드(후속 질문·직전 결과 유지)",
    )
    args = parser.parse_args()

    session = SessionContext()
    on_progress = _print_progress if (args.progress and not args.json) else None

    with Txt2SqlEngine.from_env() as engine:
        if args.chat or not args.question:
            if args.question:
                questions = [args.question]
                first_done = False
            else:
                questions = []
                first_done = True
                print(
                    "대화형 모드입니다. 후속 질문 예: 「그 아파트의 이름은?」\n"
                    "기능/제한: 「기능 알려줘」 「제한이 뭐야?」 / 종료: exit, quit, 종료",
                    flush=True,
                )

            while True:
                if not first_done and questions:
                    q = questions.pop(0)
                    first_done = True
                else:
                    try:
                        q = input("질문> ").strip()
                    except (EOFError, KeyboardInterrupt):
                        print()
                        break
                if not q:
                    continue
                if is_exit_command(q):
                    break
                result = engine.ask(
                    q, on_progress=on_progress, session=session
                )
                if args.json:
                    print(
                        json.dumps(
                            result.to_dict(),
                            ensure_ascii=False,
                            indent=2,
                            default=str,
                        )
                    )
                else:
                    _print_result(
                        result,
                        verbose=args.verbose,
                        progress=bool(args.progress),
                    )
            return

        result = engine.ask(
            args.question, on_progress=on_progress, session=session
        )
        if args.json:
            print(
                json.dumps(
                    result.to_dict(), ensure_ascii=False, indent=2, default=str
                )
            )
            if not result.ok:
                sys.exit(1)
            return

        _print_result(result, verbose=args.verbose, progress=bool(args.progress))
        if not result.ok:
            sys.exit(1)


if __name__ == "__main__":
    main()
