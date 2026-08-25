# Routing architecture before contract-first completion

기준 브랜치: `systematic-fix-q500-20260825` (`271afef`)
작업 브랜치: `contract-capability-sqp-20260825`
시점: 2026-08-25

3-core 리팩터 이후 Query Contract는 `_ask_inner`에서 먼저 생성되고, early / profile / `try_route` 실행 전에 `route_allowed`가 있다. 아래는 그 직후 상태의 실제 흐름과 남은 구멍이다.

## 실행 흐름

```text
ask()
  └─ run_ask()
       ├─ session rewrite / list-attr / year-grain / chart / guide   ← Contract 없음
       ├─ _classify_intent
       └─ _ask_inner()
            ├─ extract_contract(question)                            ← 최초 Contract
            ├─ semantic-plan followup
            ├─ subset / year-bin followup (+ route_allowed)
            ├─ answer_followup                                      ← gate 없음
            ├─ match_route → early (+ route_allowed)
            ├─ _try_preferred_intent                                ← gate 없음
            ├─ rank / usage / profile (+ route_allowed)
            ├─ meta / clarify                                       ← gate 없음
            ├─ deferred try_route (+ route_allowed)
            ├─ run_semantic_plan → generate_semantic_plan           ← Contract 재추출
            └─ run_rag_sql                                          ← gate 없음
```

## 단계 표

| 단계 | 현재 함수 | 입력 | 출력 | 문제 |
|---|---|---|---|---|
| 1 질문 진입 | `ask` → `run_ask` | question | result dict | `run_ask` 선행 경로에 Contract 없음 |
| 2 조기 안내 | `_try_list_attr_followup`, `_try_year_grain_followup`, `try_guide` | question, session | SQL 또는 안내 | SQL 경로가 Contract/capability 없이 반환 가능 |
| 3 Contract | `_ask_inner` 내부 `extract_contract` | question | QueryContract | `_ask_inner` 밖에서는 생성되지 않음 |
| 4 match_route | `match_route` / `match_route_optimized` | question only | RouteMatch early/deferred | Contract 미전달. early allowlist는 우선순위+실행 후보 |
| 5 try_route | `try_route` | question | RoutedQuery \| None | 문자열 매칭으로 SQL 즉시 생성. `should_defer_compound_to_plan` 키워드 defer |
| 6 profile | `is_profile_question` + `answer_profile_question` | question | profile SQL | 규칙 체인은 `route_allowed`. `_try_preferred_intent`는 우회 |
| 7 early 실행 | `_finish_routed_query` | RoutedQuery + contract | SQL 실행 | gate는 있으나 `match_route` 자체는 문자열만 봄 |
| 8 preferred intent | `_try_preferred_intent` | IntentPrediction | profile/rank/usage/meta | **capability 없이 실행** |
| 9 SQP | `run_semantic_plan` → `generate_semantic_plan` | question | SemanticQueryPlan | Contract 인자 없음. 내부 재추출 |
| 10 fallback | `run_rag_sql` | question | SQL | Contract/capability 없음 |
| 11 compiler | `compile_semantic_plan(plan)` | SemanticQueryPlan | SQL | Plan-only (3-core 이후). question 재해석 없음 |
| 12 verifier | `verify_contract(question, plan)` | question + plan | ContractVerifyResult | outputs/limit/ratios/group field 미비교 |

## 남은 구조 문제

1. Partial coverage route가 `_try_preferred_intent`로 실행될 수 있음
2. `match_route` / `try_route` / generator가 Contract를 받지 않고 질문을 다시 해석
3. `should_defer_compound_to_plan`이 capability와 이중화
4. `supports_spatial`은 필드만 있고 `missing_requirements`에서 미검사
5. 미매핑 intent가 `SIMPLE_COUNT`로 fallback
6. `select_execution_path`는 테스트 전용
7. capability reject 시 missing 목록이 로그에 없음

## 불변식 (목표)

```text
Partial semantic coverage must never execute a deterministic route.
```
