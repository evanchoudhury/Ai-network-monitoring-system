"""Metric ingestion, aggregation, and history tests."""
from __future__ import annotations

from datetime import timedelta

from app.models import MonitoredService, utcnow
from app.services import metrics as metrics_svc
from app.services.anomaly import Point


def test_ingest_metric_creates_service_and_point(db):
    m = metrics_svc.ingest_metric(
        db, service_name="svc-a",
        values={"request_rate": 120.0, "error_rate": 0.02, "latency_p95_ms": 88.0},
    )
    assert m.id is not None
    assert m.request_rate == 120.0


def test_error_rate_derived_when_missing(db):
    m = metrics_svc.ingest_metric(
        db, service_name="svc-b",
        values={"request_count": 1000, "error_count": 50},
    )
    assert abs(m.error_rate - 0.05) < 1e-9


def test_unauthorized_service_rejected(db):
    svc = MonitoredService(name="svc-unauth", authorized=False)
    db.add(svc)
    db.commit()
    import pytest
    with pytest.raises(metrics_svc.IngestionError):
        metrics_svc.ingest_metric(db, service_name="svc-unauth", values={"request_rate": 1})


def test_history_is_ordered_and_bounded(db):
    now = utcnow()
    for i in range(10):
        metrics_svc.ingest_metric(
            db, service_name="svc-c", values={"request_rate": float(i)},
            timestamp=now - timedelta(hours=i),
        )
    hist = metrics_svc.get_history(db, metric="request_rate", hours=24)
    ts = [p["timestamp"] for p in hist]
    assert ts == sorted(ts)  # ascending
    assert len(hist) == 10


def test_history_respects_window(db):
    now = utcnow()
    metrics_svc.ingest_metric(db, service_name="svc-d", values={"request_rate": 1.0},
                              timestamp=now - timedelta(hours=50))
    metrics_svc.ingest_metric(db, service_name="svc-d", values={"request_rate": 2.0},
                              timestamp=now - timedelta(hours=1))
    hist = metrics_svc.get_history(db, metric="request_rate", hours=24)
    assert len(hist) == 1  # only the recent point


def test_rollup_hourly(db):
    now = utcnow().replace(minute=5)
    for i in range(6):
        metrics_svc.ingest_metric(db, service_name="svc-e",
                                  values={"request_rate": 100.0 + i}, timestamp=now)
    written = metrics_svc.rollup_hourly(db, hours=2)
    assert written >= 1


def test_prometheus_parsing():
    text = """# HELP x
    # TYPE x counter
    http_requests_total 42
    http_latency_ms 15.5
    bad line here
    """
    parsed = metrics_svc.parse_prometheus_text(text)
    assert parsed["http_requests_total"] == 42
    assert parsed["http_latency_ms"] == 15.5
    assert "bad" not in parsed
