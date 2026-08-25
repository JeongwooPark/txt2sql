# Routing architecture after contract-first refactor

작업 브랜치: `contract-capability-sqp-20260825`  
완료 시점: 2026-08-25

Query Contract가 모든 라우트 결정의 선행 계층이다. Deterministic Router는 Contract를 100% 지원할 때만 실행하고, 부족하면 Semantic Query Plan으로 보낸다.

## 실행 흐름

```text
ask()
  └─ run_ask()
       ├─ session rewrite
       ├─ extract_contract(final question)                 ← 모든 SQL 경로의 Source of Truth
       ├─ list-attr / year-grain (Contract 생성 이후, 직전 SQL 재사용)
       ├─ chart / guide
       ├─ _classify_intent
       └─ _ask_inner(contract=)
            ├─ semantic-plan followup (동일 Contract)
            ├─ subset / year-bin followup (+ legacy_route_eligible)
            ├─ match_route → early 후보 (우선순위만)
            │    └─ 실행은 route_allowed / legacy_route_eligible
            ├─ _try_preferred_intent(+ contract, capability gate)
            ├─ rank / usage / profile (+ route_allowed)
            ├─ meta / clarify
            ├─ deferred try_route (+ missing_requirements 로그)
            │    └─ [decision] ROUTER | SEMANTIC_PLAN
            ├─ run_semantic_plan(contract=)
            │    generate → normalize → verify_contract → compile
            └─ run_rag_sql
```

## 단계 표

| 단계 | 함수 | 입력 | 출력 | 역할 |
|---|---|---|---|---|
| 1 질문 진입 | `run_ask` | question | result | 세션 rewrite 후 Contract 생성 |
| 2 Contract | `extract_contract` | 최종 질문 | QueryContract + `is_sufficient()` | entity/predicate/agg/group/output/order |
| 3 후보 탐지 | `detect_route_candidates` / `try_route` / `match_route` | question + contract | intent 목록 | 실행이 아니라 후보 |
| 4 Capability | `legacy_route_eligible` / `missing_requirements` | route + contract | missing 목록 | 완전 지원일 때만 Router |
| 5 early | `_is_early_intent` | intent | 우선순위 | 실행 권한 없음 |
| 6 preferred | `_try_preferred_intent` | IntentPrediction + contract | 답변 또는 None | rank/usage/profile/meta 동일 gate |
| 7 Router | `_finish_routed_query` | RoutedQuery | SQL 실행 | `[decision] ROUTER` |
| 8 SQP | `generate_semantic_plan(contract=)` | contract + question | SemanticQueryPlan | percentile/derived/ratio 보존 |
| 9 verifier | `verify_contract` | contract + plan | ok / hard_fail | agg, group, output, order, limit, ratio |
| 10 compiler | `compile_semantic_plan` | plan | SQL | Plan만 직렬화 |

## 불변식

```text
Query Contract = 사용자 요구의 Source of Truth
Capability     = 이 Route가 그 요구를 전부 처리할 수 있는가
Router         = 단순·완전한 Contract의 Fast Path
SQP            = 완전 지원하지 못하는 복합 Contract
```

Partial semantic coverage must never execute a deterministic route.

## 평가 요약

| 항목 | 이전 (`32_post_fix500`) | 이후 (`34_full500`) |
|---|---|---|
| pytest | 246 passed | 254 passed |
| Q3_agg_rank 24 | 10/24 (41.7%) | 10/24 (41.7%) |
| full-500 | 393/500 (78.6%) | 367/500 (73.4%) |
| legacy hit | 88 | 136 |
| semantic_plan hit | 346 | 292 |
| clarify hit | 38 | 47 |
| avg / p50 / p95 ms | 1640 / 139 / 12344 | 2141 / 169 / 13969 |

단순 count는 Router를 유지한다. 전체를 SQP로 보내지 않았다. full-500 하락은 일부 복합 질의가 threshold/D198 부분 라우트로 새어 정답이 깨진 경우가 주된 회귀다.
