# Sentinel AI — Implementation &amp; Test Report

_Last updated: 2026-10-30. This report is deliberately honest about what is
working, what is demonstrated with synthetic data, and what remains._

## 1. What actually works (verified)

- **Backend starts** and serves the API; `/healthz`, `/readyz`, `/metrics`,
  and `/docs` respond. 43 routes mounted.
- **Database initializes** on both SQLite (dev/tests) and **PostgreSQL 16**
  (verified: `alembic upgrade head` creates 18 tables; app boots; `/readyz = ok`).
- **Network metric ingestion** (authorized services only) via single/batch push
  and a Prometheus text parser.
- **Traffic aggregation + history** queries power the dashboard charts.
- **Anomaly detection** (rolling z-score, with a series scan for history) produces
  explainable detections recording baseline mean/std, z-score, and window; an
  optional IsolationForest detector is available. Anomalies are never auto-labelled
  as attacks.
- **Alerts** persist with dedup key + cooldown; acknowledgement works and is
  audited; duplicates are suppressed.
- **RSS news ingestion** parses feeds, canonicalizes/deduplicates URLs, and groups
  articles into stories by **distinct-publisher** diversity.
- **Claim extraction + evidence assessment** runs deterministically and **abstains**
  (`insufficient_evidence` / `unverified`) when evidence is thin; produces the full
  label set (supported / contradicted / misleading / disputed / unverified /
  insufficient_evidence) with explanation, evidence, timestamps, model version,
  and limitations.
- **Spam / phishing analysis** returns a category, heuristic score (explicitly
  *not* calibrated), named triggered indicators, parsed link flags, explanation,
  and recommended action. URLs are parsed but **never fetched**.
- **Global network map** renders real DB-backed nodes/connections with zoom/pan,
  curved arcs, animated particles, node selection, severity/layer filters, a
  legend, and a pause control; honors `prefers-reduced-motion`.
- **System health, budget/usage, reports** pages are backed by live endpoints.
- **Budget controls** account usage and **fail closed**; enforcement is tested.
- **Frontend builds** (`npm run build`) and was verified rendering against the
  live backend at desktop (1600px) and mobile (390px) widths via headless
  Chromium screenshots — see `docs/screenshots/`.
- **PWA**: manifest + service worker generated; `/api` uses `NetworkOnly` (no
  caching of authenticated responses); installable with app icons.
- **Demo vs Live mode** is detected from data presence and shown in the header;
  demo data is labelled **DEMO DATA** and never silently substituted.

## 2. LIVE-only operation (no demo mode)

Demo mode has been **removed** from the running application:
- There is **no** `/api/admin/demo/generate` route and no "Generate demo data"
  UI (a test asserts the route returns 404).
- The synthetic generator now lives in `backend/tests/factories.py` — it is
  **test-only** and is never imported by `app.*` runtime code.
- No DEMO/LIVE toggle exists; the dashboard is always LIVE.
- No synthetic fallback on API error: failures surface as explicit error/stale/
  not-configured states. Traffic KPIs render `null` → "No data available",
  never a fabricated `0`.

Verified LIVE end-to-end against the real backend (SQLite): pushed 120 real
metric points + 4 traceable connection events, ingested **152 live articles**
(BBC 37, NPR 10, Guardian 45, Al Jazeera 25, NewsAPI 35), detected 3 anomalies,
and analyzed 2 real submitted messages. Header showed **LIVE · fresh**; System
Health showed per-source freshness (Network fresh, News fresh, Spam "no source"
until a message was submitted, Workers "disabled" when the scheduler was off).

## 3. What requires credentials / configuration

| Feature | Requirement |
|---|---|
| NewsAPI ingestion | `NEWSAPI_KEY` — **implemented & tested live** (auto-seeds a source; ingested 35 real articles in testing) |
| Google Fact Check evidence | A Google Cloud **API key** in `GOOGLE_FACTCHECK_API_KEY` (not an OAuth client secret JSON). Without it, returns [] and reports verification as local-corpus-only — never fabricates |
| External LLM claim extraction | `LLM_ENABLED=true` + provider key (opt-in; deterministic pipeline is the default and needs none) |
| Live network metrics | An authorized agent/Prometheus endpoint pushing to `/api/ingest/metrics` or `/api/ingest/prometheus` |
| Global map connections | Connection events pushed to `/api/ingest/connections` + services with coordinates |
| Production Postgres | `DATABASE_URL` |

