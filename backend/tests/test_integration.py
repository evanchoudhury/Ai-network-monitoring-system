"""Integration tests.

Synthetic data is seeded ONLY via the isolated test factory (never via an API
route — no such route exists). These tests drive the real detection pipelines.
"""
from __future__ import annotations

from collections import Counter

from tests import factories


def test_factory_seeding_drives_real_pipelines(client, db):
    gen = factories.generate_all(db)
    assert gen["metrics"] > 0
    assert gen["anomalies"] > 0  # anomaly engine fired on synthetic spikes
    assert gen["articles"] > 0

    kpis = client.get("/api/overview").json()["kpis"]
    assert kpis["monitored_services"] > 0
    assert kpis["articles_collected"] > 0

    claims = client.get("/api/claims?limit=200").json()["items"]
    labels = Counter(c["status"] for c in claims)
    assert set(labels).issubset({
        "supported", "contradicted", "misleading",
        "disputed", "unverified", "insufficient_evidence",
    })
    assert client.get("/api/alerts").json()["total"] > 0


def test_anomaly_scan_is_idempotent(client, db, auth_headers):
    factories.generate_all(db)
    first = client.get("/api/anomalies").json()
    client.post("/api/anomalies/scan", headers=auth_headers)
    second = client.get("/api/anomalies").json()
    assert len(second) == len(first)  # re-scan never duplicates


def test_claim_review_overrides_assessment(client, db, auth_headers):
    factories.generate_all(db)
    claims = client.get("/api/claims?limit=1").json()["items"]
    assert claims
    cid = claims[0]["id"]
    r = client.post(f"/api/claims/{cid}/review",
                    json={"label": "supported", "explanation": "Human verified.",
                          "reviewer": "analyst"},
                    headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "supported"
    assert r.json()["needs_review"] is False


def test_retention_runs(client, db, auth_headers):
    factories.generate_all(db)
    r = client.post("/api/admin/retention/run", headers=auth_headers)
    assert r.status_code == 200
    assert "deleted" in r.json()
