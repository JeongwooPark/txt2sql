"""Canonical benchmark run artifacts — single source of truth for evaluation."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from txt2sql.config import load_settings
from txt2sql.evaluation.case_map import case_rows
from txt2sql.evaluation.execution_sources import share_execution_sources
from txt2sql.evaluation.gold_checksum import FROZEN_GOLD_CHECKSUMS, verify_gold_checksums

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_RUNS_DIR = ROOT / "artifacts" / "benchmark_runs"


def _git_commit() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except Exception:
        return "unknown"


def _git_dirty() -> bool | None:
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return bool(out.strip())
    except Exception:
        return None


def _config_hash() -> str:
    settings = load_settings()
    payload = {
        "ollama_model": settings.ollama_model,
        "ollama_embed_model": settings.ollama_embed_model,
        "semantic_plan_mode": settings.semantic_plan_mode,
        "intent_mode": settings.intent_mode,
        "route_dispatch_mode": settings.route_dispatch_mode,
        "reference_date": settings.reference_date,
        "default_sido": settings.default_sido,
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_run_id(*, label: str = "main485") -> str:
    """Generate run_id like 20260828_be9ec6d_main485."""
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    commit = _git_commit()[:7] if _git_commit() != "unknown" else "unknown"
    return f"{date}_{commit}_{label}"


def _aggregate_by(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        val = str(row.get(key) or "unknown")
        buckets.setdefault(val, []).append(row)
    out: dict[str, dict[str, Any]] = {}
    for name, items in buckets.items():
        ok = sum(1 for r in items if r.get("pass"))
        out[name] = {"n": len(items), "ok": ok, "acc_pct": round(100.0 * ok / len(items), 1) if items else 0.0}
    return out


def _error_class_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        if row.get("pass"):
            continue
        for cause in row.get("root_causes") or []:
            counts[str(cause)] += 1
        if not row.get("root_causes"):
            counts["UNKNOWN"] += 1
    return dict(counts)


def build_canonical_result(
    payload: dict[str, Any],
    *,
    data_quality_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Transform raw run output into canonical result.json structure."""
    rows = case_rows(payload)
    dq_ids = data_quality_ids or set()

    full_rows = rows
    main_rows = [r for r in rows if r.get("id") not in dq_ids]
    dq_rows = [r for r in rows if r.get("id") in dq_ids]

    def _summary(subset: list[dict[str, Any]]) -> dict[str, Any]:
        passed = sum(1 for r in subset if r.get("pass"))
        total = len(subset)
        return {
            "passed": passed,
            "total": total,
            "failed": total - passed,
            "accuracy_pct": round(100.0 * passed / total, 1) if total else 0.0,
        }

    exec_share = share_execution_sources(payload)

    return {
        "when": payload.get("when") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "scoring": payload.get("scoring", "gold_value_match_not_sql_tokens"),
        "full": _summary(full_rows),
        "main": _summary(main_rows),
        "data_quality": _summary(dq_rows) if dq_rows else {"passed": 0, "total": 0, "failed": 0, "accuracy_pct": 0.0},
        "by_kind": _aggregate_by(main_rows, "kind"),
        "by_category": _aggregate_by(main_rows, "cat"),
        "by_error_class": _error_class_counts(main_rows),
        "execution_source": exec_share,
        "compiler_source": payload.get("compiler_source") or {},
        "latency": payload.get("latency") or {},
        "cases": rows,
    }


