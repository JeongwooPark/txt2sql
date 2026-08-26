"""Gold dataset checksum immutability tests."""

from __future__ import annotations

import pytest

from txt2sql.evaluation.gold_checksum import (
    FROZEN_GOLD_CHECKSUMS,
    GoldDatasetChangedError,
    sha256_file,
    verify_gold_checksums,
)


def test_frozen_gold_checksums_match_repo_files() -> None:
    actual = verify_gold_checksums()
    assert actual == FROZEN_GOLD_CHECKSUMS


def test_gold_checksum_detects_drift(tmp_path) -> None:
    gold = tmp_path / "docs"
    gold.mkdir()
    fake = gold / "평가문항_500.json"
    fake.write_text('{"tampered": true}', encoding="utf-8")
    other = gold / "llm2sql_신규_자연어질의_테스트셋_500건_정답표.json"
    other.write_text('{"tampered": true}', encoding="utf-8")
    expected = {
        "docs/평가문항_500.json": "0" * 64,
        "docs/llm2sql_신규_자연어질의_테스트셋_500건_정답표.json": "1" * 64,
    }
    with pytest.raises(GoldDatasetChangedError):
        verify_gold_checksums(root=tmp_path, expected=expected)


def test_sha256_stable_for_existing_gold() -> None:
    from pathlib import Path

    from txt2sql.evaluation.gold_checksum import ROOT

    for rel, digest in FROZEN_GOLD_CHECKSUMS.items():
        assert sha256_file(ROOT / rel) == digest
