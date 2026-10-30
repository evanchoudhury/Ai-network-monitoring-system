"""API-level tests: auth, validation, alerts, budget, map, error handling."""
from __future__ import annotations

import pytest


def test_startup_and_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["name"] == "Sentinel AI"


def test_healthz_readyz(client):
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 200


def test_prometheus_metrics_exposed(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "sentinel_http_requests_total" in r.text


def test_overview_reports_mode(client):
    r = client.get("/api/overview")
    assert r.status_code == 200
    body = r.json()
    assert "mode" in body and "kpis" in body
    # Fresh DB: no data -> empty mode, honest about it.
    assert body["mode"]["mode"] in {"empty", "demo", "live", "live_stale"}


def test_login_success_and_failure(client):
    ok = client.post("/api/auth/token", data={"username": "admin", "password": "test-admin-pass"})
    assert ok.status_code == 200 and "access_token" in ok.json()
    bad = client.post("/api/auth/token", data={"username": "admin", "password": "wrong"})
    assert bad.status_code == 401


def test_protected_route_requires_auth(client):
    # Ingestion is admin-only.
    r = client.post("/api/ingest/metrics", json={"service": "s", "request_rate": 1})
    assert r.status_code == 401


def test_protected_route_with_auth(client, auth_headers):
    r = client.post("/api/ingest/metrics", json={"service": "s", "request_rate": 1},
                    headers=auth_headers)
    assert r.status_code == 201


def test_input_validation(client, auth_headers):
    # error_rate must be within [0, 1].
    r = client.post("/api/ingest/metrics", json={"service": "s", "error_rate": 5},
                    headers=auth_headers)
    assert r.status_code == 422


def test_metric_history_invalid_metric(client):
    r = client.get("/api/metrics/history?metric=not_a_metric")
    assert r.status_code == 422


def test_spam_analyze_endpoint(client):
    r = client.post("/api/spam/analyze",
                    json={"message": "URGENT verify your account at http://bit.ly/x now!!!"})
    assert r.status_code == 200
    body = r.json()
    assert body["category"] in {"suspicious", "high_risk", "phishing", "low_risk"}
    assert body["score_is_calibrated"] is False


def test_claim_analyze_abstains_without_evidence(client):
    r = client.post("/api/claims/analyze", json={
        "text": "An isolated statement about a fictional zqxw device launching in 2050 with 7 units."
    })
    assert r.status_code == 200
    claims = r.json()["claims"]
    if claims:  # at least abstains, never fabricates certainty
        assert claims[0]["assessment"]["label"] in {"insufficient_evidence", "unverified"}


def test_alert_lifecycle_and_dedup(client, db, auth_headers):
    from app.models import AlertCategory, Severity
    from app.services import alerts as alert_svc

    a1 = alert_svc.create_alert(db, category=AlertCategory.budget, severity=Severity.high,
                                title="Test", explanation="e", discriminator="x")
    assert a1 is not None
    # Duplicate within cooldown is suppressed.
    a2 = alert_svc.create_alert(db, category=AlertCategory.budget, severity=Severity.high,
                                title="Test", explanation="e", discriminator="x")
    assert a2 is None

    listed = client.get("/api/alerts").json()
    assert listed["total"] == 1
    aid = listed["items"][0]["id"]

    # Ack requires auth.
    assert client.post(f"/api/alerts/{aid}/ack", json={"actor": "t"}).status_code == 401
    acked = client.post(f"/api/alerts/{aid}/ack", json={"actor": "t"}, headers=auth_headers)
    assert acked.status_code == 200 and acked.json()["acknowledged"] is True


def test_budget_disclaimer_and_enforcement(client, db):
    r = client.get("/api/budget")
    assert r.status_code == 200
    body = r.json()
    assert "guaranteed" in body["disclaimer"].lower()
    assert body["within_budget"] is True

    # Simulate usage pushing past the daily request limit -> fail closed.
    from app.config import settings
    from app.core.budget import BudgetExceeded, check_and_reserve, record_usage
    for _ in range(settings.budget_max_model_requests_per_day):
        record_usage(db, provider="test", operation="op", requests=1, commit=False)
    db.commit()
    with pytest.raises(BudgetExceeded):
        check_and_reserve(db)


def test_map_data_structure(client, auth_headers):
    # Generate demo data then inspect the map payload.
    client.post("/api/admin/demo/generate", headers=auth_headers)
    r = client.get("/api/map")
    assert r.status_code == 200
    body = r.json()
    assert "nodes" in body and "connections" in body and "legend" in body
    assert body["contains_demo_data"] is True
    # Every plotted node has a real location; colours come from the spec set.
    for n in body["nodes"]:
        assert n["lat"] is not None and n["lon"] is not None
        assert n["color"] in {"cyan", "blue", "amber", "red"}


def test_unauthorized_source_rejected_by_schema(client, auth_headers):
    r = client.post("/api/sources",
                    json={"name": "x", "source_type": "rss", "authorized": False},
                    headers=auth_headers)
    assert r.status_code == 422  # must be explicitly authorized
