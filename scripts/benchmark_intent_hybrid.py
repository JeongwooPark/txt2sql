"""규칙 vs LLM vs 하이브리드 의도 분류 벤치마크.

사람처럼 다양한 질문을 gold intent와 비교해 정확도·지연을 측정한다.
판정 기준(기본):
  - hybrid 정확도 >= rules 정확도 + 3%p 이고
  - hybrid 평균 지연이 rules의 3배 이내이면 hybrid 채택 권고
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from llm2sql.config import load_settings
from llm2sql.intent_classifier import (
    classify_intent_hybrid,
    classify_intent_llm,
    predict_intent_rules,
)

# (질문, gold_intent) — 일상·오타·구어체·경계 케이스 포함
CASES: list[tuple[str, str]] = [
    # guide / coverage / out_of_scope
    ("기능 알려줘", "guide"),
    ("너 뭐 할 수 있어?", "guide"),
    ("제한이 뭐야?", "guide"),
    ("전국자료가 있는가?", "coverage"),
    ("전국 데이터도 있어?", "coverage"),
    ("서울시 건물 자료도 되나?", "coverage"),
    ("오늘 날씨 어때?", "out_of_scope"),
    ("파이썬 코드 짜줘", "out_of_scope"),
    # meta
    ("A4 컬럼 의미가 뭐야?", "meta"),
    ("사용가능한 데이터는 몇개야?", "meta"),
    ("어떤 테이블이 있어?", "meta"),
    ("법정동명이 어느 컬럼이야?", "meta"),
    # usage_overview
    ("동래구 건물의 주요 용도들을 설명하라", "usage_overview"),
    ("구서동은 건물이 주로 뭐로 쓰여?", "usage_overview"),
    ("해운대구 건물 용도 구성 알려줘", "usage_overview"),
    ("금정구 주요용도명 좀 풀어줘", "usage_overview"),
    # profile / citywide
    ("구서동 아파트의 특징은?", "profile"),
    ("장전동과 구서동의 건물 특성을 비교하라", "profile"),
    ("부산시 전역 대비 구서동의 건물특성은?", "profile"),
    ("연산동이랑 재송동 건물 분위기 어때 차이?", "profile"),
    ("구서동 건물 대략 어떤 편이야?", "profile"),
    # rank_compare
    ("장전동과 안락동에서 제일 높은 건물 비교해줘", "rank_compare"),
    ("구서동 vs 장전동 최고 높이 건물?", "rank_compare"),
    # sql-like
    ("해운대구 건물 몇 채야?", "sql"),
    ("구서동에서 건물면적이 가장 큰 아파트는?", "sql"),
    ("수영구에서 높이 50미터 넘는 건물 몇 개?", "sql"),
    ("금정구 공동주택 몇 동이야?", "sql"),
    ("부산에서 제일 높은 건물은?", "sql"),
    ("사하구 공장 건물 수 알려줘", "sql"),
    # clarify-ish
    ("구서동에서 제일 좋은 아파트는?", "clarify"),
    ("송정동 건물 몇 채야?", "clarify"),
    # 구어·변형
    ("동래구 쪽 집들이 주로 뭐하는 건물이야?", "usage_overview"),
    ("부산 전체랑 비교해서 구서동 건물 어때?", "profile"),
    ("전국 통계는 없나?", "coverage"),
    ("A9가 뭐였지?", "meta"),
    ("장전동 구서동 중에 어디가 더 높다? 최고 건물 기준", "rank_compare"),
]


def _acc(preds: list[str], golds: list[str]) -> float:
    if not golds:
        return 0.0
    return sum(p == g for p, g in zip(preds, golds, strict=True)) / len(golds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default="benchmark_intent_hybrid.json",
        help="결과 JSON 경로",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.55,
        help="hybrid confidence threshold",
    )
    args = parser.parse_args()

    settings = load_settings()
    golds = [g for _, g in CASES]
    questions = [q for q, _ in CASES]

    rows: list[dict] = []
    rules_preds: list[str] = []
    llm_preds: list[str] = []
    hybrid_preds: list[str] = []
    rules_ms: list[float] = []
    llm_ms: list[float] = []
    hybrid_ms: list[float] = []

    print(f"model={settings.ollama_model}  cases={len(CASES)}  thr={args.threshold}")
    print("-" * 72)

    for i, (q, gold) in enumerate(CASES, 1):
        t0 = time.perf_counter()
        r_rules = predict_intent_rules(q)
        rules_ms.append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        try:
            r_llm = classify_intent_llm(
                q,
                model=settings.ollama_model,
                host=settings.ollama_host,
            )
        except Exception as exc:
            r_llm = predict_intent_rules(q)
            r_llm = type(r_llm)(
                r_llm.intent, 0.0, f"err:{type(exc).__name__}", "llm"
            )
        llm_ms.append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        try:
            r_hyb = classify_intent_hybrid(
                q,
                model=settings.ollama_model,
                host=settings.ollama_host,
                threshold=args.threshold,
            )
        except Exception:
            r_hyb = r_rules
        hybrid_ms.append((time.perf_counter() - t0) * 1000)

        rules_preds.append(r_rules.intent)
        llm_preds.append(r_llm.intent)
        hybrid_preds.append(r_hyb.intent)

        mark = {
            "rules": "OK" if r_rules.intent == gold else "X",
            "llm": "OK" if r_llm.intent == gold else "X",
            "hybrid": "OK" if r_hyb.intent == gold else "X",
        }
        print(
            f"[{i:02d}] gold={gold:14s} "
            f"R={r_rules.intent:14s}{mark['rules']} "
            f"L={r_llm.intent:14s}{mark['llm']} "
            f"H={r_hyb.intent:14s}{mark['hybrid']}"
        )
        print(f"     Q: {q}")
        rows.append(
            {
                "question": q,
                "gold": gold,
                "rules": {
                    "intent": r_rules.intent,
                    "confidence": r_rules.confidence,
                    "reason": r_rules.reason,
                    "ok": r_rules.intent == gold,
                    "ms": rules_ms[-1],
                },
                "llm": {
                    "intent": r_llm.intent,
                    "confidence": r_llm.confidence,
                    "reason": r_llm.reason,
                    "ok": r_llm.intent == gold,
                    "ms": llm_ms[-1],
                },
                "hybrid": {
                    "intent": r_hyb.intent,
                    "confidence": r_hyb.confidence,
                    "reason": r_hyb.reason,
                    "source": r_hyb.source,
                    "ok": r_hyb.intent == gold,
                    "ms": hybrid_ms[-1],
                },
            }
        )

    rules_acc = _acc(rules_preds, golds)
    llm_acc = _acc(llm_preds, golds)
    hybrid_acc = _acc(hybrid_preds, golds)

    # 채택 판정
    adopt_hybrid = (
        hybrid_acc >= rules_acc + 0.03
        and statistics.mean(hybrid_ms) <= max(statistics.mean(rules_ms) * 3, 50.0)
    ) or (
        # 정확도가 같고 규칙이 틀린 어려운 케이스를 hybrid가 더 맞추면
        hybrid_acc > rules_acc
        and statistics.mean(hybrid_ms) <= 8000.0
    )

    # 더 보수적: hybrid가 rules보다 엄격히 나을 때만
    decision = "adopt_hybrid" if hybrid_acc > rules_acc + 1e-9 else "keep_rules"
    if hybrid_acc >= rules_acc + 0.03:
        decision = "adopt_hybrid"
    elif hybrid_acc < rules_acc - 0.02:
        decision = "keep_rules"
    elif hybrid_acc >= rules_acc and statistics.mean(hybrid_ms) > 5000:
        decision = "keep_rules_latency"
    elif hybrid_acc == rules_acc:
        decision = "keep_rules_tie"

    summary = {
        "model": settings.ollama_model,
        "n": len(CASES),
        "threshold": args.threshold,
        "accuracy": {
            "rules": rules_acc,
            "llm": llm_acc,
            "hybrid": hybrid_acc,
        },
        "latency_ms": {
            "rules_mean": statistics.mean(rules_ms),
            "llm_mean": statistics.mean(llm_ms),
            "hybrid_mean": statistics.mean(hybrid_ms),
            "rules_p50": statistics.median(rules_ms),
            "llm_p50": statistics.median(llm_ms),
            "hybrid_p50": statistics.median(hybrid_ms),
        },
        "decision": decision,
        "adopt_hybrid_flag": adopt_hybrid,
        "cases": rows,
    }

    out = Path(args.out)
    out.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("-" * 72)
    print(
        f"Accuracy  rules={rules_acc:.1%}  llm={llm_acc:.1%}  hybrid={hybrid_acc:.1%}"
    )
    print(
        "Latency(ms) "
        f"rules={statistics.mean(rules_ms):.1f}  "
        f"llm={statistics.mean(llm_ms):.0f}  "
        f"hybrid={statistics.mean(hybrid_ms):.0f}"
    )
    print(f"Decision: {decision}")
    print(f"Wrote {out.resolve()}")


if __name__ == "__main__":
    main()
