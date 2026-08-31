"""Tests for benchmark run consistency (Phase 1 gate)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from txt2sql.evaluation.benchmark_run import (
    build_canonical_result,
    parse_main_from_summary,
    render_summary_md,
    verify_run_consistency,
    write_benchmark_run,
)


@pytest.fixture
def sample_payload() -> dict:
    return {
        "when": "2026-08-28 00:00:00",
        "passed": 2,
        "total": 3,
        "failed": 1,
        "accuracy_pct": 66.7,
        "rows": [
            {"id": "Q001", "kind": "count", "cat": "test", "pass": True, "q": "test1"},
            {"id": "Q002", "kind": "count", "cat": "test", "pass": True, "q": "test2"},
            {"id": "Q037", "kind": "count", "cat": "test", "pass": False, "q": "test3", "reason": "fail"},
        ],
    }


def test_build_canonical_result_main_excludes_data_quality(sample_payload: dict) -> None:
    canonical = build_canonical_result(sample_payload, data_quality_ids={"Q037"})
    assert canonical["main"]["passed"] == 2
    assert canonical["main"]["total"] == 2
    assert canonical["data_quality"]["total"] == 1


def test_summary_md_matches_result_json(sample_payload: dict) -> None:
    canonical = build_canonical_result(sample_payload, data_quality_ids={"Q037"})
    md = render_summary_md(canonical)
    passed, total, acc = parse_main_from_summary(md)
    assert passed == canonical["main"]["passed"]
    assert total == canonical["main"]["total"]
    assert abs(acc - canonical["main"]["accuracy_pct"]) < 0.1


def test_write_benchmark_run_consistency(tmp_path: Path, sample_payload: dict) -> None:
    run_dir = write_benchmark_run(
        sample_payload,
        run_id="test_run",
        data_quality_ids={"Q037"},
        out_root=tmp_path,
    )
    check = verify_run_consistency(run_dir)
    assert check["consistent"], check["mismatches"]

    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    summary = (run_dir / "summary.md").read_text(encoding="utf-8")
    md_pass, md_total, _ = parse_main_from_summary(summary)
    assert result["main"]["passed"] == md_pass
    assert result["main"]["total"] == md_total
