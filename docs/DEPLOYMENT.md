# Sentinel AI — Deployment Guide

> **Never deploy publicly until** authentication secrets, database access, CORS,
> and resource limits are configured. Do not expose the database to the public
> internet. Do not enable paid resources without checking expected costs and
> confirming authorization.

## 1. Local development

See the README quick start. Backend defaults to SQLite; frontend dev server
proxies `/api` to `:8000`.

## 2. Environment configuration

Copy `.env.example` → `.env` and set at least:

| Variable | Required | Notes |
|---|---|---|
| `SECRET_KEY` | ✅ prod | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | ✅ prod | Bootstrap operator account |
| `DATABASE_URL` | ✅ prod | `postgresql+psycopg2://user:pass@host:5432/db` |
| `CORS_ORIGINS` | ✅ prod | Comma-separated frontend origins |
| `NEWSAPI_KEY`, `GOOGLE_FACTCHECK_API_KEY` | optional | Enable extra providers |
| `VITE_API_BASE_URL` | frontend build | Absolute API URL for split deploys |

Secrets are read from the environment only. A committed `.env.example` holds
**placeholders only**; never commit a real `.env` (it is git-ignored).

## 2b. Configuring live data sources (LIVE-only operation)

Sentinel AI runs **LIVE only** — it shows real collected data or an explicit
unavailable state. Configure the sources you want to observe:

### Network metrics (§ metrics sources)
Push metrics from an authorized collector (operator token required):
```bash
# Single point
curl -X POST $API/api/ingest/metrics -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"service":"prod-api","request_rate":42,"error_rate":0.01,"latency_p95_ms":120,
       "bytes_in":50000,"bytes_out":30000,"available":true}'

# Prometheus text exposition (map your metric names to our columns)
curl -X POST $API/api/ingest/prometheus -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"service":"prod-api","text":"http_requests_per_second 42\n",
       "mapping":{"request_rate":"http_requests_per_second"}}'
```
With no metrics source, the dashboard shows **NETWORK DATA SOURCE NOT CONFIGURED**.
Only authorized services are accepted; the app never scans or surveils the
network on its own.

### Global map connection events
The map plots only recorded connection events between **located** services
(services with coordinates — set them when creating the service). Record events:
```bash
curl -X POST $API/api/ingest/connections -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"connections":[{"src_service":"edge-nyc","dst_service":"edge-lon",
       "bytes_transferred":5e7,"connection_count":120,"suspicious":false}]}'
```
A connection is only ever drawn red/dashed (suspicious) when the caller sets it
from a real detector/event. No connection data → the map renders without
fabricated arcs and explains why.

### News ingestion
Default RSS feeds (BBC, NPR, Guardian, Al Jazeera) work out of the box. Set
`NEWSAPI_KEY` to also ingest NewsAPI (a "NewsAPI Top Headlines" source is
auto-seeded). Add more RSS/NewsAPI sources under **Data Sources** or
`POST /api/sources`. Failing feeds are reported per-source and never replaced
with sample articles.

### Claim-evidence provider
Local corpus evidence always works. For external fact-check evidence, set
`GOOGLE_FACTCHECK_API_KEY` to a Google Cloud **API key** (Credentials → API key,
with the *Fact Check Tools API* enabled) — **not** an OAuth 2.0 client secret
JSON. Without it, verification is honestly reported as limited to the local
corpus.

### Spam/phishing
Analyzes user-submitted messages (`POST /api/spam/analyze`) or an authorized
connected message source. With none submitted, the page shows **NO MESSAGE
SOURCE CONNECTED**. Suspicious URLs are never auto-visited.

### Verify LIVE
`GET /api/status` returns each subsystem's `configured`/`state`/freshness. The
dashboard header shows LIVE/stale/disconnected + last-updated; **System Health**
shows per-source freshness and never a green light without a real check.

## 3. Database & migrations

Production uses PostgreSQL. Apply migrations with Alembic:
```bash
cd backend
DATABASE_URL=postgresql+psycopg2://… alembic upgrade head
```
The app also runs an idempotent `create_all` on startup as a safety net, but
Alembic is the source of truth for schema changes.

> **Validated:** migrations apply cleanly on PostgreSQL 16 (18 tables) and the
> app boots and serves `/readyz = ok` against Postgres. See docs/REPORT.md.

## 4. Docker Compose (self-hosted)

```bash
cp .env.example .env    # set SECRET_KEY, ADMIN_PASSWORD
docker compose up --build -d
docker compose ps       # check health
curl -fsS localhost:8000/healthz
```
The compose stack runs Postgres (private, no published port by default), the
backend (migrations run on start), and nginx serving the SPA with `/api`
proxied to the backend. A dedicated background-worker service can be added by
running the backend image with `worker` as the command and setting
`ENABLE_SCHEDULER=false` on the API service.

## 5. Cloud deployment

