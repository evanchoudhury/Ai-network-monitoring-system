# Sentinel AI — Cost Baseline & Savings Plan

> **Pricing disclaimer.** The figures below are **indicative estimates** to size
> an architecture, not quotes. Cloud prices and free-tier/credit eligibility
> change often — **verify current pricing in your provider's console before
> provisioning.** Application-level limits (below) bound *AI usage and estimated
> AI cost*; they do **not** guarantee a maximum total cloud bill.

## 1. Current cost baseline

- **Nothing is deployed by this project.** The repository contains no IaC or
  deploy manifests and provisions no cloud resources. **Current recurring cost
  from Sentinel AI = $0.** The ~$29 credit is unspent.
- **Mandatory external AI cost = $0.** The entire analysis pipeline (anomaly
  detection, claim assessment, spam scoring) is deterministic. An external LLM
  is **opt-in** (`LLM_ENABLED=false` by default) and gated by fail-closed budget
  checks if ever enabled.
- **External APIs in use:**
  - RSS feeds (BBC/NPR/Guardian/Al Jazeera): **free**.
  - NewsAPI: **optional**, free developer tier. At the default 60-min ingest
    interval it makes ~24 calls/day — well under the free-tier limit.
  - Google Fact Check Tools API: **optional/unconfigured**, free tier when used.
- **Cloud provider holding the $29:** could **not** be verified from this
  environment (no IaC, no verified provider session). I did not assume a
  provider and did not use the `AWS_*` variables present in the sandbox.

## 2. Potentially unnecessary expenses (to avoid)

- Running the backend on an **always-on managed instance** when a free-tier VM
  or a scale-to-zero option would do (but see the worker caveat below).
- A **managed Postgres** paid tier when a free Postgres tier (Neon/Supabase) or
  Postgres co-located on the same VM is enough for this workload.
- **Serverless frontends cannot run the background scheduler** — don't pay for a
  second always-on service if one small box can host API + scheduler + DB.
- Redis, Kubernetes, extra databases, message queues: **not needed** and not
  used by this project.

## 3. Application-level safeguards (already implemented)

| Safeguard | Where | Default |
|---|---|---|
| No mandatory AI (deterministic pipeline) | whole app | LLM off |
| Configurable max model requests/tokens/day | `core/budget.py` | 500 req / 200k tok |
| Fail-closed budget check | `core/budget.py` | on |
| RSS/article dedup (content hash) | `services/news.py` | on |
| Skip already-processed articles (no re-analysis) | `services/pipeline.py` | on |
| Bounded worker concurrency | `workers/scheduler.py` | 2 threads |
| No double-runs (`max_instances=1`, coalesce) | `workers/scheduler.py` | on |
| Bounded intervals (frugal defaults) | `config.py` | news 60m / anomaly 10m / health 5m |
| HTTP timeouts, single-attempt fetch (no retry loop) | `services/news.py` | 15s |
| Data retention (keeps DB small) | `services/retention.py` | metrics 14d / articles 60d / ≤20k |
| Usage logging + estimated cost reporting | `ai_usage`, `/api/budget`, `/api/usage` | on |

All intervals/retention/limits are **environment-overridable** (reversible).

## 4. Cheapest practical architecture

The app is intentionally a small monolith: **1 static frontend + 1 backend
(API + in-process scheduler) + 1 Postgres**. No extra services required.

| Component | Cheapest option | Indicative cost |
|---|---|---|
| Frontend (static SPA) | Cloudflare Pages / Vercel / Netlify free tier | **$0** |
| Backend (API + scheduler) | one small always-on container/VM | $0–$7/mo |
| PostgreSQL | Neon / Supabase free tier, **or** co-located on the VM | **$0** (free tier) |

**Two concrete patterns:**

- **Pattern A — near-$0 single VM** (cheapest): a single small always-free/low-cost
  VM runs the backend + scheduler + Postgres via `docker compose`; frontend on a
  free static host. Indicative: **~$0–5/mo** depending on VM eligibility.
  Best when you want the scheduler always running with minimal spend.
- **Pattern B — simple managed**: Vercel (frontend, free) + a small always-on
  managed backend (e.g. ~$7/mo tier) + free managed Postgres (Neon). Indicative:
  **~$5–8/mo**. Easiest to operate.

**Avoid** scale-to-zero backends (e.g. Cloud Run min-instances=0) for the
scheduler path — ingestion/anomaly jobs won't run while scaled to zero. If you
use one, run a separate always-on worker or a provider scheduled job, which adds
cost/complexity.

### Provider note (unverified credit)
If the $29 is on a specific provider, the cheapest "one small box" there is
typically: **AWS** Lightsail (~$3.50–5/mo) or a t4g.nano/micro; **GCP** an
e2-micro VM; **Azure** a B1s VM; plus a free static frontend and free Postgres
tier or Postgres on the box. Confirm the provider and live prices before
provisioning.

## 5. Is $29 sufficient?

- **Pattern A (single free/low-cost VM):** $29 likely lasts **many months to
  effectively indefinite** if the VM is within an always-free tier; a few $/mo
  otherwise → **5+ months**.
- **Pattern B (managed ~$5–8/mo):** $29 covers roughly **3.5–6 months**.
- **AI cost:** $0 unless you opt into an LLM; even then, daily/monthly caps apply.

**Conclusion:** $29 is sufficient to run Sentinel AI for a meaningful period on
the cheapest practical architecture, *provided* you use free static hosting and a
free Postgres tier (or co-locate Postgres), and enable a provider budget alert.

## 6. Protect the credit at the provider level

Application limits are not a billing cap. Also set, in your provider console:
- A **budget / spending alert** (e.g. alert at $5, $15, $25 of the $29).
- **Quotas/limits** on the services you deploy.
- Prefer **free tiers** and the **smallest** instance that runs the workload.
- Turn off any resource you are not actively using.

## 7. Recommended next steps (no paid resources created here)

1. Confirm which provider holds the $29 credit.
2. Set a provider budget alert first.
3. Deploy Pattern A or B following `docs/DEPLOYMENT.md`.
4. Verify `/healthz`, `/readyz`, and `/api/status` after deploy.
