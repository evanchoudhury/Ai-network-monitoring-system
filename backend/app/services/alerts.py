"""Persistent alert engine with deduplication and cooldowns.

An alert is created only if an identical, still-active (unacknowledged) alert
with the same ``dedup_key`` has not been raised within the cooldown window.
This prevents alert storms from a persistent condition.
"""
from __future__ import annotations

import hashlib
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import Alert, AlertCategory, Severity, utcnow

logger = get_logger("sentinel.alerts")

DEFAULT_COOLDOWN_MINUTES = 15


def make_dedup_key(category: str, source: str | None, discriminator: str) -> str:
    raw = f"{category}|{source or ''}|{discriminator}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def create_alert(
    db: Session,
    *,
    category: AlertCategory,
    severity: Severity,
    title: str,
    explanation: str,
    source: str | None = None,
    evidence: dict | None = None,
    related: dict | None = None,
    discriminator: str = "",
    cooldown_minutes: int = DEFAULT_COOLDOWN_MINUTES,
    commit: bool = True,
) -> Alert | None:
    """Create an alert unless a matching one is within the cooldown window.

    Returns the created alert, or ``None`` if suppressed by dedup/cooldown.
    """
    dedup_key = make_dedup_key(
        category.value if isinstance(category, AlertCategory) else str(category),
        source,
        discriminator or title,
    )
    cutoff = utcnow() - timedelta(minutes=cooldown_minutes)
    existing = db.scalar(
        select(Alert)
        .where(
            Alert.dedup_key == dedup_key,
            Alert.created_at >= cutoff,
        )
        .order_by(Alert.created_at.desc())
        .limit(1)
    )
    if existing is not None:
        logger.info(
            "Alert suppressed by cooldown",
            extra={"extra_fields": {"dedup_key": dedup_key, "title": title}},
        )
        return None

    alert = Alert(
        category=category,
        severity=severity,
        title=title,
        explanation=explanation,
        source=source,
        evidence=evidence,
        related=related,
        dedup_key=dedup_key,
    )
    db.add(alert)
    if commit:
        db.commit()
        db.refresh(alert)
    return alert


def acknowledge_alert(db: Session, alert_id: int, actor: str) -> Alert | None:
    alert = db.get(Alert, alert_id)
    if alert is None:
        return None
    alert.acknowledged = True
    alert.acknowledged_by = actor
    alert.acknowledged_at = utcnow()
    db.commit()
    db.refresh(alert)
    return alert


def active_alert_count(db: Session) -> int:
    from sqlalchemy import func

    return int(
        db.scalar(
            select(func.count(Alert.id)).where(Alert.acknowledged.is_(False))
        )
        or 0
    )
