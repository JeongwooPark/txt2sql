# SQP v1.1 migration

기본 운영 모드는 `SEMANTIC_PLAN_MODE=hybrid`다. 라우터 미적중 질의는 검증된 Semantic Query Plan SQL을 실행하고, 실패·clarify·품질 미달이면 RAG로 내려간다.

## 적용

1. `feat/sqp-v11-roadmap`를 배포 대상 브랜치에서 검토한다.
2. `.env`에 아래를 둔다. 관측만 하려면 `shadow`로 내린다.

```
SEMANTIC_PLAN_MODE=hybrid
SEMANTIC_PLAN_VERSION=1.1
SEMANTIC_PLAN_MIN_CONTRACT_COVERAGE=1.0
SEMANTIC_PLAN_MIN_SLOT_CONFIDENCE=0.85
```

3. 공식 벤치는 `OLLAMA_PLAN_MODEL`을 digest pin으로 두고 `:latest`를 쓰지 않는다.
4. 기존 `version: "1.0"` Plan JSON은 `migrate_plan_v11()`이 AND tree로 옮긴다. Router 테스트는 그대로 통과해야 한다.

## 확인

- `uv run pytest tests/semantic_plan tests/query_understanding tests/evaluation tests/semantic_catalog`
- 기본값이 `hybrid`인지 `tests/semantic_plan/test_pipeline_shadow.py`의 `test_default_mode_is_hybrid`로 확인한다.
