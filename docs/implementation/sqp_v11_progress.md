# SQP v1.1 진행기록

| STEP | 상태 | 변경 | 테스트 | 지표 | Git | 차단 | 다음 |
|---|---|---|---|---|---|---|---|
| 00 | DONE | 실행 계획·진행기록·baseline JSON·gitignore | `uv run pytest tests/semantic_plan -q` 37 passed | unit 37/0/0 | `chore(plan): [STEP-00] record sqp v1.1 baseline and execution context` | 없음 | STEP-01 |
| 01 | DONE | evaluation 패키지, eval CLI, candidate jsonl | `uv run pytest tests/evaluation tests/semantic_plan -q` 47 passed | unit 47/0/0 | `test(benchmark): [STEP-01] add semantic accuracy evaluation harness` | nl2sql live는 DB 필요 시 ENV_BLOCKED 경로 존재 | STEP-02 |
| 02 | DONE | verified gold 30 + heuristic baseline 실패 기록 | `uv run pytest tests/evaluation tests/semantic_plan -q` 50 passed | heuristic 0/30, 단위 50/0/0 | `test(semantic): [STEP-02] freeze known Korean semantic error cases` | 없음 | STEP-03 |
| 03 | DONE | query_understanding contract/span | 56 passed | - | `feat(contract): [STEP-03] parse Korean semantic contract and spans` | 없음 | STEP-04 |
| 04 | DONE | heuristic coverage gate, 합계/NOT/between/ASC | 60 passed | Router 회귀 0 | `fix(plan): [STEP-04] gate heuristic plans on full semantic coverage` | 없음 | STEP-05 |
| 05 | DONE | Predicate AST, v1→v1.1 migration | 63 passed | v1 회귀 0 | `feat(plan): [STEP-05] add semantic plan v1.1 predicate AST` | 없음 | STEP-06 |

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
