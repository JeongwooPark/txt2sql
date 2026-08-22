# llm2sql

**버전 0.2.1**

부산 GIS(건물·행정구역·기초구역·산업단지) 데이터를 **자연어**로 조회하는 Python 도구입니다.  
로컬 **Ollama**로 SQL을 생성·보정하고, **PostgreSQL + PostGIS**에서 실행한 뒤 **한국어**로 답변합니다.  
CLI·라이브러리 엔진·**웹 챗봇**·**지도 웹앱**을 제공합니다.

```text
질문 → 안내/메타/모호성/특징·비교/순위비교/라우터/RAG+LLM
     → SQL 실행 → 한국어 답변 (스트림 가능)
         ├─ 세션: 후속 질문, 모호 동 번호 선택(1·2번)
         └─ 지도: geometry 발행 → GeoServer WMS/WFS → 출력 레이어
```

---

## 목차

1. [특징](#특징)
2. [요구 환경](#요구-환경)
3. [설치](#설치)
4. [환경 변수](#환경-변수)
5. [엔진 API (라이브러리)](#엔진-api-라이브러리)
6. [웹 UI](#웹-ui)
7. [레이어 패널](#레이어-패널)
8. [사용법 (CLI)](#사용법-cli)
9. [질문 유형과 동작](#질문-유형과-동작)
10. [파이프라인 구조](#파이프라인-구조)
11. [데이터·메타데이터](#데이터메타데이터)
12. [제한 사항](#제한-사항)
13. [벤치마크·스크립트](#벤치마크스크립트)
14. [프로젝트 구조](#프로젝트-구조)
15. [문제 해결](#문제-해결)
16. [0.2.1 변경 요약](#021-변경-요약)
17. [0.2 변경 요약](#02-변경-요약)
18. [0.1.4 변경 요약](#014-변경-요약)
19. [0.1.3 변경 요약](#013-변경-요약)
20. [0.1.2 변경 요약](#012-변경-요약)
21. [0.1.1 변경 요약](#011-변경-요약)
22. [0.1.0 변경 요약](#010-변경-요약)

---

## 특징

| 영역 | 내용 |
|------|------|
| 조회 | 건수·순위·버퍼/교차 등 공간 조건 SELECT |
| 설명 | 데이터셋·컬럼(속성) 의미 안내 |
| 요약 | 동·용도 특징 집계 → **문단형 자연어** (LLM 서술, 실패 시 문장 폴백) |
| 비교 | 지역 간 특징 비교, **최고 높이/면적 건물** 지역 간 비교 |
| 순위 | 부산시·구·동 단위 건물면적/연면적/높이/지상층 1위 (이상값 필터) |
| 안전 | 채팅 경로는 SELECT/WITH만 허용, 쓰기·DDL 차단. 지도용 임시 테이블(`temp_*`)만 별도 발행 |
| 모호성 | 복수 구 동명 → 후보 제시 후 **`1` / `1번` 선택** 가능 |
| 후속 | 직전 건물 focus로 「이름/지번/높이」 등 |
| 안내 | 역할·기능·제한, 범위 외 거절·유도 |
| 성능 | 고빈도 패턴은 규칙 라우터로 LLM 우회 |
| 엔진 | `Llm2SqlEngine` (연결·Ollama 재사용, `on_progress` / `on_token`) |
| 웹 UI | 공통 Head/Bottom · 지도(`/map`) · 채팅(`/`, `/chat`) · 데이터 관리 골격. SSE 스트리밍·차트 |
| 지도 | GeoServer WMS(기본)·WFS, KorDB 카탈로그, 분석결과 중첩, Identify·속성 설명 |
| 레이어 | 출력 레이어에서 z-index 관리, 우클릭 삭제·속성 테이블, 분석 레이어 재사용 |

---

## 요구 환경

- **Python** 3.13+
- **[uv](https://github.com/astral-sh/uv)** (권장)
- **PostgreSQL** + **PostGIS**
- **Ollama** (`localhost:11434` 등)
  - 생성 모델 예: `qwen3:latest`
  - 임베딩 모델 예: `mxbai-embed-large` (카탈로그 vector 차원과 일치)
- DB 메타·카탈로그: `table_metadata`, `column_metadata`, `llm_schema_catalog` 등
- **GeoServer** (지도 시각화, 선택)
  - 워크스페이스 예: `korDB`, 데이터스토어 예: `KoreaDB`
  - URL이 비어 있으면 **채팅만** 동작하고 지도 발행은 건너뜁니다
- 브라우저: OpenLayers 7.x · Chart.js는 CDN으로 로드

---

## 설치

```bash
git clone https://github.com/JeongwooPark/llm2sql.git
cd llm2sql
uv sync
cp .env.example .env
# .env 에 DATABASE_URL, Ollama, (선택) GeoServer 설정 입력
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
| `EXAMPLE_TOP_K` | 예시 SQL 검색 건수 | `3` |
| `SQL_MAX_RETRIES` | SQL 재생성 횟수 | `3` |
| `USE_EXPLAIN` | EXPLAIN으로 SQL 점검 | `true` |
| `INCLUDE_SAMPLE_VALUES` | RAG에 샘플 값 포함 | `true` |
| `INTENT_MODE` | 의도 분류 `rules` / `hybrid` / `llm` | `hybrid` |
| `INTENT_CONFIDENCE_THRESHOLD` | hybrid 신뢰 임계값 | `0.55` |
| `ROUTE_DISPATCH_MODE` | 규칙 SQL `baseline` / `optimized` | `optimized` |
| `GEOSERVER_URL` | GeoServer 베이스 URL. 비우면 지도 생략 | (없음) |
| `GEOSERVER_USER` | GeoServer REST 계정 | (없음) |
| `GEOSERVER_PASSWORD` | GeoServer REST 비밀번호 (소스에 넣지 말 것) | (없음) |
| `GEOSERVER_WORKSPACE` | 워크스페이스 | `korDB` |
| `GEOSERVER_DATASTORE` | PostGIS 데이터스토어 | `KoreaDB` |
| `MAP_SCHEMA` | 임시 레이어·속성 조회 스키마 | `public` |
| `MAP_MAX_FEATURES` | 지도 SELECT LIMIT | `2000` |
| `MAP_WFS_MAX_FEATURES` | 이보다 많으면 WFS 대신 WMS | `5000` |
| `MAP_RETENTION_HOURS` | `temp_*` 레이어 TTL | `24` |
| `MAP_MAX_ANALYSIS_LAYERS` | 세션당 분석결과 레이어 상한 | `8` |

자격 증명은 `.env`만 사용합니다. 저장소에 비밀번호를 커밋하지 마세요.

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
    print(r.map)  # GeoServer가 켜져 있고 적격 질의면 레이어 정보
    r2 = engine.ask("그 아파트의 이름은?", session=session)
    print(r2.answer)
```

- `AskResult`: `ok`, `answer`, `sql`, `tables`, `rows`, `route`, `steps`, `chart`, `map` 등 (`to_dict()`)
- `map`: 발행 성공 시 `available`, `layer`, `title`, `wms_url`, `extent` 등. 실패해도 `answer`는 유지
- 세션은 호출자가 `SessionContext`를 유지 (`clarify_place` 후보·focus 건물)
- 채팅 SQL은 읽기 전용. geometry는 채팅 JSON에 넣지 않고 지도 경로에서만 주입합니다

일회성 호환: `from llm2sql import ask, load_settings` → `ask(q, load_settings())`.

---

## 웹 UI

서버 하나(`llm2sql-web`)에서 **지도**, **채팅**, **데이터 관리** 화면을 함께 제공합니다. CLI는 별도입니다.

```bash
uv sync
uv run llm2sql-web
# 또는: uv run python -m llm2sql.webapp
```

기본 바인딩은 `127.0.0.1:8000`, 코드 변경 시 uvicorn `--reload`로 재시작됩니다. 종료는 `Ctrl+C`.

모든 웹 화면은 **Head 패널**(로고·메인 메뉴)과 **Bottom 패널**(버전·스택)로 둘러싸입니다. 메인 메뉴: **지도**, **채팅**, **데이터 관리**.

| 화면 | 주소 | 설명 |
|------|------|------|
| 지도 | [http://127.0.0.1:8000/map](http://127.0.0.1:8000/map) | 레이어 · OpenLayers · 채팅 3분할 |
| 채팅 전용 | [http://127.0.0.1:8000/](http://127.0.0.1:8000/) · `/chat` | 버블 챗봇. 지도·GeoServer 없이 대화·차트만 |
| 데이터 관리 | `/data` | 개요. 업로드·메타데이터 진입 |
| 공간데이터 업로드 | `/data/upload` | Shapefile ZIP 적재 골격 (API는 후속) |
| 메타데이터 업데이트 | `/data/metadata` | 테이블·컬럼 한글명 편집 골격 (API는 후속) |
| CLI | `uv run llm2sql --chat` | 터미널 대화. 지도 UI 없음 |

채팅 전용은 `include_map=false`라 임시 GeoServer 레이어를 만들지 않습니다. 지도 화면 채팅만 `include_map=true`입니다.

### 채팅 전용

0.1.x와 같은 전체 화면 대화 UI입니다. 자연어 질문, SSE 스트리밍, 차트, 모호 동 선택, 후속 질문이 그대로 동작합니다.

### 지도 화면

왼쪽 레이어, 가운데 지도, 오른쪽 채팅의 **3분할**입니다. 채팅 기본 폭은 600px이며 드래그로 조절합니다.

1. 오른쪽에 자연어로 질문합니다. (예: `해운대구 건물 몇 채야?`)
2. 채팅에 한국어 답변이 스트리밍됩니다. 차트 제안이 있으면 Chart.js로 그립니다.
3. 적격 GIS 질의는 GeoServer에 임시 레이어(`temp_*`)로 발행되고, **분석결과 레이어**와 **출력 레이어**에 올라 지도에 표시됩니다.
4. 지도를 클릭하면 맨 위 출력 레이어부터 Identify(속성)를 조회합니다. LLM 설명은 채팅이 아니라 **팝업**에 표시됩니다.
5. KorDB 레이어를 체크하면 해당 레이어 bbox로 지도가 맞춰집니다.

같은 범위(FROM/WHERE)의 후속·특성 질의는 레이어를 다시 발행하지 않고 기존 분석 레이어를 재사용합니다.

입력은 자연어 채팅만 사용합니다. Spatial SQL 텍스트 영역은 이식하지 않았습니다. shapefile ETL은 **데이터 관리** 메뉴의 골격만 두었습니다.

### 데이터 관리

향후 기존 레이어 갱신과 신규 데이터 추가(예: 남구 용도별건물공간정보)를 이 메뉴에서 수행합니다. 0.2.1은 llm2_geodb의 업로드·메타데이터 화면을 참고한 **페이지 골격**이며, 저장·업로드 API는 아직 연결하지 않았습니다. 좌측 목록은 GeoServer KorDB 카탈로그(`/api/map/layers`)를 보여 줍니다.

### 채팅·세션

| 기능 | 설명 |
|------|------|
| 세션 | `session_id`로 후속·모호 선택 유지 |
| 모호 동 | 보기 버튼 클릭 또는 `1` / `2번` 입력 |
| 스크롤 | 새 메시지·스트림 시 하단 고정 (위로 보면 일시 중지) |
| 차트 | 특징/비교 등 답변 후 Chart.js |
| 너비 | 지도 화면에서 채팅과 지도 사이 핸들로 폭 조절 |

### HTTP API

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/` `/chat` | 채팅 전용 HTML |
| `GET` | `/map` | 지도 HTML |
| `GET` | `/data` `/data/upload` `/data/metadata` | 데이터 관리 HTML |
| `GET` | `/api/health` | 웹 프로세스 상태 |
| `POST` | `/api/session` | 새 `session_id` |
| `POST` | `/api/chat` | SSE 질의. `include_map`이 true일 때만 지도 발행 |
| `GET` | `/api/map/status` | GeoServer 연결·WMS/WFS URL |
| `GET` | `/api/map/layers` | KorDB 카탈로그 (임시 `temp_*` 제외) |
| `POST` | `/api/map/attributes` | 속성 테이블 (`temp_*` 또는 KorDB 레이어명) |
| `POST` | `/api/map/explain` | Identify·속성 테이블용 LLM 설명 (채팅에 넣지 않음) |
| `DELETE` | `/api/map/layer/{name}` | 임시 분석 레이어만 삭제. 원본 GIS 테이블은 거부 |

---

## 레이어 패널

지도 z-index의 기준은 **출력 레이어** 목록입니다. 맨 위 항목이 지도에서 가장 위에 그려집니다.

### 출력 레이어

- KorDB 또는 분석결과를 **체크**하면 여기에 추가되고 지도에 표시됩니다.
- **체크 해제**하면 출력 목록에서 빠지고 지도에서 숨겨집니다.
- ▲▼ 또는 드래그로 순서를 바꿉니다. 이 순서가 곧 겹침 순서입니다.
- 항목을 **오른쪽 클릭**하면 메뉴가 열립니다.
  - **레이어 삭제**: 분석 레이어는 지도·GeoServer 임시 테이블까지 제거. KorDB는 출력에서만 제거(카탈로그는 유지)
  - **속성 테이블 보기**: 페이징된 속성 조회

### KorDB 레이어

- KorDB·출력 레이어·속성 테이블·Identify는 `table_metadata`/`column_metadata`의 **한글 표시명**을 씁니다. 영문 원본명은 툴팁에 남습니다.

### 분석결과 레이어

- 질의마다 쌓입니다. 체크하면 출력 레이어에 올라갑니다.
- 안내·메타·모호 확인 등 지도 비적격 질의는 레이어를 만들지 않습니다.
- 건물 목록은 피처, 건수 등 집계는 행정동 경계(`BND_ADM_DONG_PG`)로 올립니다.
- 세션당 최대 `MAP_MAX_ANALYSIS_LAYERS`(기본 8)개. 새 대화 시 정리, `MAP_RETENTION_HOURS` 후 TTL 삭제
- 같은 FROM/WHERE 범위의 후속 질문은 레이어를 재사용합니다.
- **모두 지우기**는 섹션 맨 아래에 있습니다.

### 배경지도

OpenStreetMap, Carto Dark, ESRI Imagery **최대 1개**만 켤 수 있습니다.

- 하나를 체크하면 나머지는 해제됩니다.
- 켜져 있는 항목을 다시 끄면 배경 없이 분석/KorDB만 볼 수 있습니다.
- 기본값은 OpenStreetMap입니다. 배경은 항상 출력 레이어보다 아래(z-index 0)입니다.

### 스타일·렌더링

| 항목 | 설명 |
|------|------|
| WMS | 기본. GeoServer가 타일을 그립니다 |
| WFS | 건수가 `MAP_WFS_MAX_FEATURES` 이하일 때 벡터로 표시 |
| 테마 | 기본 / 컬러풀 / 지구본 / 모던 |
| 스타일 편집 | 채우기·선·두께·투명도 (분석 레이어) |

---

## 사용법 (CLI)

CLI는 채팅과 같은 엔진을 쓰며 **웹 UI와 별개**입니다. 지도 화면은 브라우저 `/map` 전용입니다.

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
| `--json` | 전체 결과 JSON (`map` 포함 가능) |

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

| 질문 예 | route | 지도 |
|---------|-------|------|
| 기능 알려줘 | `guide_help` | 없음 |
| 제한이 뭐야? | `guide_limits` | 없음 |
| 안녕하세요 | `guide_greeting` | 없음 |
| 오늘 날씨 어때? | `guide_out_of_scope` | 없음 |

### 2) 데이터·속성 설명

| 질문 예 | route | 지도 |
|---------|-------|------|
| 어떤 데이터가 있어? | `meta_catalog` | 없음 |
| A4 컬럼 의미가 뭐야? | `meta_column` | 없음 |
| 법정동명은 어떤 속성이야? | `meta_column_display` | 없음 |

### 3) 모호성·확인

| 질문 예 | route | 후속 |
|---------|-------|------|
| 송정동 건물 몇 채야? | `clarify_place` | `1` / `1번` / 보기 클릭 → 구+동으로 재질의 |
| 구서동에서 제일 좋은 아파트는? | `clarify_vague` | 수치 기준 제안 |
| 하동 아파트 특징은? | `clarify_unknown_place` | — |

확인이 끝나기 전에는 지도를 발행하지 않습니다.

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

### 7) 일반 GIS 조회 → 지도

라우터 적중 시 규칙 SQL. 미적중 시 RAG + Ollama → 진단·교정(`fix_common_sql_mistakes`) → 실행 → 한국어 답변.

성공한 SELECT는 다음처럼 지도에 올립니다.

1. geometry가 없으면 SELECT에 주입하거나, 집계면 행정 경계와 조인
2. `CREATE UNLOGGED TABLE temp_[hex]` + GIST
3. GeoServer 피처타입 등록
4. 웹이 TileWMS(또는 조건에 맞는 WFS)로 출력 레이어에 추가
5. TTL(`MAP_RETENTION_HOURS`) 후 임시 레이어 정리

GeoServer가 꺼져 있거나 발행에 실패해도 **채팅 답변은 그대로** 나갑니다.

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
11. attach_map       적격 SQL → 임시 테이블 + GeoServer (실패 무시)
```

| 모듈 | 역할 |
|------|------|
| `engine.py` | `Llm2SqlEngine` |
| `pipeline.py` | `run_ask` / `ask` → `_with_map` |
| `domain.py` | 구·동·용도·부산시·이상값 SQL |
| `rank_compare_qa.py` | 지역 간 최고 건물 비교 |
| `map/` | SQL wrap, 발행, LayerStack, REST, GeoServer 클라이언트 |
| `webapp/` | FastAPI + 3분할 UI + OpenLayers |
| `intent_router.py` | 규칙 SQL |
| `answer.py` | 자연어·스트림·프로필 서술 |

채팅 경로의 `assert_readonly_sql`은 그대로입니다. 지도 DDL은 안전한 `temp_*` 이름에만 적용됩니다.

---

## 데이터·메타데이터

| 테이블 | 용도 |
|--------|------|
| `AL_D010_26_20250704` | 부산 건물통합 (주력) |
| `AL_D198_*` | 동래/금정 용도별 (건축년수 등) |
| `AL_D060_*` | 산업단지 |
| `BND_ADM_DONG_PG` | 행정동 경계 (건수 등 집계 지도) |
| `TL_KODIS_BAS_26_202507` | 기초구역 |
| `table_metadata` / `column_metadata` | 한글 설명 |
| `llm_schema_catalog` | RAG 임베딩 |

D010 주요 컬럼: `A4` 법정동명, `A5` 지번, `A9` 용도, `A12` 건물면적, `A14` 연면적, `A16` 높이, `A24` 건물명, `A26` 지상층.

원본 KorDB 테이블은 삭제 API가 거부합니다. 지울 수 있는 것은 `temp_[0-9a-f]{8,32}` 뿐입니다.

---

## 제한 사항

1. 등록된 부산 GIS 범위만. 날씨·잡담 등은 거절.
2. ‘좋은/추천’은 주관 평가 없이 수치 기준으로 유도.
3. 동일 동명이 여러 구에 있으면 후보 확인 후 진행.
4. 채팅 SQL 쓰기 차단. 지도 임시 테이블만 서버가 생성·삭제.
5. 후속 질문은 세션·focus 건물 필요.
6. LLM 경로는 수 초~수십 초 소요 가능.
7. 단일 DB 연결 엔진은 동시 `ask`에 락/직렬화 권장(웹은 락 사용).
8. GeoServer 미설정·다운 시 지도만 생략되고 채팅은 유지.
9. 배경지도는 동시에 여러 장을 켤 수 없음 (0개 또는 1개).

---

## 벤치마크·스크립트

```bash
uv run python scripts/benchmark_new10.py
uv run python scripts/smoke_engine.py
uv run python scripts/smoke_nl_queries.py
uv run python scripts/smoke_clarify.py
uv run python scripts/smoke_profile_qa.py
uv run python scripts/refresh_schema_catalog.py

# 지도
uv run python scripts/test_map_sql.py      # wrap·적격성·GS 실패 시 채팅 유지
uv run python scripts/test_map_layers.py   # 스택·z-index·이름 검증
node scripts/test_map_stack.mjs            # 프론트 LayerStack
```

---

## 프로젝트 구조

```text
llm2sql/
  llm2sql/
    engine.py, types.py, domain.py, pipeline.py
    map/                 # 발행·GeoServer·레이어 스택·/api/map
    webapp/
      app.py             # FastAPI SSE + map 라우터
      static/
        index.html       # 채팅 (`/`, `/chat`)
        map.html         # 지도 3분할 (`/map`)
        data.html        # 데이터 관리 개요 (`/data`)
        data_upload.html
        data_metadata.html
        js/site.js       # Head 메뉴
        js/data.js       # KorDB 목록
        js/map/          # OpenLayers 코어·레이어 UI·Identify
    rank_compare_qa.py
    guide_qa.py, meta_qa.py, clarify_qa.py
    profile_qa.py, followup_qa.py, session.py
    intent_router.py, answer.py, ...
  scripts/
    test_map_sql.py, test_map_layers.py, test_map_stack.mjs
  main.py
  pyproject.toml         # llm2sql, llm2sql-web
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
| 웹 UI가 옛 동작 | 서버 재시작 + Ctrl+F5 (정적 `?v=` 캐시). 지도 `/map`, 채팅 `/chat`, 데이터 `/data` |
| 느린 응답 | `-p`로 라우터/LLM 경로 확인 |
| 지도가 안 나옴 | `GEOSERVER_URL`·계정, `/api/map/status`, GeoServer 워크스페이스 |
| 채팅은 되는데 레이어가 없음 | 안내/메타/모호 질의는 지도를 만들지 않음. 배너 메시지 확인 |
| KorDB 목록이 비어 있음 | GeoServer 레이어 REST, `korDB` 워크스페이스 |
| 속성 테이블 실패 | 분석은 `temp_*`, KorDB는 카탈로그에 있는 이름만 허용 |
| 원본 테이블 삭제 거부 | 정상. `DELETE /api/map/layer`는 임시 레이어만 |

---

## 0.2.1 변경 요약

- **버전 번호**: 잘못 표기한 1.2를 **0.2**, 1.4를 **0.2.1**로 정정
- **사이트 프레임**: 모든 웹 화면에 Head(메인 메뉴)와 Bottom 패널. 메뉴는 지도·채팅·데이터 관리
- **데이터 관리 골격**: `/data`, `/data/upload`, `/data/metadata`. 기존 갱신·신규 추가(남구 용도별건물공간정보 등)는 후속. KorDB 목록만 표시
- **분석결과 레이어 UI**: 「모두 지우기」를 섹션 맨 아래로 이동해 제목이 한 줄로 유지
- **지도 고도화**: WMS 기본 + WFS 선택, ImageWMS(분석)/TileWMS(KorDB), KorDB 체크 시 bbox fit, 라벨·SLD
- **레이어 수명**: 세션당 최대 8개, 새 대화 시 cleanup, 24h TTL. 같은 FROM/WHERE면 후속 질의에서 레이어 재사용
- **Identify·속성 테이블**: LLM 설명을 채팅이 아니라 팝업에 표시 (`POST /api/map/explain`)
- **채팅 폭**: 지도 화면 기본 600px, 드래그 조절
- **SQL**: FROM 별칭이 WHERE/ON을 테이블로 오인하던 문제 수정, 건물명 조회 geometry wrap, COUNT→피처, 비교 UNION ALL
- **설정**: `MAP_MAX_ANALYSIS_LAYERS` 등. 비밀번호는 `.env`만
- **테스트**: `scripts/test_map_sql.py`, `test_map_layers.py`, `test_map_explain.py`, `scripts/smoke_map.py`

---

## 0.2 변경 요약

- **웹 UI 이원화**: 채팅 전용(`/`, `/chat`)과 지도 3분할(`/map`)을 같은 `llm2sql-web`에서 제공. CLI는 기존 유지
- **지도 웹앱**: 레이어 패널 · OpenLayers 지도 · 기존 SSE 채팅을 한 화면에 배치
- **질의 → 지도**: 성공한 GIS SELECT에 geometry를 넣어 `temp_*` UNLOGGED 테이블로 발행, GeoServer WMS(기본)/WFS
- **KorDB**: 카탈로그 체크 시 출력 레이어·지도에 추가, 해제 시 출력에서 제거
- **출력 레이어**: z-index의 유일한 기준. ▲▼·드래그, 우클릭(레이어 삭제 · 속성 테이블 보기)
- **배경지도**: OSM / Carto Dark / ESRI Imagery 중 최대 1개 (전부 끄기 가능)
- **안전**: 채팅은 읽기 전용 유지. 원본 KorDB 테이블 삭제 거부. GeoServer 실패 시 채팅 유지
- **TTL**: `MAP_RETENTION_HOURS` 후 임시 레이어 정리
- **설정**: `GEOSERVER_*`, `MAP_*` (비밀번호는 `.env`만)
- **테스트**: `scripts/test_map_sql.py`, `test_map_layers.py`, `test_map_stack.mjs`

---

## 0.1.4 변경 요약

- **지명 사전**: 부산 법정동·행정동·구군 최장일치(트라이). 구서역·공동주택·짧은 리 오탐 방지
- **공간 질의**: 행정동 경계 교차, 버퍼, 기초구역, 법정동→행정동 분배·구성 목록(예: 연산동 → 연산1~9동)
- **임계·단위**: 높이·층·연면적·평 환산, 행정동에도 동일 적용. 아파트는 공동주택(A9)
- **라우팅**: 안내를 의도분류 LLM보다 먼저, 고신뢰 규칙은 LLM 생략, 건수·순위·연도표는 템플릿 답변
- **기타**: D198 연도/구간 후속, 건물명+사용승인일, 카탈로그 전 속성, 신규 50문항 스모크

## 0.1.3 변경 요약

- **내부 정리**: 파이프라인 결과 dict·차트/안내 분기 중복 제거, Ollama 호출을 `llm.py`로 통일, RAG SQL 루프는 `rag_sql`과 공유
- **설정**: `Settings.from_mapping` / `load_settings` 로딩 경로 통합
- **프로필**: 용적율·건폐율 집계, 지역 전체 vs 산업단지 내 비교
- **차트**: 비교 차트에 평균 용적율 시리즈 지원
- **문서**: `llm2_geodb` 대비 고도화 비교(`docs/고도화_llm2_geodb_to_llm2sql.md`)

## 0.1.2 변경 요약

- **라우트 디스패치 최적화**: `try_route` 1회 + early allowlist + deferred 재사용 (`route_dispatch`, 기본 `optimized`)
- **건물명 조회**: 단지명·속성 후속(주소/지번 등), 순위 top-N·구 필터 개선
- **산업단지**: 단지명 기준 건수, 구 코드 필터, 단지 내 건물, 이름 후속
- **차트**: 시리즈 필터(예: 높이만) 지원
- **벤치**: `scripts/benchmark_route_opt.py`로 baseline vs optimized 평가

## 0.1.1 변경 요약

- **하이브리드 의도 분류**: 규칙 + LLM (`INTENT_MODE=hybrid`)로 질의 경로 정확도 개선
- **차트**: 특징/비교/용도 답변 후 Chart.js 시각화, 유형 변경·도움말
- **데이터셋 요약**: 특정 테이블명 요약 시 스키마 나열 대신 건수·상위 용도 등 요약
- **메타/프로필 라우팅**: 카탈로그·데이터셋 내용·용도 개요·부산시 전역 대비 비교 오분류 수정
- **기타**: RAG/예시 스토어·벤치마크 스크립트, 웹 UI 차트 연동

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