### Frontend → Vercel (or any static host)
```bash
cd frontend
VITE_API_BASE_URL=https://api.yourdomain.com npm run build
# deploy ./dist   (Vercel: framework = Vite, output = dist)
```
The PWA service worker uses `NetworkOnly` for `/api`, so authenticated
responses are never stored in a shared cache.

### Backend + database → a host that supports persistent services
Vercel is **not** suitable for the persistent background worker or a
long-lived DB connection pool. Use a container/VM host plus a managed Postgres:

| Component | Suitable options |
|---|---|
| Backend (container) | Render, Railway, Fly.io, AWS ECS/App Runner, Google Cloud Run* |
| PostgreSQL (managed) | Neon, Supabase, Render Postgres, AWS RDS, Cloud SQL |

\* Cloud Run suits the API but scales to zero; run the scheduler as a separate
always-on worker (or a scheduled Cloud Run Job) rather than in-process.

**Before choosing instance sizes, check the provider's current free-tier /
credit eligibility and live pricing.** Start small (a shared-CPU container +
the smallest managed Postgres) — the deterministic pipeline is light.

### About cloud credentials in this environment
This project does **not** bundle or assume any cloud account. If your CI or
sandbox exposes provider credentials (e.g. `AWS_*` env vars), verify they
belong to the account you intend to bill **before** provisioning anything, and
never create paid resources without explicit authorization. Sentinel AI will
not provision cloud resources on your behalf.

## 5b. Background workers & scheduling

Ingestion and scanning run server-side — **no browser tab needs to be open**.
The in-process scheduler (APScheduler) runs: news ingestion, anomaly scanning,
health checks, and retention, with these guarantees:

- **No double-runs:** `max_instances=1` + `coalesce=True` per job.
- **Bounded concurrency:** a fixed thread pool sized by `WORKER_MAX_CONCURRENCY`.
- **Failures recorded:** each job catches and logs errors (structured JSON) and
  writes source `last_status`/`last_error`; one failure never crashes the loop.
- **Bounded retries / timeouts:** HTTP calls use `HTTP_TIMEOUT_SECONDS`; feeds
  that fail are skipped until the next interval (no infinite retry loop).
- **Observability:** worker state is exposed at `GET /api/status` (`workers`).
- **Restart recovery:** schedules are re-created on startup from config; no job
  state is lost because all data lives in the database.
- **Budget-aware:** scheduled AI use (only if an LLM is enabled) goes through the
  same fail-closed budget checks.

**Deployment options:**
- *Single instance:* run the backend with `ENABLE_SCHEDULER=true` (default). The
  API process also runs the scheduler.
- *Separate worker:* run a second container from the backend image with the
  `worker` command and set `ENABLE_SCHEDULER=false` on the API, so only one
  scheduler is active. Do **not** run the scheduler in two places at once.
- *Serverless API (e.g. Cloud Run that scales to zero):* the in-process
  scheduler will not run reliably — use a dedicated always-on worker or a
  platform scheduled job (e.g. Cloud Scheduler → a worker endpoint).

A static frontend host (Vercel) does **not** run background workers — the
backend/worker must run on a host that supports persistent processes.

## 6. Pre-deployment checklist

- [ ] `SECRET_KEY` set to a strong random value (not the default)
- [ ] `ADMIN_PASSWORD` changed from the default
- [ ] `DATABASE_URL` points at managed Postgres; DB **not** publicly reachable
- [ ] `CORS_ORIGINS` restricted to your frontend origin(s)
- [ ] `alembic upgrade head` run successfully
- [ ] `/healthz` and `/readyz` return healthy
- [ ] Rate limits and budget caps reviewed (`/api/budget`)
- [ ] Retention windows set appropriately (`METRIC_RETENTION_DAYS`, etc.)
- [ ] Only authorized sources/services configured
- [ ] Expected monthly cost of chosen resources estimated and approved
- [ ] Backups configured for Postgres (see below)

## 7. Backup & recovery (Postgres)

```bash
# Backup
pg_dump "$DATABASE_URL" -Fc -f sentinel-$(date +%F).dump
# Restore
pg_restore --clean --if-exists -d "$DATABASE_URL" sentinel-YYYY-MM-DD.dump
```
Schedule regular `pg_dump` (managed providers usually offer automated backups).
Metric/article data is also retention-bounded by the app to control storage.

## 8. Monitoring & troubleshooting

- **Metrics:** scrape `GET /metrics` (Prometheus format).
- **Health:** `GET /healthz`, `GET /readyz`, and the dashboard **System Health** page.
- **Logs:** structured JSON on stdout — ship to your log aggregator.
- **Common issues:**
  - `401` on admin routes → sign in; token expired.
  - Empty dashboard → no data yet; generate demo data or configure a live source.
  - News source shows `error` → check the source's URL/terms; the error is shown,
    and no data is fabricated.
  - `readyz` 503 → database unreachable; check `DATABASE_URL` and network.
