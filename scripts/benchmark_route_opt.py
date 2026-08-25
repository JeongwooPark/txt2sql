"""규칙 SQL early 디스패치: baseline(다중 try_route) vs optimized(1회+재사용).

판정:
  - early/deferred intent·SQL 일치율 100%
  - optimized 파이프라인 라우팅 지연 <= baseline * 1.05
  → optimized 반영, 아니면 baseline 유지 권고

측정 범위: early 디스패치 + (early 미적중 시) 후단 try_route.
baseline은 후단에서 try_route를 다시 호출하고, optimized는 deferred 재사용.
"""

from __future__ import annotations

import argparse
import statistics
import time

from txt2sql.intent_router import try_route
from txt2sql.route_dispatch import match_route_baseline, match_route_optimized

CASES: list[str] = [
    # building name (looks_like True)
    "포르투나 건물 정보",
    "구서동 포르투나 아파트 주소는?",
    "장전동 센트럴파크 아파트 높이는?",
    # rank — baseline은 try_route 후 _route_building_rank 중복
    "부산에서 가장 높은 건물",
    "해운대구에서 가장 큰 건물 3개",
    "금정구 가장 높은 건물",
    "동래구에서 연면적이 제일 큰 건물",
    # industrial early
    "부산 산업단지 몇 개야?",
    "사상구 산업단지 개수",
    "부산 산업단지 이름은?",
    "사상구 산업단지 안 건물 몇 채?",
    # deferred — early 아님, 후단 try_route 필요
    "해운대구 건물 몇 채야?",
    "수영구에서 높이 50미터 넘는 건물 몇 개?",
    "금정구 공동주택 몇 동이야?",
    "구서동 아파트 수",
    # no SQL route
    "기능 알려줘",
    "A4 컬럼 의미가 뭐야?",
    "오늘 날씨 어때?",
]


def _sig(early, deferred) -> tuple:
    return (
        early.intent if early else None,
        early.sql if early else None,
        deferred.intent if deferred else None,
        deferred.sql if deferred else None,
    )


def _run_baseline(q: str) -> tuple[object, object, int]:
    """early 매치 + early 없을 때 후단 try_route 재호출(파이프라인 재현)."""
    m = match_route_baseline(q)
    calls = m.try_route_calls
    early, deferred = m.early, m.deferred
    if early is None:
        calls += 1
        deferred = try_route(q)
    return early, deferred, calls


def _run_optimized(q: str) -> tuple[object, object, int]:
    m = match_route_optimized(q)
    # early 없으면 deferred 재사용 → 추가 try_route 없음
    return m.early, m.deferred, m.try_route_calls


def _bench(fn, q: str, repeats: int) -> tuple[tuple, float, int]:
    fn(q)  # warmup
    times: list[float] = []
    last = None
    for _ in range(repeats):
        t0 = time.perf_counter()
        last = fn(q)
        times.append((time.perf_counter() - t0) * 1000)
    early, deferred, calls = last
    return _sig(early, deferred), statistics.mean(times), calls


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=40)
    args = parser.parse_args()

    mismatches: list[dict] = []
    base_ms: list[float] = []
    opt_ms: list[float] = []
    base_calls: list[int] = []
    opt_calls: list[int] = []

    print(f"cases={len(CASES)} repeats={args.repeats}\n")
    for q in CASES:
        bs, bt, bc = _bench(_run_baseline, q, args.repeats)
        os_, ot, oc = _bench(_run_optimized, q, args.repeats)
        base_ms.append(bt)
        opt_ms.append(ot)
        base_calls.append(bc)
        opt_calls.append(oc)
        ok = bs == os_
        mark = "OK" if ok else "DIFF"
        print(
            f"[{mark}] {bt:6.3f}→{ot:6.3f} ms  "
            f"calls {bc}→{oc}  | {q}"
        )
        if not ok:
            mismatches.append(
                {
                    "q": q,
                    "baseline": {"early": bs[0], "deferred": bs[2]},
                    "optimized": {"early": os_[0], "deferred": os_[2]},
                }
            )
            print(f"       baseline early={bs[0]} deferred={bs[2]}")
            print(f"       optimized early={os_[0]} deferred={os_[2]}")

    agree = 1.0 - (len(mismatches) / len(CASES))
    mean_b = statistics.mean(base_ms)
    mean_o = statistics.mean(opt_ms)
    speedup = mean_b / mean_o if mean_o > 0 else float("inf")
    mean_calls_b = statistics.mean(base_calls)
    mean_calls_o = statistics.mean(opt_calls)

    print("\n=== summary ===")
    print(f"route agreement: {agree:.1%} ({len(CASES) - len(mismatches)}/{len(CASES)})")
    print(f"avg latency: baseline {mean_b:.3f} ms → optimized {mean_o:.3f} ms ({speedup:.2f}x)")
    print(f"avg try_route calls: {mean_calls_b:.2f} → {mean_calls_o:.2f}")

    adopt = agree >= 1.0 and mean_o <= mean_b * 1.05
    decision = "ADOPT optimized" if adopt else "KEEP baseline"
    print(f"\nDECISION: {decision}")
    if mismatches:
        print("mismatches:")
        for m in mismatches:
            print(f"  - {m}")
    if adopt:
        print("→ Settings.route_dispatch_mode='optimized' 유지")
    else:
        print("→ ROUTE_DISPATCH_MODE=baseline 권고")


if __name__ == "__main__":
    main()
