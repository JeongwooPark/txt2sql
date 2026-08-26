# Phase 01 — Canonical QueryIR

## Changes
- Added `txt2sql/query_ir/` with models, adapters, normalize, completeness
- Adapters: QueryContract↔QueryIR, SemanticQueryPlan↔QueryIR
- Physical/SQL/PostGIS tokens rejected in QueryIR
- Runtime execution path unchanged (adapter-ready)

## Tests
- `tests/query_ir/` 15 passed
- Full suite parity with baseline (1 known pre-existing failure unrelated)

## Gate
- Unit: QueryIR tests green
- Gold checksum unchanged
- No pipeline behavior change
