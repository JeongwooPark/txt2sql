# llm2sql

부산 GIS(건물·행정구역·기초구역·산업단지) 데이터를 자연어로 조회하는 Python 도구입니다.  
로컬 Ollama로 SQL을 생성하고 PostgreSQL(PostGIS)에서 실행한 뒤, 한국어로 답합니다.

## 주요 기능

- 규칙 라우터 / RAG 스키마 / LLM SQL 생성
- 데이터·속성(메타) 설명, 동·용도 특징 요약
- 모호어·범위 외 질문 안내, 후속 질문(세션)
- SELECT 전용 (쓰기 금지)

## 빠른 시작

```bash
cp .env.example .env   # DATABASE_URL, OLLAMA_* 설정
uv sync
uv run python -m llm2sql.cli --chat
```

예시:

```text
기능 알려줘
현재 사용가능한 데이터는 몇개야?
구서동에서 건물면적이 가장 큰 아파트는?
그 아파트의 이름은?
```

## 환경

- Python 3.13+, `uv`
- PostgreSQL + PostGIS
- Ollama (`OLLAMA_MODEL`, `OLLAMA_EMBED_MODEL`)
