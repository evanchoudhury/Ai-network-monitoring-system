<div align="center">

<img src="frontend/public/favicon.svg" width="88" alt="Sentinel AI logo" />

# SENTINEL AI
### Network &amp; Truth Intelligence

A practical, open-source platform for **authorized network monitoring**, **statistical anomaly detection**, **news intelligence**, **evidence-based claim assessment**, and **spam/phishing analysis** — presented in a premium security-operations-center dashboard with an interactive global network map.

</div>

---

> **LIVE only.** Sentinel AI operates on real data from configured, authorized
> sources. There is **no demo mode** and no synthetic-data fallback in the running
> app. When a source is missing or unavailable, the dashboard shows an explicit
> *not configured / stale / disconnected* state — it never fabricates traffic,
> alerts, articles, or health. It also never claims to determine the absolute
> truth of a claim; it abstains when evidence is insufficient.

## Screenshots

> Captured from the running app against the live backend (demo data).

| Overview | Global Network Map |
|---|---|
| ![Overview](docs/screenshots/overview.png) | ![Network Map](docs/screenshots/network-map.png) |

| Network Traffic | Claim Verification |
|---|---|
| ![Traffic](docs/screenshots/traffic.png) | ![Claims](docs/screenshots/claim-verification.png) |

<p align="center"><img src="docs/screenshots/mobile-overview.png" width="260" alt="Mobile overview" /> &nbsp; <img src="docs/screenshots/mobile-map.png" width="260" alt="Mobile map" /></p>

## What it does

| Module | Status | Notes |
|---|---|---|
| Network metric ingestion (HTTP push + Prometheus) | ✅ Working | Authorized services only |
| Connection-event ingestion (for the map) | ✅ Working | `POST /api/ingest/connections`, traceable |
| Traffic aggregation + charts | ✅ Working | Inbound/outbound, rps, latency, error rate; "No data" when absent |
| Global network map | ✅ Working | d3-geo, zoom/pan, real nodes/connections only |
| Statistical anomaly detection | ✅ Working | Rolling z-score + optional IsolationForest |
| Persistent alerts (dedup + cooldown + ack) | ✅ Working | Detector-generated only |
| RSS news ingestion | ✅ Working | Live BBC / NPR / Guardian / Al Jazeera |
| NewsAPI ingestion | ✅ Working | Set `NEWSAPI_KEY`; auto-seeds a source |
| Google Fact Check evidence | ⚙️ Needs API key | Requires a Google **API key** (not an OAuth client) |
| Article dedup + story grouping | ✅ Working | Distinct-publisher diversity |
| Claim extraction + evidence assessment | ✅ Working | Deterministic; abstains on weak evidence |
| Spam / phishing analysis | ✅ Working | User-submitted; URLs never auto-visited |
| Per-source status & freshness | ✅ Working | fresh / stale / disconnected / not configured |
| System health monitoring | ✅ Working | Real checks only — never a fake green light |
| Budget / usage tracking | ✅ Working | Fail-closed; estimates clearly labelled |
| Auto-refresh (bounded polling) | ✅ Working | Visible last-updated + stale indicator |
| PWA (installable, offline shell) | ✅ Working | NetworkOnly for `/api` |

See **[docs/REPORT.md](docs/REPORT.md)** for a full, honest implementation &amp; test report.

## Tech stack

- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Recharts, d3-geo (map), vite-plugin-pwa
- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2, Alembic, scikit-learn, feedparser
- **Database:** PostgreSQL (production) · SQLite (local/dev/tests)
- **Infra:** Docker Compose, Prometheus-compatible `/metrics`, structured JSON logs

## Quick start (local, zero config)

The backend defaults to SQLite, so you can run it with no database setup.

**Backend**
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
export ADMIN_PASSWORD=change-me
uvicorn app.main:app --reload --port 8000
```
API docs: http://localhost:8000/docs

**Frontend**
```bash
cd frontend
npm install
npm run dev
```
Dashboard: http://localhost:5173 (the dev server proxies `/api` → `:8000`)

**Send live data** — there is no demo mode. Point the app at real sources:

```bash
# Authenticate as the operator
TOKEN=$(curl -s -X POST localhost:8000/api/auth/token -d "username=admin&password=change-me" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# Ingest live news (default RSS feeds; add NEWSAPI_KEY for NewsAPI too)
curl -X POST localhost:8000/api/news/ingest -H "Authorization: Bearer $TOKEN"

# Push a real metric from an authorized collector
curl -X POST localhost:8000/api/ingest/metrics -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"service":"prod-api","request_rate":42,"error_rate":0.01,"latency_p95_ms":120,"bytes_in":50000,"bytes_out":30000,"available":true}'
```

**Verify LIVE status**: `curl localhost:8000/api/status` reports each subsystem's
configured/freshness state; the dashboard header shows **LIVE / stale /
disconnected** with a last-updated time, and **System Health** shows per-source
freshness. No data for a source renders as *not configured* / *No data available*,
never as a fabricated value.

## Quick start (Docker Compose — Postgres + API + web)

```bash
cp .env.example .env     # then set SECRET_KEY and ADMIN_PASSWORD
docker compose up --build
```
- Dashboard → http://localhost:8080
- API → http://localhost:8000

## Testing

```bash
cd backend && source .venv/bin/activate
pytest            # 62 tests, synthetic data only, no paid calls
```

## Documentation

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — system design, data model, request flow
- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** — local, Docker, and cloud deployment + checklist
- **[docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md)** — design tokens, components, page specs
- **[docs/BRANDING.md](docs/BRANDING.md)** — logo, icon & brand asset brief
- **[docs/REPORT.md](docs/REPORT.md)** — honest status: what works, what's demo, what needs keys

## Safety & scope

- Only monitors systems and sources the operator has **explicitly authorized**.
- Treats all ingested articles/messages as **untrusted data** — never executes
  instructions contained in them.
- Does not bypass authentication, paywalls, or access controls.
- Suspicious URLs are parsed, **never automatically visited**.
- Budget limits cap application-level model usage and *estimated* AI cost — they
  are **not** a guaranteed cap on your total cloud bill.

## License

MIT — see [LICENSE](LICENSE).
