"""gt06/gt10 회귀 확인."""

from __future__ import annotations

import ollama

from txt2sql.config import load_settings
from txt2sql.db import connect
from txt2sql.intent_router import fix_common_sql_mistakes, try_route
from txt2sql.rag_sql import run_rag_sql

CASES = [
    ("gt06", "동래구 건물의 주요용도명 종류는 몇 가지야?", 29),
    ("gt10", "연제구 공동주택은 몇 채야?", 1824),
]


def main() -> None:
    bad6 = (
        'SELECT COUNT(DISTINCT "A9") FROM "AL_D010_26_20250704" '
        "WHERE \"A4\" LIKE '%동래구%';"
    )
    bad10 = (
        'SELECT COUNT(*) FROM "AL_D198_26260_20250115" '
        "WHERE \"A4\" LIKE '%연제구%' AND \"A25\" = '공동주택';"
    )
    print("fix6:", fix_common_sql_mistakes(bad6, question=CASES[0][1]))
    print("fix10:", fix_common_sql_mistakes(bad10, question=CASES[1][1]))
    print("route6:", try_route(CASES[0][1]))
    print("route10:", try_route(CASES[1][1]))

    settings = load_settings().with_overrides(ollama_model="qwen3:latest")
    client = ollama.Client(host=settings.ollama_host)
    passed = 0
    with connect(settings.database_url) as conn:
        for cid, q, exp in CASES:
            r = run_rag_sql(
                q, settings, conn=conn, ollama_client=client, skip_answer=True
            )
            rows = r.get("rows") or []
            got = list(rows[0].values())[0] if rows else None
            if isinstance(got, float) and got.is_integer():
                got = int(got)
            ok = bool(r.get("ok")) and got == exp
            passed += int(ok)
            print(f"{cid}: ok={ok} got={got} expected={exp}")
            print("  SQL:", r.get("sql"))
            if r.get("error"):
                print("  ERR:", r.get("error"))
    print(f"RESULT: {passed}/{len(CASES)}")


if __name__ == "__main__":
    main()
