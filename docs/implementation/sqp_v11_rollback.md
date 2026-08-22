# SQP v1.1 rollback

SQP를 끄려면 코드 롤백 없이 설정만 되돌린다.

```
SEMANTIC_PLAN_MODE=off
```

그러면 Router 미적중 질의는 RAG로 간다. 장애 시에는 `off`가 가장 짧은 경로다.

## 코드 롤백

1. `git checkout <이전 태그 또는 d6fc4af>`
2. 프로세스(웹/CLI)를 재시작한다.
3. 운영 DB DDL/DML은 이 작업에서 변경하지 않았으므로 스키마 롤백은 없다.

강제 푸시는 금지한다. hybrid 기본값은 FIX-4에서 올렸다. 관측만 하려면 `shadow`로 내린다.
