"""Operating-mode detection: DEMO vs LIVE.

The dashboard must always show which mode is active and never silently fall
back from live to fake data. Mode is derived from the presence of real
(non-demo) observations, so the signal is honest.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Metric, utcnow


def detect_mode(db: Session) -> dict:
    now = utcnow()
    recent_live_metrics = db.scalar(
        select(func.count(Metric.id)).where(
            Metric.is_demo.is_(False), Metric.timestamp >= now - timedelta(hours=24)
        )
    ) or 0
    any_live_metrics = db.scalar(
        select(func.count(Metric.id)).where(Metric.is_demo.is_(False))
    ) or 0

    has_demo = (db.scalar(select(func.count(Metric.id)).where(Metric.is_demo.is_(True))) or 0) > 0

    if recent_live_metrics > 0:
        mode = "live"
    elif any_live_metrics > 0:
        mode = "live_stale"
    elif has_demo:
        mode = "demo"
    else:
        mode = "empty"

    last_live = db.scalar(
        select(func.max(Metric.timestamp)).where(Metric.is_demo.is_(False))
    )
    return {
        "mode": mode,
        "live_metrics_24h": int(recent_live_metrics),
        "has_demo_data": has_demo,
        "last_live_metric_at": last_live.isoformat() if last_live else None,
    }
