# SQP v1.1 롤아웃 보고서

상태: FIX-4 완료, **hybrid 승격**, 제품 **0.2.3**

- 최종 상태: `SEMANTIC_PLAN_MODE` 기본값 `hybrid`
- 브랜치: `feat/sqp-v11-roadmap`
- 태그: `sqp-v11-phase-3`, `sqp-v11-phase-4`, `sqp-v11-ready`
- 비교:
  - A `off`: live verified 30건 재실행. `env_blocked=false`. 모델 `qwen3:latest` digest `500a1f067a9f7826`, embed `mxbai-embed-large` digest `468836162de7f81e`. `:latest`라 `--official` 없이 돌리고 digest를 기록
  - B `hybrid` 0.2.2: 재구현하지 않음. C/E만 A와 비교
  - C Plan 1.1+verifier: heuristic verified **30/30** 의미 일치
  - D linking: expression+place holdout n=17, Recall@10=1.0, Value Recall@5=1.0
  - E Phase 3 unit 유지, Phase 4 live spatial 6/6 (`ENV_BLOCKED` 아님). touches 0건은 정상, 조건 미완화
- 차단: 없음
- 결론: 전 지표 통과이므로 기본값을 `hybrid`로 올린다. 롤백은 `SEMANTIC_PLAN_MODE=off`
