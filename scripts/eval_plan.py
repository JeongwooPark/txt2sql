"""Plan 의미 정확도 evaluator.

SQL 토큰 존재만으로 정답 처리하지 않는다.
`--source heuristic` 은 DB 없이 현재 휴리스틱 Plan을 gold와 비교한다.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from llm2sql.evaluation.harness import evaluate_case
from llm2sql.evaluation.jsonl import load_jsonl
from llm2sql.evaluation.schema import EvalSummary, GoldPlanCase
from llm2sql.semantic_plan.generator import try_heuristic_plan
from llm2sql.semantic_plan.generator import extract_plan_hints


def _load_predictions(path: Path) -> dict[str, dict]:
    mapping: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        mapping[row["id"]] = row
    return mapping


def _predict(case: GoldPlanCase, predictions: dict[str, dict] | None, source: str):
    if predictions and case.id in predictions:
        row = predictions[case.id]
        return row.get("plan"), row.get("route"), row.get("clarify")
    if source == "heuristic":
        hints = extract_plan_hints(case.question)
        plan = try_heuristic_plan(case.question, hints)
        if plan is None:
            return None, None, None
        return plan.model_dump(mode="json"), "semantic_plan_heuristic", plan.requires_clarification
    return None, None, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate predicted Semantic Plans")
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument("--pred", type=Path, default=None)
    parser.add_argument("--source", choices=("pred", "heuristic"), default="pred")
    parser.add_argument("--verified-only", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    cases = load_jsonl(args.gold)
    if args.verified_only:
        cases = [c for c in cases if c.status == "verified"]
    predictions = _load_predictions(args.pred) if args.pred else None
    source = "heuristic" if args.source == "heuristic" else "pred"

    items = []
    errors: Counter[str] = Counter()
    for case in cases:
        plan, route, clarify = _predict(case, predictions, source)
        result = evaluate_case(
            case,
            predicted_plan=plan,
            predicted_route=route,
            predicted_clarify=clarify,
        )
        items.append(result.model_dump(by_alias=True))
        errors.update(result.error_codes)

    verified = [c for c in cases if c.status == "verified"]
    passed = sum(1 for item in items if item["pass"])
    summary = EvalSummary(
        name="eval_plan",
        mode=source,
        n=len(cases),
        n_verified=len(verified),
        passed=passed,
        failed=len(cases) - passed,
        error_counts=dict(errors),
        metrics={
            "plan_exact_match": (
                passed / len(cases) if cases else 0.0
            )
        },
    )
    payload = {"summary": summary.model_dump(), "items": items}
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0 if summary.failed == 0 or not args.verified_only else 1


if __name__ == "__main__":
    raise SystemExit(main())
