"""Runs the anomaly detector over stored metrics and persists results.

Bridges the pure ``anomaly`` engine with the database and the alert engine.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.logging import get_logger
from app.models import (
    Alert,
    AlertCategory,
    Anomaly,
    MonitoredService,
    Severity,
    utcnow,
)
from app.services import alerts as alert_svc
from app.services import anomaly as engine
from app.services import metrics as metrics_svc

logger = get_logger("sentinel.anomaly_runner")

MONITORED_METRICS = ["request_rate", "error_rate", "latency_p95_ms"]

_SEVERITY_ALERT_CATEGORY = {
    "request_rate": AlertCategory.traffic_spike,
    "error_rate": AlertCategory.error_rate,
    "latency_p95_ms": AlertCategory.latency,
}


def scan_service(
    db: Session, service: MonitoredService, *, hours: int = 24
) -> list[Anomaly]:
    found: list[Anomaly] = []
    for metric_name in MONITORED_METRICS:
        points = metrics_svc.get_series_points(db, service.id, metric_name, hours)
        detections = engine.detect_series(
            metric_name, points,
            threshold=settings.anomaly_zscore_threshold,
            min_baseline=settings.anomaly_min_baseline_points,
            baseline_window=settings.anomaly_baseline_window,
        )
        for det in detections:
            # Dedup by the timestamp of the anomalous point (window_end), so a
            # re-scan never duplicates a previously recorded anomaly.
            existing = db.scalar(
                select(Anomaly).where(
                    Anomaly.service_id == service.id,
                    Anomaly.metric_name == metric_name,
                    Anomaly.window_end == det.window_end,
                )
            )
            if existing is not None:
                continue
            anomaly = Anomaly(
                service_id=service.id,
                metric_name=det.metric_name,
                observed_value=det.observed_value,
                baseline_mean=det.baseline_mean,
                baseline_std=det.baseline_std,
                zscore=det.zscore,
                method=det.method,
                window_start=det.window_start,
                window_end=det.window_end,
                severity=Severity(det.severity),
                explanation=det.explanation,
                confirmed_attack=False,
                is_demo=service.is_demo,
            )
            db.add(anomaly)
            db.flush()
            found.append(anomaly)

            # Raise a correlated alert for medium+ anomalies. The discriminator
            # includes the window so distinct anomalies each alert once.
            if det.severity in ("medium", "high", "critical"):
                alert_svc.create_alert(
                    db,
                    category=_SEVERITY_ALERT_CATEGORY.get(
                        metric_name, AlertCategory.suspicious_traffic
                    ),
                    severity=Severity(det.severity),
                    title=f"Anomaly in {metric_name} on {service.name}",
                    explanation=det.explanation,
                    source=service.name,
                    evidence={
                        "observed": det.observed_value,
                        "baseline_mean": det.baseline_mean,
                        "zscore": det.zscore,
                        "detected_point_at": det.window_end.isoformat(),
                    },
                    related={"service_id": service.id, "anomaly_id": anomaly.id},
                    discriminator=f"{service.id}:{metric_name}:{det.window_end.isoformat()}",
                    cooldown_minutes=0,
                    commit=False,
                )
    db.commit()
    return found


def scan_all_services(db: Session, *, hours: int = 24, only_demo: bool = False) -> int:
    stmt = select(MonitoredService)
    if only_demo:
        stmt = stmt.where(MonitoredService.is_demo.is_(True))
    services = db.scalars(stmt).all()
    total = 0
    for svc in services:
        total += len(scan_service(db, svc, hours=hours))
    return total