def compare_migration(
    current: dict[str, Any],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    """Compare current run against baseline for fixed/regressed/still_pass/still_fail."""
    cur_cases = {r["id"]: r for r in case_rows(current)}
    base_cases = {r["id"]: r for r in case_rows(baseline)}

    fixed: list[str] = []
    regressed: list[str] = []
    still_pass: list[str] = []
    still_fail: list[str] = []

    for qid, base in base_cases.items():
        cur = cur_cases.get(qid)
        if cur is None:
            continue
        base_ok = bool(base.get("pass"))
        cur_ok = bool(cur.get("pass"))
        if base_ok and cur_ok:
            still_pass.append(qid)
        elif not base_ok and not cur_ok:
            still_fail.append(qid)
        elif not base_ok and cur_ok:
            fixed.append(qid)
        elif base_ok and not cur_ok:
            regressed.append(qid)

    return {
        "fixed": sorted(fixed),
        "regressed": sorted(regressed),
        "still_pass": sorted(still_pass),
        "still_fail": sorted(still_fail),
        "fixed_n": len(fixed),
        "regressed_n": len(regressed),
        "still_pass_n": len(still_pass),
        "still_fail_n": len(still_fail),
    }


def build_manifest(
    *,
    run_id: str,
    label: str = "main485",
    exclude_tracks: list[str] | None = None,
) -> dict[str, Any]:
    settings = load_settings()
    checksums = verify_gold_checksums()
    return {
        "run_id": run_id,
        "label": label,
        "git_commit": _git_commit(),
        "git_dirty": _git_dirty(),
        "testset_hash": checksums.get("docs/평가문항_500.json"),
        "gold_hash": checksums.get("docs/llm2sql_신규_자연어질의_테스트셋_500건_정답표.json"),
        "config_hash": _config_hash(),
        "model": settings.ollama_model,
        "model_digest": settings.ollama_plan_digest or None,
        "embedding_model": settings.ollama_embed_model,
        "embedding_digest": settings.ollama_embed_digest or None,
        "database_snapshot": None,
        "reference_date": settings.reference_date,
        "default_sido": settings.default_sido,
        "evaluation_mode": settings.semantic_plan_mode,
        "main_definition": "exclude data_quality",
        "exclude_tracks": exclude_tracks or ["data_quality"],
        "evaluator_version": "map_ui_gold500_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def render_summary_md(result: dict[str, Any], *, migration: dict[str, Any] | None = None) -> str:
    """Generate summary.md strictly from canonical result.json."""
    main = result.get("main") or {}
    full = result.get("full") or {}
    dq = result.get("data_quality") or {}
    exec_src = result.get("execution_source") or {}

    lines = [
        "# Benchmark Run Summary",
        "",
        f"- When: {result.get('when', 'unknown')}",
        f"- Scoring: {result.get('scoring', 'unknown')}",
        "",
        "## MAIN (exclude data_quality)",
        "",
        f"- **PASS**: {main.get('passed', 0)}/{main.get('total', 0)}",
        f"- **Accuracy**: {main.get('accuracy_pct', 0)}%",
        "",
        "## Full",
        "",
        f"- PASS: {full.get('passed', 0)}/{full.get('total', 0)} ({full.get('accuracy_pct', 0)}%)",
        "",
        "## data_quality track",
        "",
        f"- PASS: {dq.get('passed', 0)}/{dq.get('total', 0)}",
        "",
        "## by_kind",
        "",
        "| kind | n | ok | acc% |",
        "|------|---:|---:|-----:|",
    ]
    for kind, stats in sorted((result.get("by_kind") or {}).items()):
        lines.append(f"| {kind} | {stats['n']} | {stats['ok']} | {stats['acc_pct']} |")

    lines.extend(["", "## execution_source", ""])
    share = exec_src.get("share_pct") or {}
    for src, pct in sorted(share.items(), key=lambda x: -x[1]):
        lines.append(f"- {src}: {pct}%")

    if migration:
        lines.extend([
            "",
            "## Migration",
            "",
            f"- fixed: {migration.get('fixed_n', 0)}",
            f"- regressed: {migration.get('regressed_n', 0)}",
            f"- still_pass: {migration.get('still_pass_n', 0)}",
            f"- still_fail: {migration.get('still_fail_n', 0)}",
        ])

    lines.append("")
    return "\n".join(lines)


def parse_main_from_summary(md_text: str) -> tuple[int, int, float]:
    """Extract MAIN pass/total/accuracy from summary.md for consistency checks."""
    pass_match = re.search(r"\*\*PASS\*\*:\s*(\d+)/(\d+)", md_text)
    acc_match = re.search(r"\*\*Accuracy\*\*:\s*([\d.]+)%", md_text)
    if not pass_match:
        raise ValueError("Could not parse MAIN pass/total from summary.md")
    passed = int(pass_match.group(1))
    total = int(pass_match.group(2))
    accuracy = float(acc_match.group(1)) if acc_match else round(100.0 * passed / total, 1)
    return passed, total, accuracy


def write_benchmark_run(
    payload: dict[str, Any],
    *,
    run_id: str | None = None,
    label: str = "main485",
    data_quality_ids: set[str] | None = None,
    baseline_payload: dict[str, Any] | None = None,
    out_root: Path | None = None,
) -> Path:
    """Write full benchmark run artifact directory."""
    rid = run_id or make_run_id(label=label)
    root = out_root or BENCHMARK_RUNS_DIR
    run_dir = root / rid
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest(run_id=rid, label=label)
    canonical = build_canonical_result(payload, data_quality_ids=data_quality_ids)

    migration = None
    if baseline_payload:
        migration = compare_migration(payload, baseline_payload)
        canonical["fixed"] = migration["fixed"]
        canonical["regressed"] = migration["regressed"]
        canonical["still_pass"] = migration["still_pass"]
        canonical["still_fail"] = migration["still_fail"]

    errors = [r for r in case_rows(canonical) if not r.get("pass")]
    summary_md = render_summary_md(canonical, migration=migration)

    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (run_dir / "result.json").write_text(
        json.dumps(canonical, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (run_dir / "errors.json").write_text(
        json.dumps(errors, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if migration:
        (run_dir / "migration.json").write_text(
            json.dumps(migration, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    (run_dir / "summary.md").write_text(summary_md, encoding="utf-8")

    return run_dir


def verify_run_consistency(run_dir: Path) -> dict[str, Any]:
    """Verify result.json, summary.md, and console-equivalent MAIN values match."""
    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    summary = (run_dir / "summary.md").read_text(encoding="utf-8")

    main = result.get("main") or {}
    md_pass, md_total, md_acc = parse_main_from_summary(summary)

    mismatches: list[str] = []
    if main.get("passed") != md_pass:
        mismatches.append(f"passed: result={main.get('passed')} summary={md_pass}")
    if main.get("total") != md_total:
        mismatches.append(f"total: result={main.get('total')} summary={md_total}")
    if abs(float(main.get("accuracy_pct", 0)) - md_acc) > 0.05:
        mismatches.append(f"accuracy: result={main.get('accuracy_pct')} summary={md_acc}")

    return {
        "consistent": not mismatches,
        "mismatches": mismatches,
        "main": main,
        "summary_main": {"passed": md_pass, "total": md_total, "accuracy_pct": md_acc},
    }
