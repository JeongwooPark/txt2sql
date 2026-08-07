# llm2sql

**버전 0.1.0**

부산 GIS(건물·행정구역·기초구역·산업단지) 데이터를 **자연어**로 조회하는 Python 도구입니다.  
로컬 **Ollama**로 SQL을 생성·보정하고, **PostgreSQL + PostGIS**에서 실행한 뒤 **한국어**로 답변합니다.  
CLI·라이브러리 엔진·**웹 챗봇 UI**를 제공합니다.

```text
질문 → 안내/메타/모호성/특징·비교/순위비교/라우터/RAG+LLM
     → SQL 실행 → 한국어 답변 (스트림 가능)
         └─ 세션: 후속 질문, 모호 동 번호 선택(1·2번)
```

---

## 목차

1. [특징](#특징)
2. [요구 환경](#요구-환경)
3. [설치](#설치)
4. [환경 변수](#환경-변수)
5. [엔진 API (라이브러리)](#엔진-api-라이브러리)
6. [웹 챗봇 UI](#웹-챗봇-ui)
7. [사용법 (CLI)](#사용법-cli)
8. [질문 유형과 동작](#질문-유형과-동작)
9. [파이프라인 구조](#파이프라인-구조)
10. [데이터·메타데이터](#데이터메타데이터)
11. [제한 사항](#제한-사항)
12. [벤치마크·스크립트](#벤치마크스크립트)
13. [프로젝트 구조](#프로젝트-구조)
14. [문제 해결](#문제-해결)
15. [0.1.0 변경 요약](#010-변경-요약)

---

## 특징

| 영역 | 내용 |
|------|------|
| 조회 | 건수·순위·버퍼/교차 등 공간 조건 SELECT |
| 설명 | 데이터셋·컬럼(속성) 의미 안내 |
| 요약 | 동·용도 특징 집계 → **문단형 자연어** (LLM 서술, 실패 시 문장 폴백) |
| 비교 | 지역 간 특징 비교, **최고 높이/면적 건물** 지역 간 비교 |
| 순위 | 부산시·구·동 단위 건물면적/연면적/높이/지상층 1위 (이상값 필터) |
| 안전 | SELECT/WITH만 허용, 쓰기·DDL 차단 |
| 모호성 | 복수 구 동명 → 후보 제시 후 **`1` / `1번` 선택** 가능 |
| 후속 | 직전 건물 focus로 「이름/지번/높이」 등 |
| 안내 | 역할·기능·제한, 범위 외 거절·유도 |
| 성능 | 고빈도 패턴은 규칙 라우터로 LLM 우회 |
| 엔진 | `Llm2SqlEngine` (연결·Ollama 재사용, `on_progress` / `on_token`) |
| 웹 UI | 버블 채팅 + 로딩 스피너 + **SSE 스트리밍** |

---

## 요구 환경

- **Python** 3.13+
- **[uv](https://github.com/astral-sh/uv)** (권장)
- **PostgreSQL** + **PostGIS**
- **Ollama** (`localhost:11434` 등)
  - 생성 모델 예: `qwen3:latest`
  - 임베딩 모델 예: `mxbai-embed-large` (카탈로그 vector 차원과 일치)
- DB 메타·카탈로그: `table_metadata`, `column_metadata`, `llm_schema_catalog` 등

---

## 설치

```bash
git clone https://github.com/JeongwooPark/llm2sql.git
cd llm2sql
uv sync
cp .env.example .env
# .env 에 DATABASE_URL, Ollama 설정 입력
```

비밀번호에 특수문자가 있으면 `DATABASE_URL`에 **URL 인코딩**이 필요합니다.

```bash
ollama pull qwen3:latest
ollama pull mxbai-embed-large
uv run python scripts/refresh_schema_catalog.py   # 스키마 임베딩 갱신 시
```

---

## 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `DATABASE_URL` | PostgreSQL 접속 URL | (필수) |
| `OLLAMA_HOST` | Ollama 엔드포인트 | `http://localhost:11434` |
| `OLLAMA_MODEL` | SQL·답변 생성 모델 | `qwen3:latest` |
| `OLLAMA_EMBED_MODEL` | 스키마 RAG 임베딩 | `mxbai-embed-large` |
| `SCHEMA_TOP_K` | 카탈로그 검색 top-k | `5` |
| `DEFAULT_LIMIT` | SELECT 기본 LIMIT | `100` |

---

## 엔진 API (라이브러리)

```python
from llm2sql import Llm2SqlEngine, SessionContext, Settings

with Llm2SqlEngine.from_env() as engine:
    session = SessionContext()
    r = engine.ask(
        "구서동에서 건물면적이 가장 큰 아파트는?",
        session=session,
        on_progress=lambda stage, msg, detail: print(stage, msg),
        on_token=lambda t: print(t, end="", flush=True),  # 답변 토큰 스트림
    )
    print(r.ok, r.route, r.answer)
    r2 = engine.ask("그 아파트의 이름은?", session=session)
    print(r2.answer)
```

- `AskResult`: `ok`, `answer`, `sql`, `tables`, `rows`, `route`, `steps` 등 (`to_dict()`)
- 세션은 호출자가 `SessionContext`를 유지 (`clarify_place` 후보·focus 건물)

일회성 호환: `from llm2sql import ask, load_settings` → `ask(q, load_settings())`.

---

## 웹 챗봇 UI

버블형 대화 UI. LLM 대기 중 스피너, SSE로 진행 단계·답변 토큰 스트리밍.

```bash
uv sync
uv run llm2sql-web
# 또는: uv run python -m llm2sql.webapp
```

브라우저: `http://127.0.0.1:8000`

| 기능 | 설명 |
|------|------|
| 세션 | `session_id`로 후속·모호 선택 유지 |
| 모호 동 | 보기 버튼 클릭 또는 `1` / `2번` 입력 |
| 스크롤 | 새 메시지·스트림 시 하단 고정 (위로 보면 일시 중지) |
| API | `POST /api/chat` (SSE), `POST /api/session`, `GET /api/health` |

---

## 사용법 (CLI)

```bash
uv run python -m llm2sql.cli "해운대구 건물 몇 채야?"
uv run python -m llm2sql.cli --chat          # 대화형
uv run python -m llm2sql.cli -p "..."        # 진행 로그
uv run python -m llm2sql.cli -v "..."        # SQL·rows
uv run python -m llm2sql.cli --json "..."
uv run llm2sql --chat
```

| 옵션 | 설명 |
|------|------|
| `--chat` | 대화형 세션 |
| `-p` / `--progress` | 단계 실시간 출력 |
| `-v` / `--verbose` | route, SQL, rows |
| `--json` | 전체 결과 JSON |

### 대화 예시

```text
질문> 기능 알려줘
질문> 송정동 건물 몇 채야?     → 강서/해운대 확인
질문> 1                        → 강서구 송정동 건수
질문> 부산시에서 가장 높은 건물은?
질문> 구서동 아파트와 연산동 아파트의 특징을 비교하라
질문> 장전동과 안락동의 최고 높이 건물을 비교하라
질문> 그 아파트의 이름은?       # focus가 있을 때
질문> exit
```

---

## 질문 유형과 동작

### 1) 역할·기능·제한 / 범위 외

| 질문 예 | route |
|---------|-------|
| 기능 알려줘 | `guide_help` |
| 제한이 뭐야? | `guide_limits` |
| 안녕하세요 | `guide_greeting` |
| 오늘 날씨 어때? | `guide_out_of_scope` |

### 2) 데이터·속성 설명

| 질문 예 | route |
|---------|-------|
| 어떤 데이터가 있어? | `meta_catalog` |
| A4 컬럼 의미가 뭐야? | `meta_column` |
| 법정동명은 어떤 속성이야? | `meta_column_display` |

### 3) 모호성·확인

| 질문 예 | route | 후속 |
|---------|-------|------|
| 송정동 건물 몇 채야? | `clarify_place` | `1` / `1번` / 보기 클릭 → 구+동으로 재질의 |
| 구서동에서 제일 좋은 아파트는? | `clarify_vague` | 수치 기준 제안 |
| 하동 아파트 특징은? | `clarify_unknown_place` | — |

### 4) 특징 요약·지역/용도 비교

| 질문 예 | route |
|---------|-------|
| 구서동 아파트의 특징은? | `building_profile` (문단형) |
| 구서동 아파트와 연산동 아파트 특징 비교 | `building_profile_compare` |

- **아파트** → 용도명 **공동주택**
- 높이·건축면적 집계 시 이상값 필터 적용

### 5) 순위·최고 건물 비교

| 질문 예 | route |
|---------|-------|
| 부산시에서 가장 높은 건물은? | `building_rank_높이` |
| 부산시에서 건물면적이 제일 넓은 건물은? | `building_rank_건물면적` |
| 장전동과 안락동의 최고 높이 건물을 비교하라 | `building_rank_compare_높이` |

- 주력 테이블: `AL_D010` (`A16` 높이, `A12` 건물면적, `A14` 연면적)
- 「제일 넓은」「부산시에/에서」 등 구어 표현 지원
- 순위 답변은 컬럼코드(`A9` 등) 없이 문장으로 안내

### 6) 후속 질문 (세션)

| 질문 예 | route |
|---------|-------|
| 그 아파트의 이름은? | `followup_attr` |
| 지번은? / 높이는? | `followup_attr` |

웹 UI 또는 `--chat`에서 세션 유지 필요.

### 7) 일반 GIS 조회

라우터 적중 시 규칙 SQL. 미적중 시 RAG + Ollama → 진단·교정(`fix_common_sql_mistakes`) → 실행 → 한국어 답변.

---

## 파이프라인 구조

```text
1. clarify 번호 선택 병합 (직전 clarify_place + "1")
2. guide_qa
3. followup_qa
4. rank_compare_qa   복수 지역 최고 건물 비교
5. profile_qa        특징 요약·지역/용도 비교
6. meta_qa
7. clarify_qa
8. intent_router     건수·순위·버퍼 등
9. RAG + LLM         스키마 검색 → SQL → 검증/재생성
10. answer           실행 결과 → 한국어 (토큰 스트림 가능)
```

| 모듈 | 역할 |
|------|------|
| `engine.py` | `Llm2SqlEngine` |
| `pipeline.py` | `run_ask` / `ask` |
| `domain.py` | 구·동·용도·부산시·이상값 SQL |
| `rank_compare_qa.py` | 지역 간 최고 건물 비교 |
| `webapp/` | FastAPI + 정적 버블 UI |
| `intent_router.py` | 규칙 SQL |
| `answer.py` | 자연어·스트림·프로필 서술 |

---

## 데이터·메타데이터

| 테이블 | 용도 |
|--------|------|
| `AL_D010_26_20250704` | 부산 건물통합 (주력) |
| `AL_D198_*` | 동래/금정 용도별 (건축년수 등) |
| `AL_D060_*` | 산업단지 |
| `BND_ADM_DONG_PG` | 행정동 경계 |
| `TL_KODIS_BAS_26_202507` | 기초구역 |
| `table_metadata` / `column_metadata` | 한글 설명 |
| `llm_schema_catalog` | RAG 임베딩 |

D010 주요 컬럼: `A4` 법정동명, `A5` 지번, `A9` 용도, `A12` 건물면적, `A14` 연면적, `A16` 높이, `A24` 건물명, `A26` 지상층.

---

## 제한 사항

1. 등록된 부산 GIS 범위만. 날씨·잡담 등은 거절.
2. ‘좋은/추천’은 주관 평가 없이 수치 기준으로 유도.
3. 동일 동명이 여러 구에 있으면 후보 확인 후 진행.
4. 쓰기 SQL 차단.
5. 후속 질문은 세션·focus 건물 필요.
6. LLM 경로는 수 초~수십 초 소요 가능.
7. 단일 DB 연결 엔진은 동시 `ask`에 락/직렬화 권장(웹은 락 사용).

---

## 벤치마크·스크립트

```bash
uv run python scripts/benchmark_new10.py
uv run python scripts/smoke_engine.py
uv run python scripts/smoke_nl_queries.py
uv run python scripts/smoke_clarify.py
uv run python scripts/smoke_profile_qa.py
uv run python scripts/refresh_schema_catalog.py
```

---

## 프로젝트 구조

```text
llm2sql/
  llm2sql/
    engine.py, types.py, domain.py, pipeline.py
    webapp/           # FastAPI SSE 챗봇 + static UI
    rank_compare_qa.py
    guide_qa.py, meta_qa.py, clarify_qa.py
    profile_qa.py, followup_qa.py, session.py
    intent_router.py, answer.py, ...
  scripts/
  main.py
  pyproject.toml      # llm2sql, llm2sql-web
  .env.example
```

---

## 문제 해결

| 증상 | 확인 |
|------|------|
| `DATABASE_URL` 오류 | `.env` |
| Ollama 연결 실패 | `ollama serve`, 모델 pull |
| 임베딩 오류 | embed 모델 차원 ↔ 카탈로그 |
| 후속/번호 선택 실패 | 웹 세션 또는 `--chat` |
| 웹 UI가 옛 동작 | 서버 재시작 + Ctrl+F5 |
| 느린 응답 | `-p`로 라우터/LLM 경로 확인 |

---

## 0.1.0 변경 요약

- **`Llm2SqlEngine`**: 재사용 엔진, `AskResult`, `on_progress` / `on_token` 스트림
- **웹 챗봇**: FastAPI + 버블 UI + SSE, 로딩·스크롤·모호 보기 버튼
- **모호 동**: 번호(`1`/`1번`)·구 이름 선택 후 재질의
- **부산시 전역** 순위·「제일 넓은」 등 구어 매칭, D198 오판 교정
- **이상값 필터**: 비정상 높이·건물면적 제외
- **특징 요약**: 문단형 LLM 서술; **지역 간 특징 비교**
- **최고 건물 비교**: 예) 장전동 vs 안락동 최고 높이
- **답변 품질**: 순위·폴백에서 컬럼코드(`A9` 등) 비노출

---

## 라이선스 / 기여

개인·팀 내부 GIS 질의 실험용 프로젝트입니다. 이슈·PR은 저장소에서 환영합니다.

**저장소:** https://github.com/JeongwooPark/llm2sql
