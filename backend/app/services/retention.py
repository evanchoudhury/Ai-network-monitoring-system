"""Data-retention enforcement.

Deletes data older than the configured retention windows and trims the article
table to a maximum size. Keeps the database bounded on limited cloud storage.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Article, HealthCheck, Metric, utcnow


def apply_retention(db: Session) -> dict:
    now = utcnow()
    metric_cutoff = now - timedelta(days=settings.metric_retention_days)
    article_cutoff = now - timedelta(days=settings.article_retention_days)

    deleted_metrics = db.execute(
        delete(Metric).where(Metric.timestamp < metric_cutoff)
    ).rowcount or 0
    deleted_articles = db.execute(
        delete(Article).where(Article.ingested_at < article_cutoff)
    ).rowcount or 0
    deleted_health = db.execute(
        delete(HealthCheck).where(HealthCheck.checked_at < now - timedelta(days=7))
    ).rowcount or 0

    # Trim to max_stored_articles (oldest first).
    total_articles = db.scalar(select(func.count(Article.id))) or 0
    trimmed = 0
    if total_articles > settings.max_stored_articles:
        excess = total_articles - settings.max_stored_articles
        old_ids = db.scalars(
            select(Article.id).order_by(Article.ingested_at.asc()).limit(excess)
        ).all()
        if old_ids:
            trimmed = db.execute(
                delete(Article).where(Article.id.in_(old_ids))
            ).rowcount or 0

    db.commit()
    return {
        "metrics": int(deleted_metrics),
        "articles": int(deleted_articles) + int(trimmed),
        "health_checks": int(deleted_health),
    }
