# Sentinel AI — Architecture

## Overview

Sentinel AI is a modular monolith: one FastAPI backend with clearly separated
service modules, one React SPA frontend, one relational database, and an
in-process scheduler for background work. This keeps operations simple and cheap
while remaining easy to split into separate services later if needed.

```
┌──────────────┐     HTTPS/JSON      ┌─────────────────────────────────────────┐
│  React SPA   │ ──────────────────► │              FastAPI backend             │
│ (Vite, PWA)  │ ◄────────────────── │                                          │
└──────────────┘                     │  api/        routers (auth, ingest,      │
      │                              │              network, intelligence, ops) │
      │ /metrics (Prom)              │  services/   engines (see below)         │
      ▼                              │  core/       security, budget, ratelimit │
┌──────────────┐                     │  workers/    APScheduler (bounded)       │
│ Prometheus / │ ──push/scrape──►    │  models/     SQLAlchemy ORM              │
│ metric agents│                     └───────────────┬──────────────────────────┘
└──────────────┘                                     │
                                                      ▼
                                        ┌──────────────────────────┐
                                        │ PostgreSQL (prod)         │
                                        │ SQLite (dev/test)         │
                                        └──────────────────────────┘
```

## Backend modules

### `app/services/` — analysis engines (pure where possible)
| Module | Responsibility |
|---|---|
| `metrics.py` | Ingest/aggregate/query time-series; Prometheus text parsing |
| `anomaly.py` | Pure z-score + IsolationForest detectors (unit-testable, no DB) |
| `anomaly_runner.py` | Runs detectors over stored metrics, persists anomalies, raises alerts |
| `news.py` | RSS parsing, URL canonicalization, dedup, story grouping, evidence retrieval |
| `claims.py` | Pure claim extraction, entity extraction, stance, classification |
| `pipeline.py` | Orchestrates extraction → evidence → assessment → persistence |
| `spam.py` | Pure rule-based spam/phishing scoring with named indicators |
| `alerts.py` | Alert creation with dedup key + cooldown; acknowledgement |
| `mapdata.py` | Builds the global-map payload from real DB state |
| `health.py` | Per-component health checks |
| `retention.py` | Enforces retention windows and max-stored caps |
| `mode.py` | Derives DEMO vs LIVE mode from data presence |
| `demo.py` | Generates synthetic, clearly-flagged demo data; exercises real pipelines |

Pure modules (`anomaly`, `claims`, `spam`) contain no database access, so they
are fast and deterministic to unit-test with synthetic inputs.

### `app/core/`
- `security.py` — bcrypt password hashing, JWT access tokens, `get_current_user` / `require_admin`.
- `budget.py` — usage accounting and **fail-closed** budget checks.
- `ratelimit.py` — in-process sliding-window limiter (swap for Redis to scale out).
- `logging.py` — structured JSON logs.

### `app/api/` — routers (mounted under `/api`)
`auth`, `ingest` (admin), `network` (overview/map/metrics/anomalies/alerts),
`intelligence` (news/claims/spam), `ops` (sources/health/budget/reports/admin).

## Data model

17 tables grouped by domain (see `app/models/models.py`):

- **Monitoring:** `monitored_services`, `metrics`, `metric_aggregates`, `network_connections`
- **Sources:** `ingestion_sources`
- **News/claims:** `stories`, `articles`, `claims`, `evidence`, `claim_assessments`
- **Spam:** `spam_assessments`
- **Detections:** `anomalies`, `alerts`
- **Ops:** `health_checks`, `ai_usage`, `audit_events`, `users`

Indexes cover the hot paths: timestamps, foreign keys, source identifiers, and
status/severity columns. Constraints include unique content hashes (article
dedup), unique `(name, source_type)` sources, and unique metric-aggregate keys.
Migrations are managed by Alembic (`backend/alembic/`).

## Key design decisions

- **Deterministic by default, AI optional.** All core analysis (anomaly,
  claims, spam) uses interpretable rules + classical ML. No external LLM is
  required, guaranteeing zero mandatory AI spend. An LLM can be *opted into* via
  config without changing the contract.
- **Abstention over confidence.** The claim engine returns
  `insufficient_evidence` / `unverified` rather than guessing. Truth is never
  inferred from publisher reputation, popularity, or model confidence.
- **Source diversity, not duplication.** Stories count *distinct publishers*;
  syndicated duplicates do not inflate corroboration.
- **Map honesty.** Only services with real coordinates are plotted; a connection
  is only marked suspicious when backed by a recorded flag. Unlocated services
  are reported separately, never given fabricated positions.
- **Self-contained map renderer.** A bundled world TopoJSON rendered with d3-geo
  (SVG) was chosen over a tiled library (e.g. MapLibre GL) to avoid external
  tile API keys, work offline, and stay light on Android. The trade-off —
  no street-level basemap — is acceptable for a global activity view.
- **Bounded workers.** APScheduler runs with a small thread pool,
  `max_instances=1`, and `coalesce=True`; each job owns its DB session and
  records errors instead of crashing the scheduler.

## Request flow example (claim analysis)

1. `POST /api/claims/analyze` (rate-limited) stores the submission as an Article
   (content treated as untrusted data).
2. `pipeline.analyze_article` → `claims.extract_claims` extracts check-worthy
   sentences (preserving exact wording) and entities.
3. `news.retrieve_local_evidence` (+ optional Google Fact Check API) gathers
   evidence from configured sources, counting each publisher once.
4. `claims.classify` compares supporting vs contradicting evidence and **abstains**
   when below the minimum-evidence threshold.
5. Evidence + a structured `ClaimAssessment` (label, explanation, limitations,
   model version) are persisted; a `claim_conflict` alert is raised for
   disputed/contradicted claims.

## Observability

- `/healthz` (liveness), `/readyz` (DB readiness), `/metrics` (Prometheus).
- Structured JSON logs with request instrumentation (count + latency histogram).
- `audit_events` records sensitive administrative actions.
