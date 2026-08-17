#!/usr/bin/env bash
# llm2sql Cloud Agent 환경 start (부팅 시마다 실행, 멱등, 즉시 반환).
#
# 데이터/모델/의존성은 install.sh(스냅샷)에서 준비됩니다.
# 여기서는 매 부팅마다 필요한 데몬(PostgreSQL, Ollama)만 기동합니다.
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"

log() { echo "[start] $*"; }

# PostgreSQL (멱등)
log "PostgreSQL 기동"
sudo pg_ctlcluster 16 main start 2>/dev/null || sudo service postgresql start || true

# Ollama (중복 방지)
if ! curl -sf http://localhost:11434/api/version >/dev/null 2>&1; then
  log "ollama serve 기동"
  nohup ollama serve >/tmp/ollama-serve.log 2>&1 &
fi

# 준비 대기
for _ in $(seq 1 30); do
  pg_isready -h localhost -p 5432 >/dev/null 2>&1 && break
  sleep 1
done
for _ in $(seq 1 30); do
  curl -sf http://localhost:11434/api/version >/dev/null 2>&1 && break
  sleep 1
done

log "서비스 준비 완료"
