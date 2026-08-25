"""신규 자연어 질의 테스트셋 500건 채점 정답표 생성.

정답은 KorDB 실쿼리 결과이며, SQL 토큰 일치만으로는 정답으로 보지 않는다.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
URL = os.environ.get("DATABASE_URL", "").strip()

SRC_MD = ROOT / "docs" / "llm2sql_신규_자연어질의_테스트셋_500건_수정본.md"
OUT_MD = ROOT / "docs" / "llm2sql_신규_자연어질의_테스트셋_500건_정답표.md"
OUT_JSON = ROOT / "docs" / "llm2sql_신규_자연어질의_테스트셋_500건_정답표.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))

from gen_eval_q500 import format_gold, run_sql  # noqa: E402
from eval_q500_newset_cases import build_cases  # noqa: E402

ROW_RE = re.compile(
    r"^\| (Q\d{3}) \| (\S+) \| (\S+) \| (.+?) \| (.+?) \|\s*$"
)
SEC_RE = re.compile(r"^### (.+)$")


def parse_testset(path: Path) -> dict[str, dict]:
    section = ""
    out: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        sm = SEC_RE.match(line)
        if sm and sm.group(1)[0].isdigit():
            section = sm.group(1).strip()
            continue
        rm = ROW_RE.match(line)
        if not rm:
            continue
        qid, diff, typ, q, point = rm.groups()
        out[qid] = {
            "section": section,
            "difficulty": diff,
            "type": typ,
            "q": q.strip(),
            "point": point.strip(),
        }
    if len(out) != 500:
        raise RuntimeError(f"parsed {len(out)} questions from {path}, expected 500")
    return out


def write_md(cases, meta: dict) -> str:
    lines = [
        "# txt2sql 신규 자연어 질의 테스트셋 500건 정답표",
        "",
        f"- 생성 시각: {meta['when']}",
        f"- 데이터베이스: gisdb (KorDB)",
        f"- 원본 문항: `{SRC_MD.name}`",
        f"- 실행 성공: {meta['ok']} / {meta['total']}",
        f"- 쿼리 실패: {meta['fail']}",
        "",
        "## 평가 원칙",
        "",
        "1. **답까지 같아야 정답이다.** SQL에 COUNT/JOIN 토큰이 있어도 수치가 다르면 오답이다.",
        "2. 건수·합계·평균·비율은 아래 정답의 숫자와 일치해야 한다 (천 단위 콤마·단위 표기 차이는 허용).",
        "3. 목록·순위는 1위(또는 요청한 Top-N의 구성원)가 같아야 한다. 정렬 키가 다르면 오답이다.",
        "4. 후속 질문(Q489–Q500)은 선행 질문의 결과 집합을 유지한 채 추가 조건만 적용한 정답과 비교한다. 세션 `FU01`의 앵커는 Q478(해운대구 연면적 1만㎡ 초과)이다.",
        "5. 안내·범위외·모호 문항(Q451–Q470)은 아래 정답 요지(거절/확인/도움말)와 같아야 한다.",
        "6. SQL 실행 성공만으로 정답 처리하지 말고, 질문의 모든 조건이 Plan/SQL에 보존되었는지 확인한다.",
        "7. 결과가 0건이어도 조건이 정확하면 성공이며 임의 조건 완화는 오답이다.",
        "8. 높이 TOP-K·최고값은 이상치(0 이하 또는 500m 초과)를 제외한 정상 범위를 정답으로 본다. Q134 등 이상치 탐지 문항은 제외하지 않는다.",
        "",
        "## 채점 기록 권고",
        "",
        "`question_id`, `route`, `generated_sql`, `gold`, `pred`, `match`, `latency_ms`, `error_type`, `review_note`",
        "",
    ]
    current_cat = None
    for case in cases:
        if case.cat != current_cat:
            lines.append(f"## {case.cat}")
            lines.append("")
            current_cat = case.cat
        lines.append(f"### {case.id}")
        lines.append("")
        lines.append(f"- **질문:** {case.q}")
        if case.session:
            lines.append(f"- **세션:** `{case.session}`")
        if case.parent:
            lines.append(f"- **선행:** {case.parent}")
        if case.note:
            lines.append(f"- **비고:** {case.note}")
        lines.append(f"- **유형:** {case.kind}")
        gold = case.result.get("gold") or case.gold_text or ""
        lines.append(f"- **정답:** {gold}")
        if case.sql:
            lines.append("- **정답 SQL:**")
            lines.append("")
            lines.append("```sql")
            lines.append(case.sql.strip())
            lines.append("```")
            rc = case.result.get("row_count")
            ms = case.result.get("ms")
            err = case.result.get("error")
            extra = []
            if rc is not None:
                extra.append(f"행 {rc}")
            if ms is not None:
                extra.append(f"{ms}ms")
            if err:
                extra.append(f"오류: {err}")
            if extra:
                lines.append("")
                lines.append(f"- **실행:** {', '.join(extra)}")
        lines.append("")
    return "\n".join(lines) + "\n"


def payload(cases, ok: int, fail: int, t0: float) -> dict:
    return {
        "when": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(cases),
        "ok": ok,
        "fail": fail,
        "elapsed_s": round(time.perf_counter() - t0, 1),
        "source": str(SRC_MD),
        "evaluation": "answer_must_match_gold_not_sql_tokens_only",
        "questions": [
            {
                "id": c.id,
                "cat": c.cat,
                "q": c.q,
                "kind": c.kind,
                "source": "newset500",
                "session": c.session,
                "parent": c.parent,
                "sql": c.sql,
                "gold": c.result.get("gold") or c.gold_text,
                "row_count": c.result.get("row_count"),
                "error": c.result.get("error"),
                "ms": c.result.get("ms"),
                "note": c.note,
            }
            for c in cases
        ],
    }


def _cached_ok(old: dict | None) -> bool:
    if not old:
        return False
    gold = old.get("gold") or ""
    if old.get("error") or str(gold).startswith("쿼리 실패"):
        return False
    if old.get("sql") is None and gold:
        return True
    return bool(gold)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not URL:
        print("DATABASE_URL missing")
        return 1
    only = set()
    if "--only" in sys.argv:
        i = sys.argv.index("--only")
        only = {x.strip() for x in sys.argv[i + 1].split(",") if x.strip()}
    resume = "--resume" in sys.argv
    prev: dict[str, dict] = {}
    if resume and OUT_JSON.exists():
        prev = {q["id"]: q for q in json.loads(OUT_JSON.read_text(encoding="utf-8"))["questions"]}

    qmap = parse_testset(SRC_MD)
    cases = build_cases(qmap)
    if only:
        cases = [c for c in cases if c.id in only]

    ok = fail = 0
    t0 = time.perf_counter()
    with psycopg.connect(URL, row_factory=dict_row, connect_timeout=20) as conn:
        conn.execute("SET statement_timeout = '180s'")
        conn.execute("SET work_mem = '256MB'")
        cur = conn.cursor()
        for i, case in enumerate(cases, 1):
            old = prev.get(case.id)
            if resume and _cached_ok(old) and (not case.sql or old.get("sql") == case.sql):
                case.result = {
                    "gold": old.get("gold"),
                    "row_count": old.get("row_count") or 0,
                    "ms": old.get("ms") or 0,
                    "error": None,
                }
                ok += 1
                print(f"[{i:03}/{len(cases)}] SKIP {case.id} cached", flush=True)
                continue
            t1 = time.perf_counter()
            error = None
            rows = None
            if case.id in {"Q436", "Q437"}:
                timeout = "900s"
            elif case.id >= "Q361":
                timeout = "600s"
            else:
                timeout = "180s"
            if case.sql:
                try:
                    conn.execute(f"SET statement_timeout = '{timeout}'")
                    rows = run_sql(cur, case.sql)
                except Exception as exc:
                    conn.rollback()
                    error = f"{type(exc).__name__}: {exc}"[:500]
                    fail += 1
                else:
                    ok += 1
            else:
                ok += 1
            ms = int((time.perf_counter() - t1) * 1000)
            gold = format_gold(case, rows, error)
            case.result = {
                "gold": gold,
                "row_count": 0 if rows is None else len(rows),
                "ms": ms,
                "error": error,
            }
            status = "ERR" if error else "OK"
            print(f"[{i:03}/{len(cases)}] {status} {case.id} {ms}ms {case.q[:48]}", flush=True)
            if error:
                print(f"    {error}", flush=True)
            if i % 25 == 0:
                OUT_JSON.write_text(
                    json.dumps(payload(cases, ok, fail, t0), ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8",
                )

    data = payload(cases, ok, fail, t0)
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    OUT_MD.write_text(write_md(cases, data), encoding="utf-8")
    print(f"wrote {OUT_MD}")
    print(f"wrote {OUT_JSON}")
    print(f"ok={ok} fail={fail} n={len(cases)} elapsed={data['elapsed_s']}s")
    return 0 if fail == 0 and (only or len(cases) == 500) else 1


if __name__ == "__main__":
    raise SystemExit(main())
