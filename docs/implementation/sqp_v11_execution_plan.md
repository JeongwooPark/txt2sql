# SQP v1.1 실행 계획 (저장소 보정본)

기준 커밋: `d6fc4af3e7c823c402b08a62b5a4ddfb5915abfe` (llm2sql 0.2.2)
작업 브랜치: `feat/sqp-v11-roadmap`
작업트리: `D:\py_workspace\llm2sql-sqp-v11` (원 저장소 untracked 스크립트 보존)

## 재현 명령

```bash
uv run python --version
uv run pytest tests/semantic_plan -q
git diff --check
```

DB·Ollama가 필요한 통합 테스트는 프로젝트 `.env`의 `DATABASE_URL` / `OLLAMA_HOST`를 사용한다. 비밀정보는 커밋하지 않는다.

## 코드 경로 (실제)

| 역할 | 경로 |
|---|---|
| 오케스트레이션 | `llm2sql/pipeline.py` |
| SQP 모델 | `llm2sql/semantic_plan/models.py` |
| 휴리스틱/LLM Plan | `llm2sql/semantic_plan/generator.py` |
| compiler | `llm2sql/semantic_plan/compiler.py` |
| 설정 | `llm2sql/config.py` (`SEMANTIC_PLAN_MODE` 기본 `hybrid`, FIX-4) |
| 단위 테스트 | `tests/semantic_plan/` 등 |

## 현재 상태 (FIX-4)

- `SEMANTIC_PLAN_MODE` 기본값 `hybrid`. 태그 `sqp-v11-ready`. 제품 버전 **0.2.3**
- Phase 1 verified gold 30/30, Phase 2 holdout n=17 Recall 1.0, Phase 4 live spatial 6/6
- QLoRA는 `NOT_ELIGIBLE` (STEP-26)

## 당시 불변조건 (실행 중)

- Router 제거 금지. `hybrid` 기본값 승격은 gate 통과 후에만 (FIX-4에서 통과).
- 신규 경로는 STEP-09까지 `shadow`를 기본으로 두었다.
- 실행 성공률을 의미 정확도로 사용하지 않는다.
- 한 스텝만 IN_PROGRESS. 실패 시 다음 스텝으로 진행하지 않는다.
