"""기존 smoke 30·100을 candidate(draft) benchmark로 가져온다.

실행 결과를 gold로 복사하지 않는다. status는 항상 draft.
SQL 토큰 힌트는 notes에만 남기고 정답 판정에 쓰지 않는다.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from llm2sql.evaluation.jsonl import dump_jsonl
from llm2sql.evaluation.schema import GoldPlanCase

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "benchmarks" / "korean_postgis_v1"


def _load_compound_module():
    import sys

    path = ROOT / "scripts" / "smoke_compound30.py"
    spec = importlib.util.spec_from_file_location("smoke_compound30", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def compound30_cases() -> list[GoldPlanCase]:
    module = _load_compound_module()
    cases: list[GoldPlanCase] = []
    for item in module.CASES:
        notes = []
        if item.sql_all:
            notes.append("sql_token_hints_not_gold=" + ",".join(item.sql_all))
        if item.forbid_routes:
            notes.append("forbid_routes=" + ",".join(item.forbid_routes))
        cases.append(
            GoldPlanCase(
                id=item.id,
                question=item.q,
                status="draft",
                split="candidate",
                source="scripts/smoke_compound30.py",
                gold_clarify=item.allow_clarify,
                notes="; ".join(notes),
                verification="imported as unverified candidate; not copied from system output",
            )
        )
    return cases


def nl100_cases() -> list[GoldPlanCase]:
    payload = json.loads(
        (ROOT / "scripts" / "smoke_nl100.json").read_text(encoding="utf-8")
    )
    cases: list[GoldPlanCase] = []
    for item in payload["questions"]:
        cases.append(
            GoldPlanCase(
                id=item["id"],
                question=item["q"],
                status="draft",
                split="candidate",
                source="scripts/smoke_nl100.json",
                notes=item.get("category", ""),
                verification="imported as unverified candidate; execution success is not gold",
            )
        )
    return cases


def write_candidate_files(out_dir: Path | None = None) -> dict[str, Path]:
    target = out_dir or OUT_DIR
    target.mkdir(parents=True, exist_ok=True)
    paths = {
        "compound30": target / "candidate_compound30.jsonl",
        "nl100": target / "candidate_nl100.jsonl",
    }
    dump_jsonl(paths["compound30"], compound30_cases())
    dump_jsonl(paths["nl100"], nl100_cases())
    return paths
