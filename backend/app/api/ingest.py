"""Metric ingestion endpoints (operator-authenticated).

Ingestion is a privileged operation: only authenticated operators (or agents
using an operator token) may push metrics, and only for authorized services.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.database import get_db
from app.models import AuditEvent, NetworkConnection, User
from app.schemas.schemas import (
    ConnectionBatchIn,
    MetricBatchIn,
    MetricIn,
    PrometheusScrapeIn,
)
from app.services import metrics as metrics_svc

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/connections", status_code=201)
def ingest_connections(
    payload: ConnectionBatchIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Record observed connection events between two services for the map.

    Each endpoint must be an authorized service (auto-created if new). A
    connection is only ever marked suspicious when the caller sets it from a
    real detector/event — never speculatively.
    """
    accepted = 0
    for c in payload.connections:
        src = metrics_svc.get_or_create_service(db, c.src_service)
        dst = metrics_svc.get_or_create_service(db, c.dst_service)
        if not src.authorized or not dst.authorized:
            continue
        db.add(NetworkConnection(
            src_service_id=src.id, dst_service_id=dst.id,
            observed_at=c.timestamp or metrics_svc.utcnow(),
            bytes_transferred=c.bytes_transferred,
            connection_count=c.connection_count,
            suspicious=c.suspicious,
            is_demo=False,
        ))
        accepted += 1
    db.add(AuditEvent(actor=user.username, action="ingest_connections",
                      detail={"accepted": accepted}))
    db.commit()
    return {"accepted": accepted}


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
