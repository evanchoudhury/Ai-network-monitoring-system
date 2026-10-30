"""Live data-source status & freshness (replaces the old demo/live mode).

Sentinel AI runs LIVE only. This module reports, per subsystem, whether a real
source is configured and how fresh its data is — so the dashboard can show
honest states instead of ever substituting synthetic values.

Subsystem states:
  * ``fresh``          configured and received data within the freshness window
  * ``stale``          configured, has data, but the newest data is old
  * ``failed``         configured but the last collection attempt errored
  * ``not_configured`` no source configured and no data has ever arrived
  * ``no_source``      component needs an input that has not been connected
  * ``disabled``       the component is turned off by configuration
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    Article,
    IngestionSource,
    Metric,
    MonitoredService,
    SourceType,
    SpamAssessment,
    utcnow,
)


def _age_seconds(ts) -> float | None:
    if ts is None:
        return None
    now = utcnow()
    # Normalize naive timestamps (SQLite may return naive) to UTC.
    if ts.tzinfo is None:
        from datetime import timezone

        ts = ts.replace(tzinfo=timezone.utc)
    return (now - ts).total_seconds()


def network_status(db: Session) -> dict:
    services = db.scalar(select(func.count(MonitoredService.id))) or 0
    last_metric = db.scalar(select(func.max(Metric.timestamp)))
    total_metrics = db.scalar(select(func.count(Metric.id))) or 0

    if services == 0 and total_metrics == 0:
        return {
            "subsystem": "network",
            "configured": False,
            "state": "not_configured",
            "last_update": None,
            "age_seconds": None,
            "detail": "NETWORK DATA SOURCE NOT CONFIGURED",
            "instructions": (
                "Push metrics to POST /api/ingest/metrics (operator token) or "
                "POST /api/ingest/prometheus from an authorized collector. See "
                "docs/DEPLOYMENT.md § metrics sources."
            ),
        }

    age = _age_seconds(last_metric)
    if age is None:
        state = "disconnected"
        detail = "A service is configured but no metrics have been received yet."
    elif age <= settings.metric_fresh_seconds:
        state = "fresh"
        detail = "Receiving fresh metrics."
    else:
        state = "stale"
        detail = (
            f"Last metric is {int(age // 60)} min old "
            f"(fresh window {settings.metric_fresh_seconds // 60} min)."
        )
    return {
        "subsystem": "network",
        "configured": True,
        "state": state,
        "last_update": last_metric.isoformat() if last_metric else None,
        "age_seconds": int(age) if age is not None else None,
        "detail": detail,
        "services": int(services),
    }


def news_status(db: Session) -> dict:
    sources = db.scalars(
        select(IngestionSource).where(
            IngestionSource.enabled.is_(True),
            IngestionSource.source_type.in_([SourceType.rss, SourceType.newsapi]),
        )
    ).all()
    if not sources:
        return {
            "subsystem": "news",
            "configured": False,
            "state": "not_configured",
            "last_update": None,
            "age_seconds": None,
            "detail": "No news sources configured.",
            "instructions": "Add RSS sources under Data Sources (POST /api/sources).",
            "sources": [],
        }

    last_article = db.scalar(select(func.max(Article.ingested_at)))
    age = _age_seconds(last_article)
    failing = [s for s in sources if s.last_status == "error"]
    ok = [s for s in sources if s.last_status == "ok"]

    if age is None:
        state = "disconnected"
        detail = "Sources configured but no articles collected yet."
    elif age <= settings.news_fresh_seconds:
        state = "fresh" if not failing else "degraded"
        detail = "Receiving fresh articles." + (
            f" {len(failing)} source(s) failing." if failing else ""
        )
    else:
        state = "stale"
        detail = f"Newest article is {int(age // 60)} min old."

    return {
        "subsystem": "news",
        "configured": True,
        "state": state,
        "last_update": last_article.isoformat() if last_article else None,
        "age_seconds": int(age) if age is not None else None,
        "detail": detail,
        "sources": [
            {
                "name": s.name,
                "status": s.last_status or "never run",
                "last_ingested_at": s.last_ingested_at.isoformat()
                if s.last_ingested_at else None,
                "error": s.last_error,
            }
            for s in sources
        ],
        "ok_count": len(ok),
        "failing_count": len(failing),
    }


def claims_status(db: Session) -> dict:
    # Local corpus evidence is always available; external fact-check provider is
    # optional. Report honestly which evidence providers are configured.
    providers = ["local_corpus"]
    if settings.google_factcheck_api_key:
        providers.append("google_factcheck")
    return {
        "subsystem": "claims",
        "configured": True,
        "state": "fresh",
        "evidence_providers": providers,
        "external_evidence_configured": bool(settings.google_factcheck_api_key),
        "detail": (
            "Evidence limited to the local article corpus. Configure "
            "GOOGLE_FACTCHECK_API_KEY for external fact-check evidence."
            if not settings.google_factcheck_api_key
            else "Local corpus + external fact-check provider configured."
        ),
    }


def spam_status(db: Session) -> dict:
    submitted = db.scalar(
        select(func.count(SpamAssessment.id)).where(
            SpamAssessment.source == "user_submission"
        )
    ) or 0
    if submitted == 0:
        return {
            "subsystem": "spam",
            "configured": True,
            "state": "no_source",
            "detail": "NO MESSAGE SOURCE CONNECTED",
            "instructions": "Submit messages via POST /api/spam/analyze or the Spam page.",
            "analyzed_count": 0,
        }
    last = db.scalar(
        select(func.max(SpamAssessment.created_at)).where(
            SpamAssessment.source == "user_submission"
        )
    )
    return {
        "subsystem": "spam",
        "configured": True,
        "state": "active",
        "last_update": last.isoformat() if last else None,
        "analyzed_count": int(submitted),
        "detail": f"{submitted} message(s) analyzed.",
    }


def workers_status() -> dict:
    return {
        "subsystem": "workers",
        "configured": settings.enable_scheduler,
        "state": "fresh" if settings.enable_scheduler else "disabled",
        "detail": (
            "In-process scheduler enabled."
            if settings.enable_scheduler
            else "Scheduler disabled — run a dedicated worker or enable ENABLE_SCHEDULER."
        ),
        "news_ingest_interval_minutes": settings.news_ingest_interval_minutes,
        "anomaly_scan_interval_minutes": settings.anomaly_scan_interval_minutes,
    }


def overall(db: Session) -> dict:
    net = network_status(db)
    news = news_status(db)
    claims = claims_status(db)
    spam = spam_status(db)
    workers = workers_status()
    # The platform is always LIVE; the "operational" flag reflects whether at
    # least one real data source is actively fresh.
    any_fresh = net["state"] == "fresh" or news["state"] in ("fresh", "degraded")
    return {
        "live": True,
        "operational": any_fresh,
        "generated_at": utcnow().isoformat(),
        "network": net,
        "news": news,
        "claims": claims,
        "spam": spam,
        "workers": workers,
    }
