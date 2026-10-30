"""Metric ingestion endpoints (operator-authenticated).

Ingestion is a privileged operation: only authenticated operators (or agents
using an operator token) may push metrics, and only for authorized services.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.database import get_db
from app.models import AuditEvent, User
from app.schemas.schemas import MetricBatchIn, MetricIn, PrometheusScrapeIn
from app.services import metrics as metrics_svc

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/metrics", status_code=201)
def ingest_one(
    payload: MetricIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        point = metrics_svc.ingest_metric(
            db,
            service_name=payload.service,
            values=payload.model_dump(exclude={"service", "timestamp", "source"}),
            timestamp=payload.timestamp,
            source=payload.source,
        )
    except metrics_svc.IngestionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return {"id": point.id, "service_id": point.service_id, "status": "accepted"}


@router.post("/metrics/batch", status_code=201)
def ingest_batch(
    payload: MetricBatchIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    accepted = 0
    errors: list[str] = []
    for m in payload.metrics:
        try:
            metrics_svc.ingest_metric(
                db,
                service_name=m.service,
                values=m.model_dump(exclude={"service", "timestamp", "source"}),
                timestamp=m.timestamp,
                source=m.source,
                commit=False,
            )
            accepted += 1
        except metrics_svc.IngestionError as exc:
            errors.append(str(exc))
    db.commit()
    return {"accepted": accepted, "rejected": len(errors), "errors": errors[:10]}


@router.post("/prometheus", status_code=201)
def ingest_prometheus(
    payload: PrometheusScrapeIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Ingest a Prometheus text-exposition payload.

    ``mapping`` maps our metric columns to Prometheus metric names, e.g.
    {"request_rate": "http_requests_per_second"}.
    """
    parsed = metrics_svc.parse_prometheus_text(payload.text)
    if not parsed:
        raise HTTPException(status_code=422, detail="No metrics parsed from payload.")
    values = {}
    for col, prom_name in payload.mapping.items():
        if prom_name in parsed:
            values[col] = parsed[prom_name]
    if not values:
        raise HTTPException(
            status_code=422,
            detail="Mapping produced no matching metrics; check metric names.",
        )
    point = metrics_svc.ingest_metric(
        db, service_name=payload.service, values=values, source="prometheus"
    )
    db.add(AuditEvent(actor=user.username, action="ingest_prometheus", target=payload.service))
    db.commit()
    return {"id": point.id, "mapped": list(values.keys())}