## 4. Tests executed

- **Backend unit + integration: 62 tests, all passing** (`pytest`), synthetic
  fixtures only, **no paid/external calls**. Includes a dedicated
  `test_live_only.py` proving: the demo route is gone (404), empty DB reports
  *not configured* (null KPIs, not fake 0), stale data is reported stale, a
  failing feed records an error without fabricating articles, the map explains
  why it has no connections, and the `/status` endpoint reports each subsystem.
  Other coverage spans: backend startup, DB init,
  metric ingestion + aggregation + Prometheus parsing, anomaly detection (stable
  series / spike / mid-history / missing data / sensitivity / explanation), RSS
  parsing, dedup (incl. tracking-param normalization), story grouping + source
  diversity (incl. syndication), claim extraction/stance/classification +
  insufficient-evidence abstention, spam analysis, alert dedup + ack, budget
  enforcement (fail-closed), API validation, authentication, map data structure,
  and error handling.
- **Frontend:** `tsc --noEmit` + `vite build` pass; rendered pages verified via
  headless-Chromium screenshots with **zero console errors**.
- **PostgreSQL path:** migrations + boot + demo pipeline + `/readyz` verified on
  PostgreSQL 16.
- **Live-provider tests** are intentionally separated (marked `live`) and not run
  by default.

## 5. What remains incomplete / limitations

- **Spam score is not calibrated** — it is a transparent sum of indicator
  weights, surfaced as a heuristic, not a probability. Calibration would require a
  labelled dataset and evaluation.
- **Claim assessment is heuristic** (lexical overlap + negation for stance). It is
  honest about this and abstains readily; it is not a substitute for human review
  and does not resolve truth.
- **Map basemap** is a simplified world outline (110m), chosen to avoid external
  tile API keys and keep the app offline-capable and light on mobile. No
  street-level detail.
- **Docker images could not be built inside this sandbox** because the sandbox
  routes package installs through a TLS-intercepting proxy whose CA is absent from
  the base images (`pip`/`npm` fail SSL verification in-container). The Dockerfiles
  and compose file are standard and correct for a normal environment; the
  application itself was validated natively (SQLite and PostgreSQL) with real
  health checks.
- **No deployment to a public cloud was performed** — no verified cloud account or
  authorization was available, and the project does not provision paid resources
  on its own. Deployment instructions and a checklist are provided instead.
- **Rate limiter is in-process** — fine for a single instance; use Redis for
  horizontal scaling.
- **IsolationForest** is implemented but not wired into the default scan loop
  (z-score is the default); enable per-deployment if desired.

## 6. Expected cloud-resource requirements (estimate only)

These are rough starting points, **not** a guaranteed bill — confirm against the
provider's current pricing and credit eligibility before provisioning.

| Component | Suggested starting size |
|---|---|
| Backend container | 0.25–0.5 vCPU, 512 MB RAM (shared-CPU tier) |
| PostgreSQL (managed) | Smallest tier, ~1 GB storage to start (retention-bounded) |
| Frontend | Static hosting (Vercel/CDN) — negligible |
| Background worker | Reuse the backend instance, or a tiny always-on worker |

The deterministic pipeline is CPU-light and makes **zero mandatory external AI
calls**, so default estimated AI cost is **$0.00**. If an LLM is opted into, the
budget controls cap daily/monthly *estimated* spend and fail closed.

## 7. How to run locally

See the README quick start (SQLite, zero-config) or `docker compose up --build`
for the full Postgres stack. Generate demo data from the dashboard **Settings**
page (operator sign-in) or the `/api/admin/demo/generate` endpoint.

## 8. How to deploy safely

Follow `docs/DEPLOYMENT.md` and its pre-deployment checklist: set strong secrets,
keep the database private, restrict CORS, run migrations, verify health endpoints,
estimate and approve costs, and confirm only authorized sources/services are
configured before going public.
