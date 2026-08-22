# SQP v1.1 migration

기본 운영 모드는 `SEMANTIC_PLAN_MODE=shadow`다. 사용자 답변 SQL은 기존 Router/RAG 경로를 쓰고, SQP SQL은 추적만 한다.

## 적용

1. `feat/sqp-v11-roadmap`를 배포 대상 브랜치에서 검토한다.
2. `.env`에 아래를 둔다. `hybrid`로 올리지 않는다.

```
SEMANTIC_PLAN_MODE=shadow
SEMANTIC_PLAN_VERSION=1.1
SEMANTIC_PLAN_MIN_CONTRACT_COVERAGE=1.0
SEMANTIC_PLAN_MIN_SLOT_CONFIDENCE=0.85
```

3. 공식 벤치는 `OLLAMA_PLAN_MODEL`을 digest pin으로 두고 `:latest`를 쓰지 않는다.
4. 기존 `version: "1.0"` Plan JSON은 `migrate_plan_v11()`이 AND tree로 옮긴다. Router 테스트는 그대로 통과해야 한다.

## 확인

- `uv run pytest tests/semantic_plan tests/query_understanding tests/evaluation tests/semantic_catalog`
- 기본값이 여전히 `shadow`인지 `tests/semantic_plan/test_pipeline_shadow.py`로 확인한다.
