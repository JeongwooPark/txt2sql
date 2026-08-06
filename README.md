# llm2sql

부산 GIS(건물·행정구역·기초구역·산업단지) 데이터를 **자연어**로 조회하는 Python 도구입니다.  
로컬 **Ollama**로 SQL을 생성·보정하고, **PostgreSQL + PostGIS**에서 실행한 뒤 **한국어**로 답변합니다.

```text
질문 → (안내/메타/모호성/특징/라우터/RAG+LLM) → SQL 실행 → 한국어 답변
         └─ 대화형 세션 시 후속 질문(그 아파트 이름은?) 지원
```

---

## 목차

1. [특징](#특징)
2. [요구 환경](#요구-환경)
3. [설치](#설치)
4. [환경 변수](#환경-변수)
5. [사용법](#사용법)
6. [질문 유형과 동작](#질문-유형과-동작)
7. [파이프라인 구조](#파이프라인-구조)
8. [데이터·메타데이터](#데이터메타데이터)
9. [제한 사항](#제한-사항)
10. [벤치마크·스크립트](#벤치마크스크립트)
11. [프로젝트 구조](#프로젝트-구조)
12. [문제 해결](#문제-해결)

---

## 특징

| 영역 | 내용 |
|------|------|
| 조회 | 건수·순위·버퍼/교차 등 공간 조건 SELECT |
| 설명 | 데이터셋·컬럼(속성) 의미 안내 (`table_metadata` / `column_metadata`) |
| 요약 | 동·용도 기준 연면적·높이·층수·구조 통계 |
| 안전 | SELECT/WITH만 허용, 쓰기·DDL 차단 |
| 모호성 | 복수 구 동명, ‘제일 좋은’ 등 주관 표현 → 확인 요청 |
| 후속 | 직전 건물 결과 기준 「이름/지번/높이」 등 |
| 안내 | 역할·기능·제한, 범위 외 일반 질문 거절·유도 |
| 성능 | 고빈도 패턴은 규칙 라우터로 LLM 우회 |

---

## 요구 환경

- **Python** 3.13+
- **[uv](https://github.com/astral-sh/uv)** (권장)
- **PostgreSQL** + **PostGIS** (공간 테이블·GiST 인덱스)
- **Ollama** (`localhost:11434` 등)
  - 생성 모델 예: `qwen3:latest`
  - 임베딩 모델 예: `mxbai-embed-large` (카탈로그 vector 차원과 일치해야 함)
- DB에 메타·카탈로그 테이블이 준비되어 있어야 합니다  
  (`table_metadata`, `column_metadata`, `llm_schema_catalog` 등)

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

Ollama 모델 예시:

```bash
ollama pull qwen3:latest
ollama pull mxbai-embed-large
```

스키마 카탈로그 임베딩을 갱신할 때:

```bash
uv run python scripts/refresh_schema_catalog.py
```

---

## 환경 변수

`.env.example` 기준:

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `DATABASE_URL` | PostgreSQL 접속 URL | (필수) |
| `OLLAMA_HOST` | Ollama 엔드포인트 | `http://localhost:11434` |
| `OLLAMA_MODEL` | SQL 생성 모델 | `qwen3:latest` |
| `OLLAMA_EMBED_MODEL` | 스키마 RAG 임베딩 | `mxbai-embed-large` |
| `SCHEMA_TOP_K` | 카탈로그 검색 top-k | `5` |
| `DEFAULT_LIMIT` | SELECT 기본 LIMIT | `100` |

---

## 사용법

### CLI

```bash
# 단일 질문
uv run python -m llm2sql.cli "해운대구 건물 몇 채야?"

# 대화형 (후속 질문·세션 유지)
uv run python -m llm2sql.cli --chat

# 단계별 진행 로그
uv run python -m llm2sql.cli -p "구서동 아파트의 특징은?"

# SQL·원본 행 포함
uv run python -m llm2sql.cli -v "구서동에서 건물면적이 가장 큰 아파트는?"

# JSON 출력
uv run python -m llm2sql.cli --json "기능 알려줘"

# 엔트리포인트
uv run llm2sql --chat
uv run python main.py --chat
```

| 옵션 | 설명 |
|------|------|
| `--chat` | 대화형. 직전 건물 focus로 후속 질문 가능 |
| `-p` / `--progress` | 파이프라인 단계 실시간 출력 |
| `-v` / `--verbose` | route, SQL, rows 추가 출력 |
| `--json` | 전체 결과 JSON |

### 대화 예시

```text
질문> 기능 알려줘
질문> 현재 사용가능한 데이터는 몇개야?
질문> 구서동에서 제일 좋은 아파트는?
질문> 구서동에서 건물면적이 가장 큰 아파트는?
질문> 그 아파트의 이름은?
질문> 지번은?
질문> exit
```

---

## 질문 유형과 동작

### 1) 역할·기능·제한 / 범위 외

| 질문 예 | route | 동작 |
|---------|-------|------|
| 기능 알려줘 | `guide_help` | 역할·가능 기능·예시 |
| 제한이 뭐야? | `guide_limits` | 범위·쓰기 금지·세션 등 |
| 안녕하세요 | `guide_greeting` | 소개 + 짧은 사용법 |
| 오늘 날씨 어때? | `guide_out_of_scope` | 범위 외 안내 |

### 2) 데이터·속성 설명

| 질문 예 | route |
|---------|-------|
| 어떤 데이터가 있어? | `meta_catalog` |
| 사용가능한 데이터는 몇개야? | `meta_catalog_count` |
| A4 컬럼 의미가 뭐야? | `meta_column` |
| 법정동명은 어떤 속성이야? | `meta_column_display` |
| 건물 테이블이 뭐야? | `meta_table` |

동일 물리명(`A4` 등)은 **테이블마다 의미가 다를 수 있음**을 함께 안내합니다.

### 3) 모호성·확인

| 질문 예 | route |
|---------|-------|
| 송정동 건물 몇 채야? | `clarify_place` (강서/해운대 등 후보) |
| 구서동에서 제일 좋은 아파트는? | `clarify_vague` (수치 기준 제안) |
| 하동 아파트 특징은? | `clarify_unknown_place` |
| 타워팰리스 몇 채? | `clarify_unknown_term` |

### 4) 특징 요약·순위

| 질문 예 | route |
|---------|-------|
| 구서동 아파트의 특징은? | `building_profile` |
| 건물면적/연면적/높이/지상층이 가장 큰·높은… | `building_rank_*` |

- **아파트** → 속성상 용도명 **공동주택**으로 매핑  
- **건물면적** → `A12`(건축물면적), **연면적** → `A14`

### 5) 후속 질문 (세션 필요)

직전 순위 결과로 focus 건물이 잡힌 뒤:

| 질문 예 | route |
|---------|-------|
| 그 아파트의 이름은? | `followup_attr` (`A24` 건물명) |
| 지번은? / 높이는? / 자세히 | `followup_attr` / `followup_detail` |

`--chat` 없이 단일 실행만 하면 후속 질문이 이어지지 않습니다.

### 6) 일반 GIS 조회

라우터 적중 시 LLM 없이 SQL 생성. 미적중 시 스키마 RAG + Ollama 생성 → 진단·재시도 → 실행 → 한국어 문장화.

---

## 파이프라인 구조

처리 순서는 대략 다음과 같습니다.

```text
1. guide_qa      역할/기능/제한/범위 외
2. followup_qa   세션 focus 기반 후속 (있을 때)
3. meta_qa       데이터·속성 설명
4. clarify_qa    모호·미지 지명/용어
5. profile_qa    동·용도 특징 집계
6. intent_router 고빈도 COUNT/순위/버퍼 등
7. RAG + LLM     스키마 검색 → SQL 생성 → 검증/재생성
8. answer        실행 결과 → 한국어 답변
```

주요 모듈:

| 모듈 | 역할 |
|------|------|
| `pipeline.py` | `ask()` 오케스트레이션 |
| `intent_router.py` | 규칙 기반 SQL |
| `schema_retriever.py` | `llm_schema_catalog` 임베딩 검색 |
| `sql_generator.py` | Ollama SQL 생성 |
| `sql_validator.py` / `sql_fix.py` | 진단·표시명→물리명 |
| `db.py` | 읽기 전용 실행, LIMIT, geometry 생략 |
| `cli.py` | CLI·대화형 세션 |

---

## 데이터·메타데이터

앱이 기대하는 주요 공간·메타 테이블(예시):

| 테이블 | 용도 |
|--------|------|
| `AL_D010_26_20250704` | 부산 GIS 건물통합 (주력) |
| `AL_D198_*` | 동래/금정 용도별 건물 |
| `AL_D060_*` | 산업단지 |
| `BND_ADM_DONG_PG` | 행정동 경계 |
| `TL_KODIS_BAS_26_202507` | 기초구역 |
| `table_metadata` / `column_metadata` | 한글 표시명·설명 |
| `llm_schema_catalog` | RAG용 요약·임베딩 |

D010에서 자주 쓰는 속성:

| 컬럼 | 의미 |
|------|------|
| `A4` | 법정동명 |
| `A5` | 지번 |
| `A9` | 건축물용도명 |
| `A12` | 건축물면적(건물면적) |
| `A14` | 연면적 |
| `A16` | 높이(m) |
| `A24` | 건물명 |
| `A26` | 지상층 |
| `geometry` | 도형 (SRID 4326, 기본 결과에서 생략) |

---

## 제한 사항

1. **범위**: 등록된 부산 GIS 메타·공간 데이터만. 날씨·뉴스·코딩·잡담 등은 안내 후 거절.
2. **주관 판단**: ‘좋은/추천’은 직접 평가하지 않고 측정 가능 기준으로 재질문을 유도.
3. **모호 지명**: 동일 동명이 여러 구에 있으면 후보를 제시.
4. **쓰기 금지**: `INSERT`/`UPDATE`/`DELETE`/`DDL` 등 차단.
5. **건물명**: `A24`가 비어 있으면 지번·건축물ID로 식별 안내.
6. **후속 질문**: 직전 세션에 특정 건물이 있을 때만 (`--chat` 권장).
7. **LLM 경로**: 라우터 미적중 시 Ollama 호출로 수 초~수십 초 소요될 수 있음.

---

## 벤치마크·스크립트

```bash
# 신규 기능(메타/모호/특징/순위/후속) 10문항
uv run python scripts/benchmark_new10.py

# GT / 5×10 벤치 (환경·DB 필요)
uv run python scripts/benchmark_gt10.py
uv run python scripts/benchmark_5x10.py

# 스키마 카탈로그 재임베딩
uv run python scripts/refresh_schema_catalog.py

# 스모크
uv run python scripts/smoke_guide.py
uv run python scripts/smoke_meta_qa.py
uv run python scripts/smoke_clarify.py
uv run python scripts/smoke_profile_qa.py
uv run python scripts/smoke_followup.py
```

벤치마크 JSON 산출물은 `.gitignore` 대상입니다.

---

## 프로젝트 구조

```text
llm2sql/
  llm2sql/           # 패키지
    pipeline.py      # ask()
    cli.py           # CLI
    guide_qa.py      # 역할·제한·범위 외
    meta_qa.py       # 데이터/속성 설명
    clarify_qa.py    # 모호성
    profile_qa.py    # 특징 요약
    followup_qa.py   # 후속 질문
    session.py       # 대화 세션
    intent_router.py # 규칙 SQL
    schema_retriever.py
    sql_generator.py
    ...
  scripts/           # 벤치·스모크·카탈로그 갱신
  main.py
  pyproject.toml
  .env.example
```

---

## 문제 해결

| 증상 | 확인 |
|------|------|
| `DATABASE_URL이 설정되지 않았습니다` | `.env` 존재·로드 여부 |
| Ollama 연결 실패 | `ollama serve`, `OLLAMA_HOST`, 모델 pull |
| 임베딩/검색 오류 | `OLLAMA_EMBED_MODEL` 차원 ↔ `llm_schema_catalog` |
| 후속 질문이 안 됨 | `--chat` 사용, 직전 순위/단건 건물 결과 여부 |
| 한글 콘솔 깨짐 | Windows에서 UTF-8 터미널, CLI는 stdout UTF-8 재설정 시도 |
| 느린 응답 | 라우터 미적중·LLM 재생성 여부 (`-p`로 단계 확인) |

---

## 라이선스 / 기여

개인·팀 내부 GIS 질의 실험용 프로젝트입니다. 이슈·PR은 저장소에서 환영합니다.

**저장소:** https://github.com/JeongwooPark/llm2sql
