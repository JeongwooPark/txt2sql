# SQP v1.1 진행기록

| STEP | 상태 | 변경 | 테스트 | 지표 | Git | 차단 | 다음 |
|---|---|---|---|---|---|---|---|
| 00 | DONE | 실행 계획·진행기록·baseline JSON·gitignore | `uv run pytest tests/semantic_plan -q` 37 passed | unit 37/0/0 | `chore(plan): [STEP-00] record sqp v1.1 baseline and execution context` | 없음 | STEP-01 |
| 01 | DONE | evaluation 패키지, eval CLI, candidate jsonl | `uv run pytest tests/evaluation tests/semantic_plan -q` 47 passed | unit 47/0/0 | `test(benchmark): [STEP-01] add semantic accuracy evaluation harness` | nl2sql live는 DB 필요 시 ENV_BLOCKED 경로 존재 | STEP-02 |
| 02 | DONE | verified gold 30 + heuristic baseline 실패 기록 | `uv run pytest tests/evaluation tests/semantic_plan -q` 50 passed | heuristic 0/30, 단위 50/0/0 | `test(semantic): [STEP-02] freeze known Korean semantic error cases` | 없음 | STEP-03 |
| 03 | DONE | query_understanding contract/span | 56 passed | - | `feat(contract): [STEP-03] parse Korean semantic contract and spans` | 없음 | STEP-04 |
| 04 | DONE | heuristic coverage gate, 합계/NOT/between/ASC | 60 passed | Router 회귀 0 | `fix(plan): [STEP-04] gate heuristic plans on full semantic coverage` | 없음 | STEP-05 |
| 05 | DONE | Predicate AST, v1→v1.1 migration | 63 passed | v1 회귀 0 | `feat(plan): [STEP-05] add semantic plan v1.1 predicate AST` | 없음 | STEP-06 |
| 06 | DONE | Ollama JSON schema format, parse→v1.1 | 66 passed | - | `feat(plan): [STEP-06] enforce structured plan output and normalization` | Ollama live는 mock과 분리 | STEP-07 |
| 07 | DONE | predicate 재귀 compiler, field compare, HAVING | 69 passed | injection 차단 | `feat(compiler): [STEP-07] compile predicate AST deterministically` | 없음 | STEP-08 |
| 08 | DONE | contract verifier, slot confidence | 72 passed | slot 미달 시 실행 금지 | `feat(verifier): [STEP-08] verify contract coverage and slot confidence` | 없음 | STEP-09 |
| 09 | DONE | shadow 기본값, config flags, pipeline trace | 75 passed | gold exact 2/30, gate NOT_PASSED, shadow 유지 | `feat(pipeline): [STEP-09] integrate sqp v1.1 in shadow mode` | Phase1 gold gate 미달, 태그 보류 | STEP-10 |
| 10-14 | DONE | semantic_catalog, linking, join edges, eval_schema_linking | 77 passed | holdout Recall gate NOT_PASSED (목표 미완화) | `feat(catalog): [STEP-10] externalize semantic catalog and source bindings` | labeled holdout 부재 | STEP-15 |
| 15-18 | DONE | Plan-SQL sqlglot 동등성, result shape, hard-query selector | 81 passed | silent-error fixture 탐지 4/4, Phase3 unit gate PASSED | `feat(sql-verifier): [STEP-15] verify plan and SQL AST equivalence` | live gold 미달로 hybrid 금지 | STEP-19 |
| 19-22 | DONE | PostGIS policy, canonical join, Plan event log | 87 passed | unit spatial+4-turn PASSED | `feat(spatial): [STEP-19] map spatial relations by explicit policy` | live spatial accuracy 미측정, hybrid 금지 | STEP-23 |

## STEP-00

- 목표: 재현 기준 고정, 기능 브랜치, baseline 테스트 기록
- 기준 HEAD: `d6fc4af3e7c823c402b08a62b5a4ddfb5915abfe` == `origin/master`
- Python: 3.13.11 (`uv`, Windows-11-10.0.26200)
- Unit test: 37 passed in 4.62s (worktree)
- Ollama: reachable `http://localhost:11434`
  - `qwen3:latest` digest `500a1f067a9f7826…` Q4_K_M 8.2B
  - `mxbai-embed-large:latest` digest `468836162de7f81e…` F16
  - 공식 benchmark는 `latest` tag를 그대로 쓰지 않고 digest를 기록한다 (STEP-23)
- DB: PostgreSQL 16.11, PostGIS 3.5.3, schema `public`
  - URL hash `48864f80687e` (비밀정보 미저장)
  - catalog tables present (name snapshot only)
- 사용자 untracked 스크립트는 원 작업트리에 보존, 본 브랜치에 포함하지 않음

## STEP-15~18

- 목표: Plan predicate tree ↔ SQL WHERE 동등성, result shape, hard-query 후보 선택
- 구현: `sql_equivalence.py`, `result_shape.py`, `selector.py`, runner에서 compile 후 검증
- 0건 결과는 list에서 정상, count shape 불일치는 Q03. 조건 완화 없음
- simple Router 질의는 `should_enumerate_candidates`가 False
- `uv run pytest tests/semantic_plan tests/semantic_catalog tests/query_understanding tests/evaluation -q` 81 passed
- Phase 3 unit fixture 탐지율 1.0 → 태그 `sqp-v11-phase-3`
- hybrid 승격은 STEP-24에서만 판단

## STEP-19~22

- 목표: within을 ST_Intersects로 일괄 번역하지 않음, canonical join edge, BasePlan+event follow-up
- `spatial_policy.py`: within/covered_by→ST_CoveredBy, intersects, touches, buffer, nearest, overlap_ratio
- Plan.joins는 catalog edge_id만. POI 모호하면 clarify
- followup event: add/replace/remove/negate_filter, change_scope/order/limit, undo_last, reset_to_base. PlanDelta는 migration 유지
- 87 passed. 태그 `sqp-v11-phase-4`
- hybrid 승격은 STEP-24에서만 판단
