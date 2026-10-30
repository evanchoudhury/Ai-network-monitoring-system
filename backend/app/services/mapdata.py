"""Builds global-network-map payloads from real database state.

Node colouring follows the product spec:
  * cyan  -> normal observed activity
  * blue  -> monitored service / high-traffic location
  * amber -> a recently detected anomaly is associated with the node
  * red   -> a high/critical unacknowledged alert is associated with the node

Connections are teal by default; a connection is only ever marked red/dashed
(``suspicious``) when backed by a recorded flag. Services without a known
location are returned separately as ``unlocated`` and are never plotted with a
fabricated position.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Alert,
    Anomaly,
    MonitoredService,
    NetworkConnection,
    Severity,
    utcnow,
)

HIGH_TRAFFIC_RPS = 500.0


def build_map_data(db: Session, *, hours: int = 24) -> dict:
    since = utcnow() - timedelta(hours=hours)
    services = db.scalars(select(MonitoredService)).all()

    # Recent anomalies & alerts keyed by service.
    recent_anomalies = db.scalars(
        select(Anomaly).where(Anomaly.detected_at >= since)
    ).all()
    anomaly_svc = {a.service_id for a in recent_anomalies if a.service_id}

    recent_alerts = db.scalars(
        select(Alert).where(Alert.created_at >= since, Alert.acknowledged.is_(False))
    ).all()

    nodes = []
    unlocated = []
    svc_by_id = {s.id: s for s in services}

    from app.services.metrics import latest_per_service
    latest = {row["service_id"]: row for row in latest_per_service(db)}

    for svc in services:
        row = latest.get(svc.id, {})
        rps = row.get("request_rate") or 0.0
        has_anomaly = svc.id in anomaly_svc
        # High-severity alert referencing this service?
        has_high_alert = any(
            (a.severity in (Severity.high, Severity.critical))
            and (a.related or {}).get("service_id") == svc.id
            for a in recent_alerts
        )

        if has_high_alert:
            color = "red"
            kind = "alert"
        elif has_anomaly:
            color = "amber"
            kind = "anomaly"
        elif rps >= HIGH_TRAFFIC_RPS:
            color = "blue"
            kind = "high_traffic"
        else:
            color = "cyan"
            kind = "normal"

        node = {
            "id": svc.id,
            "name": svc.name,
            "country": svc.country,
            "city": svc.city,
            "color": color,
            "kind": kind,
            "request_rate": rps,
            "error_rate": row.get("error_rate"),
            "latency_p95_ms": row.get("latency_p95_ms"),
            "available": row.get("available"),
            "is_demo": svc.is_demo,
            "last_seen": row.get("timestamp"),
        }
        if svc.latitude is not None and svc.longitude is not None:
            node["lat"] = svc.latitude
            node["lon"] = svc.longitude
            nodes.append(node)
        else:
            unlocated.append(node)

    # Connections between located nodes only.
    located_ids = {n["id"] for n in nodes}
    conns = db.scalars(
        select(NetworkConnection)
        .where(NetworkConnection.observed_at >= since)
        .order_by(NetworkConnection.observed_at.desc())
        .limit(500)
    ).all()
    connections = []
    for c in conns:
        if c.src_service_id not in located_ids or c.dst_service_id not in located_ids:
            continue
        src = svc_by_id[c.src_service_id]
        dst = svc_by_id[c.dst_service_id]
        connections.append({
            "id": c.id,
            "src": {"id": src.id, "name": src.name, "lat": src.latitude, "lon": src.longitude},
            "dst": {"id": dst.id, "name": dst.name, "lat": dst.latitude, "lon": dst.longitude},
            "bytes": c.bytes_transferred,
            "count": c.connection_count,
            "suspicious": c.suspicious,
            "is_demo": c.is_demo,
            "style": "attack" if c.suspicious else "normal",
        })

    any_demo = any(n["is_demo"] for n in nodes) or any(c["is_demo"] for c in connections)
    return {
        "nodes": nodes,
        "connections": connections,
        "unlocated": unlocated,
        "legend": {
            "cyan": "Normal observed activity",
            "blue": "Monitored service / high traffic",
            "amber": "Detected anomaly",
            "red": "High-severity alert",
            "teal_line": "Ordinary observed connection",
            "red_dashed_line": "Suspicious connection (event-backed)",
        },
        "counts": {
            "nodes": len(nodes),
            "connections": len(connections),
            "countries": len({n["country"] for n in nodes if n["country"]}),
            "suspicious": sum(1 for c in connections if c["suspicious"]),
            "unlocated": len(unlocated),
        },
        "contains_demo_data": any_demo,
        "window_hours": hours,
    }
