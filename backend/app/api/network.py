"""Overview, network metrics, map, anomalies, and alerts endpoints."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.database import get_db
from app.models import (
    Alert,
    Anomaly,
    Article,
    Claim,
    ClaimLabel,
    Metric,
    MonitoredService,
    Severity,
    SpamAssessment,
    SpamCategory,
    User,
    utcnow,
)
from app.schemas.schemas import AlertAckIn
from app.services import alerts as alert_svc
from app.services import anomaly_runner
from app.services import mapdata as map_svc
from app.services import metrics as metrics_svc
from app.core.budget import get_status as budget_status
from app.services import status as status_svc

router = APIRouter(tags=["network"])


def _sum_or_none(db: Session, column, since) -> float | None:
    """Sum of a metric column in the window, or None when there is NO data.

    Returns None (not 0) when no values exist, so the dashboard can show
    "No data available" rather than implying zero traffic.
    """
    val = db.scalar(
        select(func.sum(column)).where(Metric.timestamp >= since, column.isnot(None))
    )
    return float(val) if val is not None else None


def _avg_latest(db: Session, column, since) -> float | None:
    val = db.scalar(select(func.avg(column)).where(Metric.timestamp >= since, column.isnot(None)))
    return round(float(val), 2) if val is not None else None


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    now = utcnow()
    last_hour = now - timedelta(hours=1)
    last_day = now - timedelta(hours=24)

    status = status_svc.overall(db)

    # Traffic KPIs are None when no metric data exists (never a fabricated 0).
    incoming = _sum_or_none(db, Metric.bytes_in, last_day)
    outgoing = _sum_or_none(db, Metric.bytes_out, last_day)
    rps = _avg_latest(db, Metric.request_rate, last_hour)
    latency = _avg_latest(db, Metric.latency_p95_ms, last_hour)
    error_rate = _avg_latest(db, Metric.error_rate, last_hour)

    active_alerts = alert_svc.active_alert_count(db)
    anomalies_24h = db.scalar(
        select(func.count(Anomaly.id)).where(Anomaly.detected_at >= last_day)
    ) or 0
    articles_total = db.scalar(select(func.count(Article.id))) or 0
    claims_pending = db.scalar(
        select(func.count(Claim.id)).where(Claim.needs_review.is_(True))
    ) or 0
    spam_detections = db.scalar(
        select(func.count(SpamAssessment.id)).where(
            SpamAssessment.category.in_(
                [SpamCategory.suspicious, SpamCategory.high_risk, SpamCategory.phishing]
            )
        )
    ) or 0
    services_total = db.scalar(select(func.count(MonitoredService.id))) or 0

    budget = budget_status(db)

    recent_alerts = db.scalars(
        select(Alert).order_by(Alert.created_at.desc()).limit(8)
    ).all()

    return {
        "status": status,
        "generated_at": now.isoformat(),
        "network_configured": status["network"]["configured"],
        "kpis": {
            "incoming_bytes_24h": incoming,
            "outgoing_bytes_24h": outgoing,
            "requests_per_second": rps,
            "avg_latency_p95_ms": latency,
            "error_rate": error_rate,
            "active_alerts": active_alerts,
            "anomalies_24h": int(anomalies_24h),
            "articles_collected": int(articles_total),
            "claims_awaiting_review": int(claims_pending),
            "spam_detections": int(spam_detections),
            "monitored_services": int(services_total),
        },
        "ai_usage": {
            "day_requests": budget.day_requests,
            "day_tokens": budget.day_tokens,
            "estimated_day_cost_usd": budget.day_cost_usd,
            "estimated_month_cost_usd": budget.month_cost_usd,
            "note": "Costs are ESTIMATES. The core pipeline uses no external AI, "
                    "so default cost is $0.00.",
        },
        "recent_alerts": [_alert_dict(a) for a in recent_alerts],
    }


@router.get("/services")
def list_services(db: Session = Depends(get_db)):
    services = db.scalars(select(MonitoredService).order_by(MonitoredService.name)).all()
    latest = {r["service_id"]: r for r in metrics_svc.latest_per_service(db)}
    return [
        {
            "id": s.id, "name": s.name, "description": s.description,
            "country": s.country, "city": s.city,
            "lat": s.latitude, "lon": s.longitude,
            "authorized": s.authorized, "is_demo": s.is_demo,
            "latest": latest.get(s.id),
        }
        for s in services
    ]


@router.get("/metrics/history")
def metric_history(
    metric: str = Query("request_rate"),
    hours: int = Query(24, ge=1, le=720),
    service_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    try:
        data = metrics_svc.get_history(
            db, service_id=service_id, metric=metric, hours=hours
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "metric": metric, "hours": hours, "service_id": service_id,
        "points": data, "count": len(data),
        "network_status": status_svc.network_status(db),
    }


@router.get("/metrics/traffic")
def traffic_series(
    hours: int = Query(24, ge=1, le=168),
    service_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    """Inbound/outbound bandwidth series for the traffic charts."""
    bytes_in = metrics_svc.get_history(db, service_id=service_id, metric="bytes_in", hours=hours)
    bytes_out = metrics_svc.get_history(db, service_id=service_id, metric="bytes_out", hours=hours)
    return {
        "hours": hours,
        "inbound": bytes_in,
        "outbound": bytes_out,
        "network_status": status_svc.network_status(db),
    }


@router.get("/map")
def network_map(hours: int = Query(24, ge=1, le=168), db: Session = Depends(get_db)):
    data = map_svc.build_map_data(db, hours=hours)
    data["network_status"] = status_svc.network_status(db)
    return data


@router.get("/anomalies")
def list_anomalies(
    hours: int = Query(168, ge=1, le=2160),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    since = utcnow() - timedelta(hours=hours)
    rows = db.scalars(
        select(Anomaly).where(Anomaly.detected_at >= since)
        .order_by(Anomaly.detected_at.desc()).limit(limit)
    ).all()
    return [
        {
            "id": a.id, "service_id": a.service_id, "metric": a.metric_name,
            "observed_value": a.observed_value, "baseline_mean": a.baseline_mean,
            "baseline_std": a.baseline_std, "zscore": a.zscore, "method": a.method,
            "severity": a.severity.value, "explanation": a.explanation,
            "confirmed_attack": a.confirmed_attack, "is_demo": a.is_demo,
            "window_start": a.window_start.isoformat() if a.window_start else None,
            "window_end": a.window_end.isoformat() if a.window_end else None,
            "detected_at": a.detected_at.isoformat(),
        }
        for a in rows
    ]


@router.post("/anomalies/scan")
def trigger_scan(
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    found = anomaly_runner.scan_all_services(db, hours=hours)
    return {"anomalies_detected": found}


def _alert_dict(a: Alert) -> dict:
    return {
        "id": a.id, "created_at": a.created_at.isoformat(),
        "severity": a.severity.value, "category": a.category.value,
        "source": a.source, "title": a.title, "explanation": a.explanation,
        "evidence": a.evidence, "related": a.related,
        "acknowledged": a.acknowledged, "acknowledged_by": a.acknowledged_by,
        "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
    }


@router.get("/alerts")
def list_alerts(
    acknowledged: bool | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Alert).order_by(Alert.created_at.desc())
    if acknowledged is not None:
        stmt = stmt.where(Alert.acknowledged.is_(acknowledged))
    if severity:
        try:
            stmt = stmt.where(Alert.severity == Severity(severity))
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid severity")
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.limit(limit).offset(offset)).all()
    return {"total": int(total or 0), "items": [_alert_dict(a) for a in rows]}


@router.get("/alerts/{alert_id}")
def get_alert(alert_id: int, db: Session = Depends(get_db)):
    a = db.get(Alert, alert_id)
    if not a:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _alert_dict(a)


@router.post("/alerts/{alert_id}/ack")
def ack_alert(
    alert_id: int,
    payload: AlertAckIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    alert = alert_svc.acknowledge_alert(db, alert_id, payload.actor or user.username)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _alert_dict(alert)
