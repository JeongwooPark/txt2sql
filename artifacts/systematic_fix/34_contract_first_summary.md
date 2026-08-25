# Contract-first routing — final summary

브랜치: `contract-capability-sqp-20260825`  
기준: `systematic-fix-q500-20260825` / `32_post_fix500.json`

## 한 줄 결론

Contract → Capability → Router/SQP 분기가 production에 들어갔다. 단순 질문은 Router fast path를 유지하고(legacy 88→136), 전 질문을 SQP로 몰지 않았다(SQP 346→292). Q3 24건은 10/24로 동일. full-500은 393→367(−26)로 하락했다.

## 커밋

1. `docs(architecture): document routing flow before contract-first refactor`
2. `refactor(pipeline): create query contract before all route decisions`
3. `refactor(routing): gate deterministic routes by full contract capability`
4. `refactor(routing): remove partial-match early route execution`
5. `refactor(semantic-plan): generate and verify plans from query contract`
6. `test(routing): cover contract capability router and sqp decisions`
7. `fix(routing): reject threshold routes when temporal predicates are required`

## pytest

254 passed, 0 failed (`artifacts/systematic_fix/34_pytest.json`). Cases A–F는 `tests/query_understanding/test_contract_router_sqp_decisions.py`.

## 골드 평가

| 세트 | before | after | artifact |
|---|---|---|---|
| Q3_agg_rank 24 | 10/24 (41.7%) | 10/24 (41.7%) | `34_q3_agg_rank.json` |
| full-500 | 393/500 (78.6%) | 367/500 (73.4%) | `34_full500.json` |

## Route hit / latency (`34_vs_32_compare.json`)

| | 32_post_fix500 | 34_full500 |
|---|---|---|
| legacy | 88 | 136 |
| semantic_plan (clarify 제외) | 346 | 292 |
| clarify | 38 | 47 |
| other (meta/guide) | 28 | 25 |
| avg_ms | 1640 | 2141 |
| p50_ms | 139 | 169 |
| p95_ms | 12344 | 13969 |
| elapsed_s | 820.9 | 1071.8 |

회귀 36건 / 개선 10건. 가장 많은 회귀 쌍은 `semantic_plan_count → building_area_threshold_count` (6).

## 아키텍처 목표 대비

- Query Contract가 `run_ask` 최상단에서 생성된다.
- Router 실행은 `legacy_route_eligible`만 허가한다.
- early allowlist는 우선순위만 제공한다.
- profile / preferred-intent도 동일 gate.
- SQP verifier가 aggregation / group / output / order / limit / ratio를 검사한다.
- 단순 질문 Router 유지: Case A, `해운대구 건물 몇 채야` regression 통과.

05–29 artifact는 덮어쓰지 않았다.
