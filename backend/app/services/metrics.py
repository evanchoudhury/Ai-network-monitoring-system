"""Network metric ingestion, aggregation, history, and map data.

Ingestion is source-agnostic: an authorized source pushes metric points, or a
Prometheus endpoint is scraped. Only metrics for *authorized* services are
accepted. We never attempt to observe traffic we are not permitted to.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import Metric, MetricAggregate, MonitoredService, utcnow

logger = get_logger("sentinel.metrics")

NUMERIC_METRIC_FIELDS = [
    "request_count", "request_rate", "bytes_in", "bytes_out",
    "latency_p50_ms", "latency_p95_ms", "latency_p99_ms",
    "error_count", "error_rate", "status_2xx", "status_3xx",
    "status_4xx", "status_5xx",
]


class IngestionError(Exception):
    pass


def get_or_create_service(
    db: Session, name: str, *, authorized: bool = True, is_demo: bool = False
) -> MonitoredService:
    svc = db.scalar(select(MonitoredService).where(MonitoredService.name == name))
    if svc is None:
        svc = MonitoredService(name=name, authorized=authorized, is_demo=is_demo)
        db.add(svc)
        db.flush()
    return svc


def ingest_metric(
    db: Session,
    *,
    service_name: str,
    values: dict,
    timestamp: datetime | None = None,
    source: str = "http_push",
    is_demo: bool = False,
    commit: bool = True,
) -> Metric:
    """Persist a single metric observation for an authorized service."""
    svc = get_or_create_service(db, service_name, is_demo=is_demo)
    if not svc.authorized:
        raise IngestionError(
            f"Service '{service_name}' is not authorized for monitoring."
        )

    point = Metric(
        service_id=svc.id,
        timestamp=timestamp or utcnow(),
        source=source,
        is_demo=is_demo or svc.is_demo,
    )
    for field in NUMERIC_METRIC_FIELDS:
        if field in values and values[field] is not None:
            setattr(point, field, float(values[field]))
    if "available" in values and values["available"] is not None:
        point.available = bool(values["available"])

    # Derive error_rate if not supplied but we have the pieces.
    if point.error_rate is None and point.request_count and point.error_count is not None:
        point.error_rate = (
            point.error_count / point.request_count if point.request_count else 0.0
        )

    db.add(point)
    if commit:
        db.commit()
        db.refresh(point)
    return point


def get_history(
    db: Session,
    *,
    service_id: int | None = None,
    metric: str = "request_rate",
    hours: int = 24,
    include_demo: bool = True,
) -> list[dict]:
    """Return ordered time-series points for a metric."""
    if metric not in NUMERIC_METRIC_FIELDS:
        raise ValueError(f"Unknown metric: {metric}")
    since = utcnow() - timedelta(hours=hours)
    col = getattr(Metric, metric)
    stmt = (
        select(Metric.timestamp, col, Metric.service_id, Metric.is_demo)
        .where(Metric.timestamp >= since, col.isnot(None))
        .order_by(Metric.timestamp.asc())
    )
    if service_id is not None:
        stmt = stmt.where(Metric.service_id == service_id)
    if not include_demo:
        stmt = stmt.where(Metric.is_demo.is_(False))
    rows = db.execute(stmt).all()
    return [
        {
            "timestamp": r[0].isoformat() if hasattr(r[0], "isoformat") else r[0],
            "value": float(r[1]),
            "service_id": r[2],
            "is_demo": r[3],
        }
        for r in rows
    ]


def get_series_points(
    db: Session, service_id: int, metric: str, hours: int
):
    """Return (timestamp, value) points for the anomaly engine."""
    from app.services.anomaly import Point

    rows = get_history(db, service_id=service_id, metric=metric, hours=hours)
    return [Point(timestamp=datetime.fromisoformat(r["timestamp"]), value=r["value"]) for r in rows]


def rollup_hourly(db: Session, hours: int = 48) -> int:
    """Compute hourly aggregates. Returns number of aggregate rows written."""
    since = utcnow() - timedelta(hours=hours)
    rows = db.execute(
        select(Metric).where(Metric.timestamp >= since)
    ).scalars().all()

    buckets: dict[tuple, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for m in rows:
        bucket = m.timestamp.replace(minute=0, second=0, microsecond=0)
        for field in NUMERIC_METRIC_FIELDS:
            val = getattr(m, field)
            if val is not None:
                buckets[(m.service_id, bucket)][field].append(val)

    written = 0
    for (service_id, bucket), metric_map in buckets.items():
        for metric_name, vals in metric_map.items():
            if not vals:
                continue
            existing = db.scalar(
                select(MetricAggregate).where(
                    MetricAggregate.service_id == service_id,
                    MetricAggregate.bucket == bucket,
                    MetricAggregate.resolution == "1h",
                    MetricAggregate.metric_name == metric_name,
                )
            )
            agg = existing or MetricAggregate(
                service_id=service_id,
                bucket=bucket,
                resolution="1h",
                metric_name=metric_name,
            )
            agg.count = len(vals)
            agg.avg = sum(vals) / len(vals)
            agg.min = min(vals)
            agg.max = max(vals)
            agg.sum = sum(vals)
            if existing is None:
                db.add(agg)
            written += 1
    db.commit()
    return written


def latest_per_service(db: Session) -> list[dict]:
    """Return the most recent metric row per service for dashboard/map use."""
    services = db.scalars(select(MonitoredService)).all()
    out = []
    for svc in services:
        m = db.scalar(
            select(Metric)
            .where(Metric.service_id == svc.id)
            .order_by(Metric.timestamp.desc())
            .limit(1)
        )
        if m is None:
            continue
        out.append({
            "service_id": svc.id,
            "service": svc.name,
            "is_demo": svc.is_demo,
            "timestamp": m.timestamp.isoformat(),
            "request_rate": m.request_rate,
            "error_rate": m.error_rate,
            "latency_p95_ms": m.latency_p95_ms,
            "bytes_in": m.bytes_in,
            "bytes_out": m.bytes_out,
            "available": m.available,
        })
    return out


def parse_prometheus_text(text: str) -> dict[str, float]:
    """Parse a Prometheus text-exposition payload into {metric: value}.

    A minimal parser supporting counters/gauges without labels, sufficient for
    scraping simple /metrics endpoints. Lines with labels keep the full
    ``name{labels}`` as the key.
    """
    out: dict[str, float] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.rsplit(" ", 1)
        if len(parts) != 2:
            continue
        name, value = parts
        try:
            out[name.strip()] = float(value)
        except ValueError:
            continue
    return out
