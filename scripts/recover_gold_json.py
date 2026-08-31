"""Recover full gold JSON from last MAIN485 eval + build_cases SQL."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from eval_q500_newset_cases import build_cases  # noqa: E402
from gen_eval_q500_newset import (  # noqa: E402
    OUT_JSON,
    OUT_MD,
    SRC_MD,
    parse_testset,
    payload,
    write_md,
)

RUN = ROOT / "artifacts/evaluation/main485_post_gold_refresh.json"
PATCH = ROOT / "artifacts/evaluation/gold_corrupt_backup.json"


def main() -> int:
    if OUT_JSON.is_file():
        PATCH.write_text(OUT_JSON.read_text(encoding="utf-8"), encoding="utf-8")

    run = json.loads(RUN.read_text(encoding="utf-8"))
    run_gold = {
        c["id"]: c.get("gold")
        for c in run.get("cases", [])
        if c.get("id")
    }
    patch_map = {}
    if PATCH.is_file():
        patch_doc = json.loads(PATCH.read_text(encoding="utf-8"))
        patch_map = {q["id"]: q for q in patch_doc.get("questions", [])}

    qmap = parse_testset(SRC_MD)
    cases = build_cases(qmap)
    for case in cases:
        patched = patch_map.get(case.id)
        if patched and patched.get("gold"):
            gold = patched["gold"]
            if patched.get("sql"):
                case.sql = patched["sql"]
        else:
            gold = run_gold.get(case.id) or case.gold_text or ""
        case.result = {
            "gold": gold,
            "row_count": patched.get("row_count", 0) if patched else 0,
            "ms": patched.get("ms", 0) if patched else 0,
            "error": None,
        }

    data = payload(cases, len(cases), 0, time.perf_counter())
    OUT_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    OUT_MD.write_text(write_md(cases, data), encoding="utf-8")
    print(f"restored {len(cases)} questions -> {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
