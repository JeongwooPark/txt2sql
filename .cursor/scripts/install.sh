#!/usr/bin/env bash
# llm2sql Cloud Agent 환경 install (멱등).
#
# 지속 상태(패키지·의존성·DB 데이터·Ollama 모델·임베딩)를 준비합니다.
# 환경 빌드에서는 이 스크립트가 베이스 스냅샷을 만들 때 1회 실행되어
# 결과가 스냅샷에 구워집니다. 데몬 기동은 start.sh가 담당합니다.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

log() { echo "[install] $*"; }

# ---------------------------------------------------------------------------
# 1) 시스템 패키지: PostgreSQL 16 + PostGIS + pgvector, 빌드 도구
# ---------------------------------------------------------------------------
if ! command -v psql >/dev/null 2>&1 \
    || ! ls /usr/share/postgresql/16/extension/postgis.control >/dev/null 2>&1; then
  log "apt: PostgreSQL 16 + PostGIS + pgvector 설치"
  sudo apt-get update -y
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    postgresql-16 postgresql-16-postgis-3 postgresql-16-pgvector \
    postgresql-client-16 build-essential curl ca-certificates zstd git
fi

# ---------------------------------------------------------------------------
# 2) Ollama (로컬 LLM: SQL 생성/의도 분류/답변 + 임베딩)
# ---------------------------------------------------------------------------
if ! command -v ollama >/dev/null 2>&1; then
  log "Ollama 설치"
  sudo apt-get install -y zstd >/dev/null 2>&1 || true
  curl -fsSL https://ollama.com/install.sh | sh
fi

# ---------------------------------------------------------------------------
# 3) uv + Python 3.13 의존성
# ---------------------------------------------------------------------------
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  log "uv 설치"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
log "uv sync (Python 3.13 + 의존성)"
uv sync

# ---------------------------------------------------------------------------
# 4) PostgreSQL 기동 (멱등)
# ---------------------------------------------------------------------------
log "PostgreSQL 기동"
sudo pg_ctlcluster 16 main start 2>/dev/null || sudo service postgresql start || true
for _ in $(seq 1 30); do
  pg_isready -h localhost -p 5432 >/dev/null 2>&1 && break
  sleep 1
done

# ---------------------------------------------------------------------------
# 5) 역할 + 데이터베이스 + 확장
# ---------------------------------------------------------------------------
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='llm2sql'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE ROLE llm2sql LOGIN PASSWORD 'llm2sql';"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='llm2sql'" | grep -q 1 \
  || sudo -u postgres createdb -O llm2sql llm2sql
sudo -u postgres psql -d llm2sql -c \
  "CREATE EXTENSION IF NOT EXISTS postgis; CREATE EXTENSION IF NOT EXISTS vector; GRANT ALL ON SCHEMA public TO llm2sql;"

# ---------------------------------------------------------------------------
# 6) .env (로컬 서비스 기본값). 실제 원천 DB/모델은 여기서 덮어쓰세요.
# ---------------------------------------------------------------------------
if [ ! -f "$REPO_ROOT/.env" ]; then
  log ".env 생성"
  cat > "$REPO_ROOT/.env" <<'EOF'
DATABASE_URL=postgresql://llm2sql:llm2sql@localhost:5432/llm2sql
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen3:1.7b
OLLAMA_EMBED_MODEL=mxbai-embed-large
SCHEMA_TOP_K=5
DEFAULT_LIMIT=100
EXAMPLE_TOP_K=3
SQL_MAX_RETRIES=3
USE_EXPLAIN=true
INCLUDE_SAMPLE_VALUES=true
INTENT_MODE=hybrid
INTENT_CONFIDENCE_THRESHOLD=0.55
EOF
fi

# ---------------------------------------------------------------------------
# 7) 대표 부산 GIS 샘플 데이터 적재 (멱등: seed.sql이 DROP 후 재생성)
# ---------------------------------------------------------------------------
log "샘플 GIS 데이터 적재"
PGPASSWORD=llm2sql psql -h localhost -U llm2sql -d llm2sql -v ON_ERROR_STOP=1 \
  -f "$REPO_ROOT/.cursor/seed/seed.sql" >/dev/null

# ---------------------------------------------------------------------------
# 8) Ollama 기동 + 모델 준비
# ---------------------------------------------------------------------------
if ! curl -sf http://localhost:11434/api/version >/dev/null 2>&1; then
  log "ollama serve 기동"
  nohup ollama serve >/tmp/ollama-serve.log 2>&1 &
  for _ in $(seq 1 30); do
    curl -sf http://localhost:11434/api/version >/dev/null 2>&1 && break
    sleep 1
  done
fi
ollama list 2>/dev/null | grep -q 'mxbai-embed-large' || { log "pull mxbai-embed-large"; ollama pull mxbai-embed-large; }
ollama list 2>/dev/null | grep -q 'qwen3:1.7b'        || { log "pull qwen3:1.7b";        ollama pull qwen3:1.7b; }

# ---------------------------------------------------------------------------
# 9) 스키마 카탈로그 임베딩 갱신 (RAG)
# ---------------------------------------------------------------------------
log "스키마 카탈로그 임베딩 갱신"
uv run python scripts/refresh_schema_catalog.py

log "완료"
