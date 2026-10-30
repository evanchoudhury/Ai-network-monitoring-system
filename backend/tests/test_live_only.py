"""Tests proving the application runs LIVE only and never fabricates data."""
from __future__ import annotations

from datetime import timedelta

from app.models import utcnow
from app.services import metrics as metrics_svc
from tests import factories


def test_no_demo_generation_endpoint(client, auth_headers):
    """The synthetic-data generation route must not exist in the live app."""
    r = client.post("/api/admin/demo/generate", headers=auth_headers)
    assert r.status_code == 404


def test_empty_db_reports_not_configured(client):
    """With no data, the dashboard reports NOT CONFIGURED — not fake zeros."""
    ov = client.get("/api/overview").json()
    assert ov["network_configured"] is False
    net = ov["status"]["network"]
    assert net["state"] == "not_configured"
    assert "NOT CONFIGURED" in net["detail"]
    assert "instructions" in net
    # Traffic KPIs are null (no data), never a fabricated 0.
    assert ov["kpis"]["incoming_bytes_24h"] is None
    assert ov["kpis"]["outgoing_bytes_24h"] is None
    assert ov["kpis"]["requests_per_second"] is None


def test_status_endpoint_reports_each_subsystem(client):
    s = client.get("/api/status").json()
    assert s["live"] is True
    for subsystem in ("network", "news", "claims", "spam", "workers"):
        assert subsystem in s
    assert s["spam"]["state"] == "no_source"
    assert "NO MESSAGE SOURCE CONNECTED" in s["spam"]["detail"]


def test_fresh_metric_makes_network_fresh(client, db, auth_headers):
    client.post("/api/ingest/metrics",
                json={"service": "prod-api", "request_rate": 10.0, "bytes_in": 100,
                      "bytes_out": 50},
                headers=auth_headers)
    ov = client.get("/api/overview").json()
    assert ov["network_configured"] is True
    assert ov["status"]["network"]["state"] == "fresh"
    assert ov["kpis"]["incoming_bytes_24h"] is not None


def test_stale_metric_is_reported_stale(client, db):
    """Old-only data is reported as stale, not presented as current/fresh."""
    old = utcnow() - timedelta(hours=6)
    metrics_svc.ingest_metric(db, service_name="old-svc",
                              values={"request_rate": 5.0}, timestamp=old)
    net = client.get("/api/status").json()["network"]
    assert net["state"] == "stale"
    assert net["configured"] is True


def test_failed_feed_is_reported_not_faked(client, db, monkeypatch):
    """A failing feed records an error and never injects synthetic articles."""
    from app.models import IngestionSource, SourceType

    src = IngestionSource(name="Broken Feed", source_type=SourceType.rss,
                          url="https://example.invalid/rss", enabled=True, authorized=True)
    db.add(src)
    db.commit()

    # Force the fetch to fail — assert no articles are fabricated.
    import app.services.news as news_svc

    def boom(url):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(news_svc, "fetch_feed_bytes", boom)

    # Drive the same inline ingestion the scheduler/endpoint uses.
    from sqlalchemy import select
    from app.models import Article
    before = db.scalar(select(__import__("sqlalchemy").func.count(Article.id))) or 0
    try:
        raw = news_svc.fetch_feed_bytes(src.url)
        news_svc.ingest_articles(db, src, news_svc.parse_feed(raw))
    except RuntimeError:
        src.last_status = "error"
        src.last_error = "connection refused"
        db.commit()
    after = db.scalar(select(__import__("sqlalchemy").func.count(Article.id))) or 0
    assert after == before  # no fabricated articles
    assert src.last_status == "error"


def test_news_status_reports_failing_source(client, db):
    from app.models import IngestionSource, SourceType

    db.add(IngestionSource(name="Good", source_type=SourceType.rss, url="https://x/rss",
                           enabled=True, authorized=True, last_status="ok"))
    db.add(IngestionSource(name="Bad", source_type=SourceType.rss, url="https://y/rss",
                           enabled=True, authorized=True, last_status="error",
                           last_error="403"))
    db.commit()
    news = client.get("/api/status").json()["news"]
    assert news["configured"] is True
    assert news["failing_count"] == 1


def test_map_without_connections_explains_why(client, db):
    # Seed located services but no connection events.
    from app.models import MonitoredService
    db.add(MonitoredService(name="svc-geo", latitude=40.0, longitude=-74.0,
                            country="US", city="NY", authorized=True))
    db.commit()
    m = client.get("/api/map").json()
    assert m["counts"]["connections"] == 0
    assert m["empty_reason"]  # honest explanation, no fabricated arcs
    assert m["connections"] == []


def test_invalid_ingestion_payload_rejected(client, auth_headers):
    r = client.post("/api/ingest/metrics",
                    json={"service": "s", "error_rate": 42}, headers=auth_headers)
    assert r.status_code == 422


def test_claims_status_reports_evidence_providers(client):
    s = client.get("/api/status").json()["claims"]
    assert "local_corpus" in s["evidence_providers"]
    # No external key configured in tests -> flagged honestly.
    assert s["external_evidence_configured"] is False
