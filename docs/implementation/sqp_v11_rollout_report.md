# SQP v1.1 롤아웃 보고서

상태: STEP-24 완료, **hybrid 미승격**

- 최종 상태: `SEMANTIC_PLAN_MODE` 기본값 `shadow` 유지
- 브랜치: `feat/sqp-v11-roadmap`
- 태그: `sqp-v11-phase-3`, `sqp-v11-phase-4`. `sqp-v11-ready`는 미생성
- 비교:
  - A `off`: 기준선. live A/B 전량 재실행은 하지 않음
  - B `hybrid` 0.2.2: 기본값으로 쓰지 않음
  - C Plan 1.1+verifier: unit 통과, gold exact 2/30
  - D linking: labeled holdout 없음 → Recall gate 미통과
  - E candidates+spatial policy: unit 통과, live spatial 미측정
- 차단: Phase 1 gold, Phase 2 holdout, live A–E KPI 미완
- 결론: 하나라도 미달이면 `hybrid`로 올리지 않는다
