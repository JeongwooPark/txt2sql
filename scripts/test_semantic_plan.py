"""Semantic Query Plan 단위 테스트. pytest 없이 실행 가능."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run_module(mod_name: str) -> tuple[int, list[str]]:
    mod = importlib.import_module(mod_name)
    failed: list[str] = []
    passed = 0
    for name in sorted(dir(mod)):
        if not name.startswith("test_") or not callable(getattr(mod, name)):
            continue
        try:
            getattr(mod, name)()
        except Exception as exc:
            failed.append(f"{mod_name}.{name}: {type(exc).__name__}: {exc}")
            print(f"[FAIL] {mod_name}.{name}: {exc}")
        else:
            passed += 1
            print(f"[OK]   {mod_name}.{name}")
    return passed, failed


def main() -> int:
    modules = (
        "tests.semantic_plan.test_catalog",
        "tests.semantic_plan.test_normalizer",
        "tests.semantic_plan.test_validator",
        "tests.semantic_plan.test_compiler",
        "tests.semantic_plan.test_generator",
    )
    passed = 0
    failed: list[str] = []
    for name in modules:
        p, f = _run_module(name)
        passed += p
        failed.extend(f)
    print(f"\npassed={passed} failed={len(failed)}")
    for item in failed:
        print(" -", item)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
