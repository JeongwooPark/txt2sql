# Phase 00 — Baseline Freeze

## Git
- branch: `semantic-architecture-v2`
- base commit: `a9937fd` (release/0.3.1-map-ui-newset500 tip)

## Unit (Gate A)
- 349 passed, 1 failed
- known failure: `test_violate_negation_is_not_y` (expects `NOT`/`<>`, actual SQL uses `IS DISTINCT FROM` which is semantically correct)
- frozen as baseline; not patched in Phase 0

## map-ui-newset500
- source: `tests/map_ui_gold500/results/mapui_newset500_round3_20260826_120607.json`
- **244 / 500 = 48.8%**
- avg latency ~1337ms, p50 ~1021ms, p95 ~3941ms
- weakest: scalar 12.9%, cat5 13.3%, group 33.3%

## Gold immutability
- SHA256 frozen in `txt2sql/evaluation/gold_checksum.py`
- `docs/평가문항_500.json`
- `docs/llm2sql_신규_자연어질의_테스트셋_500건_정답표.json`
- evaluation aborts on checksum drift (`GoldDatasetChangedError`)

## Notes
- Full newset500 re-run deferred to final gold compare; Round3 on same commit used as reproducible baseline.
- `eval_q500_gold.py` artifact copied when present under `q500_gold_eval.json`.
