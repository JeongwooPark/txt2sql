# llm2_geodb → llm2sql 고도화 비교

| 항목 | 내용 |
|------|------|
| 기준 시스템 | `llm2_geodb` (LM2GISDB) — 대화형 GIS 해석·오케스트레이션 |
| 고도화 시스템 | `llm2sql` (v0.2.1) — 자연어→SQL→한국어 답변 |
| 비교 범위 | 자연어·SQL·의도·메타데이터·안전·세션·답변 품질 |
| **명시적 제외** | 지도 시각화, GeoServer 레이어, OpenLayers, WMS/WFS, Shapefile ETL |
| 작성 목적 | `llm2_geodb`에서 `llm2sql`로 이어진 **고도화 내용** 문서화 |

---

## 목차

1. [요약](#1-요약)
2. [문제 정의와 포지셔닝](#2-문제-정의와-포지셔닝)
3. [계승한 설계](#3-계승한-설계)
4. [고도화 핵심: NL→SQL 완결](#4-고도화-핵심-nlsql-완결)
5. [의도·라우팅 고도화](#5-의도라우팅-고도화)
6. [스키마·메타데이터 고도화](#6-스키마메타데이터-고도화)
7. [SQL 검증·교정·실행](#7-sql-검증교정실행)
8. [세션·모호성·후속 질의](#8-세션모호성후속-질의)
9. [답변 생성·품질](#9-답변-생성품질)
10. [제품 표면·운영](#10-제품-표면운영)
11. [처리 흐름 대비](#11-처리-흐름-대비)
12. [기능 대조표](#12-기능-대조표)
13. [연구 한계(L)와 llm2sql 대응](#13-연구-한계l와-llm2sql-대응)
14. [모듈 매핑](#14-모듈-매핑)
15. [결론](#15-결론)

---

## 1. 요약

`llm2_geodb`는 행정 GIS DB의 **스키마·질의·결과 이해 장벽**을 완화하기 위해, 사용자가 제공한 Spatial SQL을 **안전하게 실행**하고 결과를 **메타데이터 주입 한국어로 해석**하는 대화 계층을 정립했다. 다만 **자연어→SQL 생성(NL→SQL)** 은 의도적으로 비어 있었고, 연구보고서에서도 **L5: 스키마 RAG + Text-to-SQL + 검증 실행** 을 후속 과제로 명시했다.

`llm2sql`은 이 기반(읽기 전용 거버넌스, 메타데이터 정렬 답변, 의도 분기, 다턴 맥락, 로컬 Ollama)을 계승하면서, L5를 중심으로 **자연어 질의만으로 SELECT를 생성·검증·실행하고 한국어로 답하는 파이프라인**을 구현·고도화한 시스템이다.

> 한 줄: **해석·안전 실행(llm2_geodb) → 자연어 조회 완결(llm2sql)**. 본 문서는 지도화를 제외한 대화·SQL 계층만 다룬다.

---

## 2. 문제 정의와 포지셔닝

### 2.1 공통으로 다루는 세 가지 장벽

| 장벽 | 현상 | llm2_geodb 대응 | llm2sql 대응 |
|------|------|-----------------|--------------|
| 스키마 장벽 | `AL_D010_…`, `A9` 등 코드·영문 식별자 | 실행 SQL의 테이블 메타 조회 후 해석에 주입 | 스키마 RAG + display/fix + 답변에서 표시명 우선 |
| 질의 장벽 | PostGIS·JOIN 숙련 요구 | SQL 작성 **상담 힌트** (자동 생성·실행 루프 없음) | **NL→SQL 생성** + 규칙 라우터 + 검증·재시도 |
| 결과 이해 장벽 | 실행 성공 ≠ 의미 이해 | 샘플 결과 + 메타 → 한국어 해석 | 템플릿/LLM 서술 + 프로필·비교·차트 스펙 |

### 2.2 시스템 포지션

| 구분 | llm2_geodb | llm2sql |
|------|------------|---------|
| 핵심 I/O | SQL 입력 → 실행 → 한국어 해석 | 자연어 입력 → SQL → 실행 → 한국어 답변 |
| NL→SQL | **미구현** (UI stub, L5) | **구현** (RAG+LLM + 규칙 경로) |
| 의도 모델 | `EXECUTE` / `SQL` / `CHAT` | `guide`·`meta`·`clarify`·`profile`·`rank_compare`·`sql` 등 |
| SQL 출처 | 사용자 작성·붙여넣기·히스토리 회수 | 시스템 생성(또는 규칙 템플릿) |
| 주 스택 | Flask · Ollama · PostGIS 메타 | FastAPI/CLI 엔진 · Ollama · PostGIS · 스키마 카탈로그 |
| 도메인 | 범용 GIS 대화 프로토타입 | 부산 GIS(건물·행정구역·기초구역·산업단지)에 특화 |

### 2.3 설계 철학의 연속성

양 시스템 모두 다음 제약을 공유한다.

1. 원본 DB에 대한 **쓰기성 연산 금지**
2. 사용자 대면 설명은 **업무 표시명·설명** 우선
3. 가능하면 **온프레미스 LLM(Ollama)** 으로 처리
4. 규칙과 LLM을 **계층화**하여 비용·안정성 균형

`llm2sql`은 여기에 **“질문을 SQL로 바꿀 책임”** 을 시스템이 지고, 그 책임을 **검증 루프**로 뒷받침한다는 점이 결정적 차이이다.

---

## 3. 계승한 설계

### 3.1 읽기 전용 거버넌스

| 항목 | llm2_geodb | llm2sql |
|------|------------|---------|
| 핵심 API | `dialogue/safety.py` — `assert_readonly_sql`, `guard_and_execute` | `llm2sql/db.py` — `assert_readonly_sql`, `ensure_limit`, `execute_query` |
| 정책 | SELECT/WITH 계열 조회만 허용, 쓰기·DDL 거부 | 동일 + 다중 문장(`;`) 차단, LIMIT 강제, geometry 직렬화 생략 |
| 계층 | 의도 분류 · 생성 프롬프트 · 실행 API 키워드 차단 | 의도/가이드 거절 · SQL 생성 프롬프트 · 실행 전 가드 · 사전 검증 |

### 3.2 메타데이터 정렬 해석·답변

`llm2_geodb`는 실행 SQL에서 주 테이블을 추출한 뒤 `table_metadata` / `column_metadata`(및 col_def·pnu_def 계열)로 **표시명·설명·단위**를 프롬프트에 넣어 해석한다. SQL 재출력을 억제하는 **해석 모드**와 일반 **상담 모드**를 분리한다.

`llm2sql`은 동일 메타 자산을 다음으로 확장한다.

- 답변·프로필 서술에서 컬럼코드(`A9` 등) **비노출**
- 생성 SQL의 한글 display → 물리명 **rewrite** (`sql_fix.py`)
- 스키마 RAG 카탈로그에 동의어·샘플값 반영 (`semantic_meta.py`, `schema_retriever.py`)
- 메타 전용 QA 경로 (`meta_qa.py`) — “어떤 데이터가 있어?”, “A4 의미가 뭐야?”

### 3.3 의도 분기와 이중 게이트

`llm2_geodb`의 ORCH는 **규칙 게이트**(단문 실행, 발화 내 SQL 추출) 후 **LLM 의도 분류**(EXECUTE/SQL/CHAT)로 분기한다. 실행과 상담을 API·프롬프트 수준에서 분리한다.

`llm2sql`은 “실행할지 말지”를 넘어 **어떤 스킬로 답할지** 까지 라우팅한다. 고빈도 조회는 규칙 라우터로 LLM을 우회하고, 애매한 경우만 생성 경로로 보낸다.

### 3.4 다턴 대화 상태

| 항목 | llm2_geodb | llm2sql |
|------|------------|---------|
| 상태 위치 | 브라우저 `chatHistory`, `lastExecutedSQL` | 서버/CLI 공용 `SessionContext` |
| 주 용도 | SQL 재실행, 상담 맥락 | clarify 선택, focus 건물 후속, 차트 pending, 직전 질문 확장 |
| 한계(당시) | 히스토리 무제한·요약 메모리 없음 | 슬라이딩 요약은 제한적이나, 구조화 슬롯으로 후속 정확도 향상 |

### 3.5 로컬 LLM·후처리

- Ollama 기반 호출, 모델 교체 가능 사상
- think 태그·역할 접두어 등 출력 정규화 아이디어 → `llm2sql` 답변 경로에서도 정제·템플릿 폴백으로 품질 관리

---

## 4. 고도화 핵심: NL→SQL 완결

### 4.1 llm2_geodb의 공백 (L5)

연구보고서 한계표:

| ID | 한계 | 후속 방향 |
|----|------|-----------|
| L5 | NL→SQL 미완 | 스키마 RAG + Text-to-SQL + 검증 실행 |

UI에도 자연어→SQL 버튼이 stub로 남아 “아직 구현되지 않았습니다” 메시지를 넣는 수준이었다. 채팅의 SQL 도움은 **자유 텍스트 제안**이며, 생성 SQL의 자동 검증·실행 루프는 없다.

### 4.2 llm2sql의 생성 파이프라인

미매칭(규칙 라우터 비적중) 질의에 대해:

```text
질문
 → retrieve_schema (llm_schema_catalog 벡터 검색 + 도메인 강제 포함/제외)
 → build_few_shot_for_question (정적 FEW_SHOT + example_store 동적 검색)
 → generate_sql (Ollama)
 → rewrite_display_names / fix_common_sql_mistakes
 → validate_sql_preexec (도메인 진단 → sqlglot → EXPLAIN)
 → execute_query (+ 오류·빈결과 시 재생성, 최대 sql_max_retries)
 → format_success (한국어 답변)
```

관련 모듈:

| 모듈 | 역할 |
|------|------|
| `schema_retriever.py` | 임베딩 검색, 컴팩트 스키마 조립 |
| `sql_generator.py` | SYSTEM_PROMPT, `generate_sql` |
| `prompt_examples.py` | 정적 few-shot, DOMAIN_HINTS |
| `example_store.py` | 임베딩+Jaccard 예제 검색 |
| `sql_fix.py` | 한글명 → 물리 테이블/컬럼명 |
| `sql_validator.py` | 사전 검증 체인 |
| `rag_sql.py` | 라우터 우회한 RAG-only 벤치 경로 |

### 4.3 규칙 SQL 경로 (성능·안정성)

고빈도 패턴(건수, 높이/층수 필터, top-N 순위, 버퍼, 동 경계 교차, 산업단지, 건축년수 등)은 `intent_router.py`가 **템플릿 SQL**을 직접 만들어 LLM 생성을 우회한다.  
이는 `llm2_geodb`의 “규칙 우선 게이트” 철학을 **조회 생성 단계**까지 확장한 것이다.

`route_dispatch.py`(v0.1.2)는 `try_route` 1회 호출 + early allowlist + deferred 재사용으로 디스패치 비용을 줄인다.

---

## 5. 의도·라우팅 고도화

### 5.1 의도 라벨 비교

| llm2_geodb | llm2sql (`INTENT_LABELS`) | 설명 |
|------------|---------------------------|------|
| EXECUTE | (세션 후속·재질의로 대체) | 직전 SQL 재실행 중심 → focus/clarify 선택으로 재구성 |
| SQL | `sql` | DB 조회 필요 일반 질의 |
| CHAT | `guide`, `meta`, `out_of_scope` 등으로 세분 | 상담을 스킬별로 분리 |
| — | `clarify` | 동명 모호·주관 표현 확인 |
| — | `profile` | 지역·용도 특징 요약·비교 |
| — | `usage_overview` | 용도 구성·분포 |
| — | `rank_compare` | 복수 지역 최고 건물 비교 |
| — | `coverage` | 자료 범위(부산만인지 등) |

### 5.2 분류 방식

| 항목 | llm2_geodb | llm2sql |
|------|------------|---------|
| 기본 | LLM 초단답 + 부분문자열 라벨 파싱 | `INTENT_MODE=hybrid` (기본): LLM JSON + 규칙 폴백/보정 |
| 규칙 | 단문 실행·SQL 포함 여부 | `predict_intent_rules`, 알려진 오분류 패치(메타/프로필/단일지역 순위 등) |
| 설정 | — | `rules` / `hybrid` / `llm` 전환 가능 |

### 5.3 파이프라인 상 스킬 순서 (개념)

`llm2sql` `_ask_inner` / `run_ask` 기준 개념 순서:

1. 세션 전처리 (clarify 번호 선택, 차트 수락/거절/종류, 짧은 기준 보정 등)
2. 의도 분류 (hybrid/llm)
3. `guide_qa` — 기능·제한·인사·범위 외
4. `followup_qa` — focus 건물 속성
5. early `match_route` — 건물명·산업단지·순위 등
6. preferred intent 디스패치 — rank_compare / profile / meta / clarify …
7. `rank_compare_qa` → `profile_qa` / usage_overview → `meta_qa` → `clarify_qa`
8. `intent_router` (규칙 SQL)
9. RAG + LLM 생성·검증·실행
10. `answer` + (선택) 차트 제안, 세션 갱신

`llm2_geodb`에는 위와 같은 **도메인 스킬 분해**가 없고, 상담·해석·재실행의 오케스트레이션에 가깝다.

---

## 6. 스키마·메타데이터 고도화

### 6.1 스키마 선택

| 항목 | llm2_geodb | llm2sql |
|------|------------|---------|
| 방법 | SQL 문자열에서 첫 `FROM` 테이블 정규식 | `llm_schema_catalog` 벡터 유사도 검색 |
| 약점/보완 | JOIN·서브쿼리 시 메타 누락 (L1) | top-k + 건물/행정/산업단지 테이블 **강제 포함·제외** 휴리스틱 |
| 임베딩 | 없음 | Ollama embed (`OLLAMA_EMBED_MODEL`, 예: `mxbai-embed-large`) |
| 갱신 | 메타 CSV 적재 도구 | `scripts/refresh_schema_catalog.py` |

### 6.2 의미 메타·동의어

`llm2sql`은 `semantic_meta.py`로 테이블/컬럼 동의어를 보강하고, 컴팩트 스키마 텍스트에 샘플값·한글 설명을 실어 생성 프롬프트의 적중률을 높인다.  
`llm2_geodb`의 “메타 주입 해석”이 **실행 후 설명**에 쓰였다면, `llm2sql`에서는 **생성 전 스키마 선택·프롬프트**와 **실행 후 답변** 양쪽에 쓰인다.

### 6.3 메타 QA 전용 경로

| 질문 예 | llm2_geodb | llm2sql |
|---------|------------|---------|
| 어떤 데이터가 있어? | 일반 CHAT 상담 | `meta_catalog` |
| A4 컬럼 의미가 뭐야? | 상담(정확도 편차) | `meta_column` / display명 매칭 |
| 특정 데이터셋 요약 | 없음 | 건수·상위 용도 등 **요약** (스키마 나열만 하지 않음) |

---

## 7. SQL 검증·교정·실행

### 7.1 검증 깊이

| 단계 | llm2_geodb | llm2sql |
|------|------------|---------|
| 읽기 전용 키워드 | 있음 (선두/키워드 가드) | 있음 (강화: 금지 키워드 목록, 단일 문장) |
| 구문 검증 | 없음 (TODO 수준) | **sqlglot** |
| 계획 검증 | 없음 | **EXPLAIN** |
| 도메인 진단 | 없음 | `diagnose_sql` (잘못된 테이블/패턴 등) |
| 실행 실패 복구 | 사용자 재작성 의존 | LLM 재생성 + `error_feedback`, 재시도 상한 |
| 빈 결과 | 해석만 | 진단 후 재생성 / 공간 의도 시 PostGIS 강제·템플릿 폴백 |
| 공통 실수 교정 | 없음 | `fix_common_sql_mistakes` (예: A3→A4, D198↔D010, 순위 강제) |
| LIMIT | 실행 정책에 따름 | `ensure_limit`로 기본 LIMIT 부여 |

### 7.2 안전 속성 강화 포인트

`llm2_geodb`도 3층 안전 정책을 명시했으나, 가드가 **선두 키워드**에 치우친 단순 패턴이었다.  
`llm2sql`은 생성 SQL이 시스템에 의해 만들어지므로 **사전 검증 체인**이 더 중요하다. 여전히 범용 SQL 인젝션·CTE 우회에 대한 완전 형식 검증은 아니며, **읽기 전용 + 단일 SELECT + LIMIT** 을 운영 전제로 한다.

---

## 8. 세션·모호성·후속 질의

### 8.1 모호성 (Clarification)

| 항목 | llm2_geodb | llm2sql |
|------|------------|---------|
| 구조화 슬롯 | 없음 | `clarify_qa.check_ambiguity` |
| 동명 복수 구 | 상담에 의존 | 후보 제시 → `1` / `1번` / 구 이름 선택 |
| 주관 표현(좋은/추천) | 상담 안내 | `clarify_vague` — 수치 기준으로 유도 |
| 미지 지명 | 상담 | `clarify_unknown_place` 등 |

### 8.2 후속 질의

| 항목 | llm2_geodb | llm2sql |
|------|------------|---------|
| 중심 객체 | 직전 **SQL** | 직전 **focus 건물**(및 last question/route) |
| 예 | “실행해줘”, “다시” | “그 아파트의 이름은?”, “지번은?”, “높이는?” |
| 구현 | RecoverSQL / lastExecutedSQL | `followup_qa` + `SessionContext` |
| 짧은 보정 | 자유 상담 | 건축년수 기준 등 `_expand_followup_question` |

### 8.3 세션 객체 (`SessionContext`)

대표 상태(개념):

- clarify 후보·선택 대기
- focus 건물(속성 후속용)
- pending chart (제안·종류·시리즈 필터)
- last question / route / full question

웹은 `session_id`로, CLI는 `--chat`으로 동일 모델을 유지한다.

---

## 9. 답변 생성·품질

### 9.1 해석 vs 답변

| 항목 | llm2_geodb | llm2sql |
|------|------------|---------|
| 주 모드 | 실행 결과 **해석** (`interpret_sql_result`) | 질의 목적에 맞는 **답변** (`format_success` 등) |
| 입력 | SQL + 샘플 rows + 메타 컨텍스트 | route·rows·도메인 템플릿·(선택) LLM 서술 |
| SQL 노출 | 해석 본문에서 SQL 재출력 금지 설계 | 사용자 답변은 의미 중심, verbose/API로 SQL 확인 가능 |
| 샘플 | 상위 N건 중심 | 집계·순위·프로필은 **의도된 집계 SQL** 결과를 서술 |

### 9.2 템플릿 우선과 할루시네이션 완화

순위·건물명·일부 산업단지 경로는 **템플릿 답변**을 우선해 컬럼코드 노출·과장 서술을 막는다.  
특징 요약(`profile_qa`)은 집계 후 LLM 문단 서술, 실패 시 문장 폴백이다.

### 9.3 도메인 품질

- `domain.py`: 구·동·용도 별칭, 부산시 전역, 건축년수, 건물명 후보, 한국어 조사
- 이상값 필터: 비정상 높이·건축면적·연면적 제외 (`sane_height_sql` 등)
- 공간 템플릿: `spatial_templates.py` (동 내 건물 건수 등)

### 9.4 차트 (지도 제외)

지도 레이어와 별개로, `chart_qa.py`는 비교·프로필 등 답변 후 **Chart.js 스펙 제안**, 차트 종류 변경, 시리즈 필터(예: 높이만)를 제공한다.  
시각화 **수단**이 지도에서 차트/표 중심으로 바뀐 것이며, 본 문서의 “지도화 제외” 범위 안에서도 **결과 이해 보조**로 기록한다.

---

## 10. 제품 표면·운영

### 10.1 진입점

| 구분 | llm2_geodb | llm2sql |
|------|------------|---------|
| 웹 | Flask `/api/chat`, `/api/execute-query`, `/api/process-llm` | FastAPI `POST /api/chat` (SSE), `/api/session`, `/api/health` |
| CLI | (대화는 웹 중심) | `llm2sql.cli` 일회·`--chat`, progress/verbose/json |
| 라이브러리 | 모듈 직접 호출 | `Llm2SqlEngine.ask`, `AskResult`, `SessionContext` |

### 10.2 스트리밍·관측

- `on_progress` / `on_token` 콜백, 웹 SSE로 단계·토큰 스트리밍
- `ProgressTracker`로 파이프라인 단계 가시화

### 10.3 평가·회귀

`llm2_geodb`는 연구용 검증 축(의도 accuracy, 해석 인간평가, 안전 차단율)을 **제시**했다.  
`llm2sql`은 실행 가능한 스크립트로 일부를 상시화한다.

예시:

- `scripts/smoke_nl_queries.py`, `smoke_clarify.py`, `smoke_profile_qa.py`, `smoke_engine.py`
- `scripts/benchmark_intent_hybrid.py`, `benchmark_route_opt.py`, `benchmark_new10.py`
- `scripts/eval_spatial_queries.py` (공간 SQL 품질; 지도 렌더와 무관)

---

## 11. 처리 흐름 대비

### 11.1 llm2_geodb (지도 단계 제외)

```text
사용자 발화
  ├─ 단문 실행? → 직전/히스토리 SQL 회수 → 읽기전용 실행 → 메타 주입 해석
  ├─ 발화에 SELECT/WITH? → ExtractSQL → 실행 → 해석
  ├─ intent=EXECUTE? → 재실행 → 해석
  └─ 그 외 → classify → CHAT 상담 (SQL 생성·검증 루프 없음)
```

### 11.2 llm2sql

```text
자연어 질문
  → 세션 전처리 (clarify 선택, 차트, 짧은 후속 보정)
  → 의도 분류 (hybrid)
  → guide / followup / rank_compare / profile / meta / clarify
  → 규칙 라우터 SQL 또는 RAG+LLM SQL
  → 검증·교정·실행 (재시도)
  → 한국어 답변 (+ 선택적 차트 제안)
  → SessionContext 갱신
```

---

## 12. 기능 대조표

| 기능 | llm2_geodb | llm2sql |
|------|:----------:|:-------:|
| 사용자 SQL 실행 | ✅ | △ (시스템 생성 SQL 실행이 주) |
| NL→SQL 생성 | ❌ | ✅ |
| 스키마 벡터 RAG | ❌ | ✅ |
| 동적/정적 few-shot | ❌ | ✅ |
| sqlglot / EXPLAIN 사전검증 | ❌ | ✅ |
| 실행 실패·빈결과 재생성 | ❌ | ✅ |
| 규칙 템플릿 SQL (고빈도) | △ (오케스트레이션 규칙만) | ✅ |
| 하이브리드 다중 의도 | △ (3라벨) | ✅ (다스킬) |
| 메타데이터 주입 설명 | ✅ (해석) | ✅ (해석+생성+meta QA) |
| 읽기 전용 가드 | ✅ | ✅ (강화) |
| 구조화 clarify | ❌ | ✅ |
| focus 기반 속성 후속 | ❌ | ✅ |
| 특징 요약·지역 비교 | ❌ | ✅ |
| 순위·최고건물 비교 | ❌ | ✅ |
| 이상값 필터 | ❌ | ✅ |
| 차트 스펙 제안 | ❌ | ✅ |
| 엔진 API + SSE 챗봇 | △ (Flask REST) | ✅ |
| 벤치/스모크 스크립트 | △ (문서 축) | ✅ |
| 지도 레이어 시각화 | ✅ (본 문서 제외) | — (범위 외) |

범례: ✅ 지원 / △ 부분·간접 / ❌ 없음 / — 비교 제외

---

## 13. 연구 한계(L)와 llm2sql 대응

`llm2_geodb` 보고서 §18 한계 중, 지도와 무관한 항목과 대응 현황이다.

| ID | llm2_geodb 한계 | llm2sql에서의 대응 |
|----|-----------------|-------------------|
| L1 | FROM 단일 테이블 휴리스틱 | 벡터 RAG + 다중 테이블 스키마 조립·강제 포함 (완전 AST 파서는 아님) |
| L2 | 세미콜론 의존 SQL 추출 | 사용자 SQL 추출 의존도 감소 — **시스템 생성 SQL**이 주경로 |
| L3 | 의도 라벨 부분문자열 파싱 | JSON 의도 분류 + 라벨 enum + hybrid 보정 |
| L4 | 샘플 10건 해석의 대표성 | 질의 유형별 **집계·순위 SQL**로 요약; 프로필은 통계 기반 |
| L5 | NL→SQL 미완 | **해소** — RAG + Text-to-SQL + 검증 실행 + 규칙 경로 |
| L6 | 히스토리 무제한 | 구조화 세션 슬롯으로 핵심 맥락 유지 (장기 요약 메모리는 향후 과제) |
| L7 | `has_last_sql` 가정 | focus/last_question 등 명시 상태 필드 |
| L8 | 해석·상담 라우팅 UI 부재 | 의도·스킬 자동 라우터 + 웹 보기 버튼(clarify) |

---

## 14. 모듈 매핑

### 14.1 llm2_geodb (대화·SQL 계층)

| 영역 | 주요 위치 |
|------|-----------|
| 의도 | `llm_interpreter.classify_intent` |
| 상담 | `chat`, `chat_conversation` |
| 해석 | `interpret_sql_result`, `prompts/sql_interpretation_prompt.txt` |
| 메타 | `dialogue/metadata_context.py` |
| 안전 | `dialogue/safety.py` |
| 정규화 | `dialogue/normalize.py` |
| API | `webapp.py` `/api/chat`, `/api/process-llm`, `/api/execute-query` |
| 프론트 ORCH | `static/js/map.js`, `dialogue-algorithms.js` (SQL 추출·재실행; 지도 호출은 본 문서 범위 외) |

### 14.2 llm2sql

| 영역 | 주요 위치 |
|------|-----------|
| 엔진·파이프라인 | `engine.py`, `pipeline.py`, `types.py` |
| 의도 | `intent_classifier.py`, `route_dispatch.py` |
| 규칙 SQL | `intent_router.py`, `spatial_templates.py` |
| RAG·생성 | `schema_retriever.py`, `sql_generator.py`, `example_store.py` |
| 검증·실행 | `sql_validator.py`, `sql_fix.py`, `db.py` |
| 스킬 QA | `guide_qa.py`, `meta_qa.py`, `clarify_qa.py`, `profile_qa.py`, `rank_compare_qa.py`, `followup_qa.py` |
| 답변·차트 | `answer.py`, `chart_qa.py` |
| 세션·도메인 | `session.py`, `domain.py`, `semantic_meta.py` |
| 웹·CLI | `webapp/`, `cli.py` |

---

## 15. 결론

`llm2_geodb`는 GIS DB에 대한 **질문–(사용자 SQL)–실행–메타데이터 해석** 순환과 **다층 안전·대화 오케스트레이션**을 연구·프로토타입으로 정립했다. 지도화는 그 순환의 한 출력이었으나, 본 문서에서는 제외하고 **대화·SQL 계층**만 평가했다.

`llm2sql`은 그 계층을 전제로 다음을 고도화했다.

1. **L5 완결**: 스키마 RAG + Text-to-SQL + 검증·재시도 실행  
2. **규칙/하이브리드 라우팅**: 고빈도 LLM 우회 + 다스킬 의도  
3. **구조화 세션**: clarify 번호 선택, focus 후속, 차트 pending  
4. **도메인 품질**: 부산 GIS 바인딩, 이상값 필터, 템플릿 답변, 메타/프로필/순위 전용 경로  
5. **제품화**: 재사용 엔진, SSE 챗봇, CLI, 벤치·스모크

따라서 `llm2sql`은 `llm2_geodb`의 **대화형 이해·안전 실행** 성과를 계승하면서, 실무 사용자가 SQL을 직접 쓰지 않아도 되는 **자연어 조회 완결형**으로 발전한 결과물이다.

---

## 부록 A. 버전별 고도화 메모 (llm2sql)

| 버전 | 요지 |
|------|------|
| 0.1.0 | `Llm2SqlEngine`, 웹 SSE, clarify 번호 선택, 부산시 전역 순위, 이상값 필터, 특징·최고건물 비교, 컬럼코드 비노출 |
| 0.1.1 | 하이브리드 의도, 차트, 데이터셋 요약, 메타/프로필 오분류 수정, RAG·example store·벤치 |
| 0.1.2 | route_dispatch 최적화, 건물명·산업단지·차트 시리즈 필터, `benchmark_route_opt` |
| 0.1.3 | 파이프라인·Ollama·RAG 경로 단순화, 용적율/산업단지 프로필 비교, 고도화 문서 |
| 0.1.4 | 지명 사전(법정/행정), 공간·임계·행정동 목록, 의도분류/답변 템플릿 최적화 |
| 0.2 | 지도 3분할, GeoServer WMS/WFS, KorDB·분석 레이어, Identify |
| 0.2.1 | Head/Bottom 프레임, 데이터 관리 골격, Identify 설명, 분석 레이어 재사용 |

## 부록 B. 참고 경로

- `D:\py_workspace\llm2_geodb\docs\RND_대화형GIS해석_알고리즘_연구결과보고서.md`
- `D:\py_workspace\llm2sql\README.md`
- 본 문서: `D:\py_workspace\llm2sql\docs\고도화_llm2_geodb_to_llm2sql.md`
