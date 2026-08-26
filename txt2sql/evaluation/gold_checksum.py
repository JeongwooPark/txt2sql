"""Gold dataset immutability guard for semantic architecture v2."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Frozen at Phase 0 baseline (semantic-architecture-v2).
FROZEN_GOLD_CHECKSUMS: dict[str, str] = {
    "docs/평가문항_500.json": "73786531eac4188bdaa328c2674e9db1c01fb26f5d7afaf612d1fa0bdad03788",
    "docs/llm2sql_신규_자연어질의_테스트셋_500건_정답표.json": (
        "6f01c72296ca1d4dc54da30cfbf6288717c1ce27d96952e960d4922ae3a54b08"
    ),
}


class GoldDatasetChangedError(RuntimeError):
    """Raised when a frozen gold dataset file hash no longer matches."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_gold_checksums(
    *,
    root: Path | None = None,
    expected: dict[str, str] | None = None,
) -> dict[str, str]:
    """Verify frozen gold files. Abort evaluation if any checksum drifts."""
    base = root or ROOT
    want = expected or FROZEN_GOLD_CHECKSUMS
    actual: dict[str, str] = {}
    mismatches: list[str] = []
    for rel, expected_hash in want.items():
        path = base / rel
        if not path.is_file():
            mismatches.append(f"missing:{rel}")
            continue
        got = sha256_file(path)
        actual[rel] = got
        if got != expected_hash:
            mismatches.append(f"changed:{rel}:expected={expected_hash}:got={got}")
    if mismatches:
        raise GoldDatasetChangedError(
            "Gold dataset changed during semantic architecture v2; evaluation aborted. "
            + "; ".join(mismatches)
        )
    return actual


def dump_checksum_report(out_path: Path, *, root: Path | None = None) -> dict[str, str]:
    actual = verify_gold_checksums(root=root)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(actual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return actual
