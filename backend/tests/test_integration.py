"""Integration tests: demo generation drives the real detection pipelines."""
from __future__ import annotations

from collections import Counter


def test_demo_generation_end_to_end(client, auth_headers):
    r = client.post("/api/admin/demo/generate", headers=auth_headers)
    assert r.status_code == 200
    gen = r.json()["generated"]
    assert gen["metrics"] > 0
    assert gen["anomalies"] > 0  # anomaly engine fired on synthetic spikes
    assert gen["articles"] > 0

    # Overview reflects the generated state.
    kpis = client.get("/api/overview").json()["kpis"]
    assert kpis["monitored_services"] > 0
    assert kpis["articles_collected"] > 0

    # Claims span multiple honest labels (not all one bucket, never fabricated).
    claims = client.get("/api/claims?limit=200").json()["items"]
    labels = Counter(c["status"] for c in claims)
    assert "supported" in labels or "disputed" in labels
    assert set(labels).issubset({
        "supported", "contradicted", "misleading",
        "disputed", "unverified", "insufficient_evidence",
    })

    # Alerts were persisted and can be listed.
    assert client.get("/api/alerts").json()["total"] > 0


def test_anomaly_scan_is_idempotent(client, auth_headers):
    client.post("/api/admin/demo/generate", headers=auth_headers)
    first = client.get("/api/anomalies").json()
    # Re-scanning must not duplicate existing anomalies.
    client.post("/api/anomalies/scan", headers=auth_headers)
    second = client.get("/api/anomalies").json()
    assert len(second) == len(first)


def test_claim_review_overrides_assessment(client, auth_headers):
    client.post("/api/admin/demo/generate", headers=auth_headers)
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


def test_retention_runs(client, auth_headers):
    client.post("/api/admin/demo/generate", headers=auth_headers)
    r = client.post("/api/admin/retention/run", headers=auth_headers)
    assert r.status_code == 200
    assert "deleted" in r.json()
