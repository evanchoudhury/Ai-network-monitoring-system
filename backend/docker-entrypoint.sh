#!/usr/bin/env bash
# Entrypoint: run DB migrations, then start the requested process.
set -euo pipefail

echo "[entrypoint] Running database migrations (alembic upgrade head)…"
# For Postgres, migrations manage the schema. If alembic fails (e.g. a very
# first boot race), the app's create_all fallback still ensures tables exist.
alembic upgrade head || echo "[entrypoint] alembic upgrade failed or no-op; app will ensure schema on startup."

case "${1:-api}" in
  api)
    echo "[entrypoint] Starting API (uvicorn)…"
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "${WEB_CONCURRENCY:-2}"
    ;;
  worker)
    # Dedicated worker: runs only the scheduler loop (API disabled).
    echo "[entrypoint] Starting background worker (scheduler only)…"
    exec python -c "import time; from app.workers.scheduler import start_scheduler; start_scheduler(); [time.sleep(3600) for _ in iter(int, 1)]"
    ;;
  *)
    exec "$@"
    ;;
esac
