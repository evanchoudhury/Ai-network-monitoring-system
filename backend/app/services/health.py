"""System health checks for each major component."""
from __future__ import annotations

import time
from datetime import timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Article, HealthCheck, IngestionSource, Metric, utcnow


def check_database(db: Session) -> dict:
    start = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
        latency = (time.perf_counter() - start) * 1000
        return {"component": "database", "status": "ok", "latency_ms": round(latency, 2),
                "detail": "postgresql" if not settings.is_sqlite else "sqlite"}
    except Exception as exc:  # noqa: BLE001
        return {"component": "database", "status": "down", "detail": str(exc), "latency_ms": None}


def check_collectors(db: Session) -> dict:
    """Collector health = recent successful metric ingestion."""
    recent = db.scalar(
        select(func.count(Metric.id)).where(
            Metric.timestamp >= utcnow() - timedelta(minutes=30)
        )
    )
    status = "ok" if (recent or 0) > 0 else "degraded"
    return {
        "component": "collectors",
        "status": status,
        "detail": f"{recent or 0} metric points in last 30m",
        "latency_ms": None,
    }


def check_news_sources(db: Session) -> dict:
    failing = db.scalars(
        select(IngestionSource).where(
            IngestionSource.enabled.is_(True),
            IngestionSource.last_status == "error",
        )
    ).all()
    total = db.scalar(
        select(func.count(IngestionSource.id)).where(IngestionSource.enabled.is_(True))
    ) or 0
    if total == 0:
        return {"component": "news_sources", "status": "degraded",
                "detail": "no enabled sources configured", "latency_ms": None}
    status = "ok" if not failing else "degraded"
    return {"component": "news_sources", "status": status,
            "detail": f"{len(failing)}/{total} sources failing", "latency_ms": None}


def check_ai_provider() -> dict:
    """AI provider status. Deterministic pipeline needs no provider; report
    'disabled' honestly when no external LLM is configured."""
    if not settings.llm_enabled:
        return {"component": "ai_provider", "status": "ok",
                "detail": "deterministic pipeline (no external LLM configured)",
                "latency_ms": None}
    if not settings.llm_api_key:
        return {"component": "ai_provider", "status": "degraded",
                "detail": "LLM enabled but no API key present", "latency_ms": None}
    return {"component": "ai_provider", "status": "ok",
            "detail": f"configured: {settings.llm_provider}", "latency_ms": None}


def run_all(db: Session, *, persist: bool = True) -> list[dict]:
    results = [
        check_database(db),
        check_collectors(db),
        check_news_sources(db),
        check_ai_provider(),
    ]
    if persist:
        for r in results:
            db.add(HealthCheck(
                component=r["component"], status=r["status"],
                detail=r.get("detail"), latency_ms=r.get("latency_ms"),
            ))
        db.commit()
    return results
