# Semantic Architecture v2 Final vs Round3

## Verdict
- Round3: 244/500 (48.8%)
- v2 (Phases 0-11): 244/500 (48.8%)
- Delta: +0 (+0.0 pct points)
- Gold checksum: verified unchanged

## Migration
- fixed: 0
- regressed: 0
- still_fail: 500
- still_pass: 0

## Latency
- Round3: avg=1337 p50=1021 p95=3941
- v2: avg=1345 p50=1026 p95=4211

## by_kind (v2)
{
  "count": {
    "n": 180,
    "ok": 97,
    "acc_pct": 53.9
  },
  "list": {
    "n": 128,
    "ok": 84,
    "acc_pct": 65.6
  },
  "group": {
    "n": 93,
    "ok": 31,
    "acc_pct": 33.3
  },
  "scalar": {
    "n": 62,
    "ok": 8,
    "acc_pct": 12.9
  },
  "meta": {
    "n": 19,
    "ok": 16,
    "acc_pct": 84.2
  },
  "compare": {
    "n": 18,
    "ok": 8,
    "acc_pct": 44.4
  }
}

## Architecture
QueryIR + Semantic Catalog binding + Logical/Physical planner + compiler facade + RAG fallback snapshots + interaction deltas + stage eval landed.
Accuracy parity with Round3 (no regression). Long-tail operator accuracy uplift is next on the planner execution path.
