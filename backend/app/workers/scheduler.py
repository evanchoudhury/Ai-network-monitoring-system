"""Bounded background scheduler.

Uses APScheduler with a small thread pool and strict limits:
* ``max_instances=1`` per job (no pile-ups)
* ``coalesce=True`` (missed runs collapse into one)
* a bounded worker pool sized by ``worker_max_concurrency``

Jobs: news ingestion, anomaly scanning, health checks, and retention.
Each job opens its own DB session and swallows/records errors so a single
failure never crashes the scheduler.
"""
from __future__ import annotations

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.core.logging import get_logger
from app.database import SessionLocal

logger = get_logger("sentinel.scheduler")

_scheduler: BackgroundScheduler | None = None


def _run_news_ingest() -> None:
    from app.api.intelligence import ingest_all_sources  # reuse logic
    from app.services import pipeline

    db = SessionLocal()
    try:
        # Inline fetch loop (avoid FastAPI dependency wiring).
        from sqlalchemy import select
        from app.models import IngestionSource, SourceType
        from app.services import news as news_svc

        sources = db.scalars(
            select(IngestionSource).where(
                IngestionSource.enabled.is_(True),
                IngestionSource.source_type == SourceType.rss,
            )
        ).all()
        for src in sources:
            if not src.url or not src.authorized:
                continue
            try:
                raw = news_svc.fetch_feed_bytes(src.url)
                articles = news_svc.parse_feed(raw)
                news_svc.ingest_articles(db, src, articles)
            except Exception as exc:  # noqa: BLE001
                src.last_status = "error"
                src.last_error = str(exc)[:500]
                db.commit()
                logger.warning("News source failed",
                               extra={"extra_fields": {"source": src.name, "error": str(exc)}})
        pipeline.analyze_recent_articles(db, limit=settings.max_articles_per_batch,
                                         use_factcheck=bool(settings.google_factcheck_api_key))
    except Exception as exc:  # noqa: BLE001
        logger.error("news_ingest job failed", extra={"extra_fields": {"error": str(exc)}})
    finally:
        db.close()


def _run_anomaly_scan() -> None:
    from app.services import anomaly_runner

    db = SessionLocal()
    try:
        found = anomaly_runner.scan_all_services(db, hours=24)
        if found:
            logger.info("anomaly scan", extra={"extra_fields": {"found": found}})
    except Exception as exc:  # noqa: BLE001
        logger.error("anomaly_scan job failed", extra={"extra_fields": {"error": str(exc)}})
    finally:
        db.close()


def _run_health_check() -> None:
    from app.services import health

    db = SessionLocal()
    try:
        health.run_all(db, persist=True)
    except Exception as exc:  # noqa: BLE001
        logger.error("health_check job failed", extra={"extra_fields": {"error": str(exc)}})
    finally:
        db.close()


def _run_retention() -> None:
    from app.services import retention

    db = SessionLocal()
    try:
        retention.apply_retention(db)
    except Exception as exc:  # noqa: BLE001
        logger.error("retention job failed", extra={"extra_fields": {"error": str(exc)}})
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    if not settings.enable_scheduler:
        logger.info("Scheduler disabled by configuration.")
        return None
    if _scheduler is not None:
        return _scheduler

    executors = {"default": ThreadPoolExecutor(max_workers=settings.worker_max_concurrency)}
    job_defaults = {"coalesce": True, "max_instances": 1, "misfire_grace_time": 60}
    sched = BackgroundScheduler(executors=executors, job_defaults=job_defaults, timezone="UTC")

    sched.add_job(_run_news_ingest, "interval",
                  minutes=settings.news_ingest_interval_minutes, id="news_ingest")
    sched.add_job(_run_anomaly_scan, "interval",
                  minutes=settings.anomaly_scan_interval_minutes, id="anomaly_scan")
    sched.add_job(_run_health_check, "interval",
                  minutes=settings.health_check_interval_minutes, id="health_check")
    sched.add_job(_run_retention, "interval", hours=6, id="retention")

    sched.start()
    _scheduler = sched
    logger.info("Scheduler started with bounded worker pool.",
                extra={"extra_fields": {"max_workers": settings.worker_max_concurrency}})
    return sched


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
