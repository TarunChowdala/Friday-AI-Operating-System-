#!/usr/bin/env bash
# Start Friday infra (Postgres + Redis via Podman) then the local backend.
# Local uvicorn = desktop system controls work (volume, apps, screen, …).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BACKEND"

PG_NAME="${FRIDAY_PG_NAME:-friday-pg}"
REDIS_NAME="${FRIDAY_REDIS_NAME:-friday-redis}"

ensure_postgres() {
  if podman container exists "$PG_NAME" 2>/dev/null; then
    echo "[friday] starting $PG_NAME ..."
    podman start "$PG_NAME" >/dev/null
  else
    echo "[friday] creating $PG_NAME (postgres:16) ..."
    podman run -d --name "$PG_NAME" \
      -e POSTGRES_USER=friday \
      -e POSTGRES_PASSWORD=friday \
      -e POSTGRES_DB=friday \
      -p 5432:5432 \
      docker.io/library/postgres:16
  fi
}

ensure_redis() {
  if podman container exists "$REDIS_NAME" 2>/dev/null; then
    echo "[friday] starting $REDIS_NAME ..."
    podman start "$REDIS_NAME" >/dev/null
  else
    echo "[friday] creating $REDIS_NAME (redis:7) ..."
    podman run -d --name "$REDIS_NAME" \
      -p 6379:6379 \
      docker.io/library/redis:7
  fi
}

wait_tcp() {
  local host=$1 port=$2 label=$3
  echo -n "[friday] waiting for $label"
  for _ in $(seq 1 30); do
    if (echo >/dev/tcp/"$host"/"$port") >/dev/null 2>&1; then
      echo " — ready"
      return 0
    fi
    echo -n "."
    sleep 1
  done
  echo
  echo "[friday] ERROR: $label not reachable on $host:$port" >&2
  exit 1
}

echo "[friday] ensuring Postgres + Redis ..."
ensure_postgres
ensure_redis
wait_tcp 127.0.0.1 5432 "Postgres"
wait_tcp 127.0.0.1 6379 "Redis"

if [[ ! -d "$BACKEND/venv" ]]; then
  echo "[friday] ERROR: venv missing. Run: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$BACKEND/venv/bin/activate"

export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://friday:friday@127.0.0.1:5432/friday}"
export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"

echo "[friday] starting backend on http://0.0.0.0:8000 ..."
exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
