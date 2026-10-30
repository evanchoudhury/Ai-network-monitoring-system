"""Operational endpoints: sources, health, budget/usage, reports, admin."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import require_admin
from app.database import get_db
from app.models import (
    AIUsage,
    Alert,
    Anomaly,
    Article,
    AuditEvent,
    Claim,
    HealthCheck,
    IngestionSource,
    Metric,
    MonitoredService,
    SourceType,
    SpamAssessment,
    User,
    utcnow,
)
from app.schemas.schemas import ServiceIn, SourceIn
from app.services import health as health_svc
from app.services import retention as retention_svc
from app.core.budget import get_status as budget_status
from app.services import status as status_svc

router = APIRouter(tags=["ops"])


# --------------------------- Sources -------------------------------------- #
@router.get("/sources")
def list_sources(db: Session = Depends(get_db)):
    rows = db.scalars(select(IngestionSource).order_by(IngestionSource.name)).all()
    return [
        {
            "id": s.id, "name": s.name, "source_type": s.source_type.value,
            "url": s.url, "enabled": s.enabled, "authorized": s.authorized,
            "last_status": s.last_status, "last_error": s.last_error,
            "last_ingested_at": s.last_ingested_at.isoformat() if s.last_ingested_at else None,
            "config": s.config,
        }
        for s in rows
    ]


@router.post("/sources", status_code=201)
def create_source(
    payload: SourceIn, db: Session = Depends(get_db), user: User = Depends(require_admin)
):
    existing = db.scalar(
        select(IngestionSource).where(
            IngestionSource.name == payload.name,
            IngestionSource.source_type == SourceType(payload.source_type),
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Source already exists")
    src = IngestionSource(
        name=payload.name, source_type=SourceType(payload.source_type),
        url=payload.url, config=payload.config, enabled=payload.enabled,
        authorized=payload.authorized,
    )
    db.add(src)
    db.add(AuditEvent(actor=user.username, action="create_source", target=payload.name))
    db.commit()
    db.refresh(src)
    return {"id": src.id, "name": src.name}


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(
    source_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)
):
    src = db.get(IngestionSource, source_id)
    if not src:
        raise HTTPException(status_code=404, detail="Source not found")
    db.add(AuditEvent(actor=user.username, action="delete_source", target=src.name))
    db.delete(src)
    db.commit()


@router.post("/services", status_code=201)
def create_service(
    payload: ServiceIn, db: Session = Depends(get_db), user: User = Depends(require_admin)
):
    existing = db.scalar(select(MonitoredService).where(MonitoredService.name == payload.name))
    if existing:
        raise HTTPException(status_code=409, detail="Service already exists")
    svc = MonitoredService(
        name=payload.name, description=payload.description,
        latitude=payload.latitude, longitude=payload.longitude,
        country=payload.country, city=payload.city, authorized=payload.authorized,
    )
    db.add(svc)
    db.add(AuditEvent(actor=user.username, action="create_service", target=payload.name))
    db.commit()
    db.refresh(svc)
    return {"id": svc.id, "name": svc.name}


# --------------------------- Health --------------------------------------- #
@router.get("/health")
def health(db: Session = Depends(get_db)):
    checks = health_svc.run_all(db, persist=False)
    overall = "ok"
    if any(c["status"] == "down" for c in checks):
        overall = "down"
    elif any(c["status"] == "degraded" for c in checks):
        overall = "degraded"
    last_errors = db.scalars(
        select(HealthCheck).where(HealthCheck.status != "ok")
        .order_by(HealthCheck.checked_at.desc()).limit(5)
    ).all()
    return {
        "overall": overall,
        "status": status_svc.overall(db),
        "components": checks,
        "last_errors": [
            {"component": e.component, "status": e.status, "detail": e.detail,
             "at": e.checked_at.isoformat()}
            for e in last_errors
        ],
        "generated_at": utcnow().isoformat(),
    }


# --------------------------- Budget / usage ------------------------------- #
@router.get("/budget")
def budget(db: Session = Depends(get_db)):
    status = budget_status(db)
    return {
        "within_budget": status.within_budget,
        "day_requests": status.day_requests,
        "day_tokens": status.day_tokens,
        "estimated_day_cost_usd": status.day_cost_usd,
        "estimated_month_cost_usd": status.month_cost_usd,
        "limits": status.limits,
        "notes": status.notes,
        "resource_controls": {
            "max_articles_per_batch": settings.max_articles_per_batch,
            "worker_max_concurrency": settings.worker_max_concurrency,
            "max_retry_attempts": settings.max_retry_attempts,
            "request_timeout_seconds": settings.request_timeout_seconds,
            "metric_retention_days": settings.metric_retention_days,
            "article_retention_days": settings.article_retention_days,
            "llm_enabled": settings.llm_enabled,
        },
        "disclaimer": (
            "These are application-level limits on model usage and estimated "
            "AI cost. They are NOT a guaranteed cap on your total cloud bill. "
            "Costs shown are estimates unless marked provider-reported."
        ),
    }


@router.get("/status")
def data_source_status(db: Session = Depends(get_db)):
    """Per-subsystem LIVE status: configured?, state, freshness, instructions."""
    return status_svc.overall(db)


@router.get("/usage")
def usage(days: int = Query(7, ge=1, le=90), db: Session = Depends(get_db)):
    since = utcnow() - timedelta(days=days)
    rows = db.scalars(
        select(AIUsage).where(AIUsage.created_at >= since)
        .order_by(AIUsage.created_at.desc()).limit(500)
    ).all()
    return {
        "days": days,
        "records": [
            {
                "at": r.created_at.isoformat(), "provider": r.provider,
                "operation": r.operation, "model": r.model,
                "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
                "requests": r.requests, "estimated_cost_usd": r.estimated_cost_usd,
                "provider_reported": r.provider_reported,
            }
            for r in rows
        ],
    }


# --------------------------- Reports -------------------------------------- #
@router.get("/reports/summary")
def report_summary(hours: int = Query(24, ge=1, le=720), db: Session = Depends(get_db)):
    since = utcnow() - timedelta(hours=hours)

    def count(model, ts_col):
        return int(db.scalar(select(func.count()).select_from(model).where(ts_col >= since)) or 0)

    return {
        "window_hours": hours,
        "status": status_svc.overall(db),
        "metrics_ingested": count(Metric, Metric.timestamp),
        "anomalies": count(Anomaly, Anomaly.detected_at),
        "alerts": count(Alert, Alert.created_at),
        "articles": count(Article, Article.ingested_at),
        "claims": count(Claim, Claim.created_at),
        "spam_assessments": count(SpamAssessment, SpamAssessment.created_at),
        "generated_at": utcnow().isoformat(),
    }


# --------------------------- Admin --------------------------------------- #
# NOTE: Sentinel AI runs LIVE only. There is intentionally NO demo-data
# generation endpoint — synthetic data must never be able to enter the running
# dashboard. Synthetic fixtures exist solely for the isolated test suite.
@router.post("/admin/retention/run")
def run_retention(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    result = retention_svc.apply_retention(db)
    db.add(AuditEvent(actor=user.username, action="run_retention", detail=result))
    db.commit()
    return {"status": "ok", "deleted": result}


@router.get("/admin/audit")
def list_audit(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    rows = db.scalars(
        select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)
    ).all()
    return [
        {"at": e.created_at.isoformat(), "actor": e.actor, "action": e.action,
         "target": e.target, "detail": e.detail}
        for e in rows
    ]
