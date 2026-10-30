"""Synthetic DEMO data generator.

Everything produced here is flagged ``is_demo=True`` (or clearly attributed to
demo sources) so the UI can label it DEMO DATA and never confuse it with live
observations. This exercises the *real* pipelines (anomaly detection, claim
assessment, spam scoring) on synthetic inputs — it does not hardcode results.
"""
from __future__ import annotations

import math
import random
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Anomaly,
    Article,
    IngestionSource,
    Metric,
    MonitoredService,
    NetworkConnection,
    Severity,
    SourceType,
    SpamAssessment,
    utcnow,
)
from app.services import spam as spam_mod
from app.services.news import content_hash

RNG = random.Random(1337)  # deterministic demo data

DEMO_LOCATIONS = [
    ("edge-nyc", "United States", "New York", 40.71, -74.01, 900),
    ("edge-sfo", "United States", "San Francisco", 37.77, -122.42, 1200),
    ("edge-lon", "United Kingdom", "London", 51.51, -0.13, 700),
    ("edge-fra", "Germany", "Frankfurt", 50.11, 8.68, 650),
    ("edge-sin", "Singapore", "Singapore", 1.35, 103.82, 480),
    ("edge-tok", "Japan", "Tokyo", 35.68, 139.69, 540),
    ("edge-syd", "Australia", "Sydney", -33.87, 151.21, 300),
    ("edge-sao", "Brazil", "Sao Paulo", -23.55, -46.63, 260),
    ("edge-blr", "India", "Bangalore", 12.97, 77.59, 420),
    ("edge-jnb", "South Africa", "Johannesburg", -26.2, 28.05, 180),
]

DEMO_ARTICLES = [
    # Cluster A — renewable energy (expected: supported; 3 corroborating sources)
    ("[DEMO] National grid reports renewable energy output rose 12 percent this year",
     "Officials said renewable energy generation rose 12 percent compared with last year.",
     "DemoWire"),
    ("[DEMO] Independent institute confirms renewable energy output increased 12 percent",
     "An independent energy institute confirmed renewable energy generation increased 12 percent this year.",
     "DemoAnalytics"),
    ("[DEMO] Government data shows renewable energy output up 12 percent",
     "New government data shows renewable energy generation rose 12 percent this year.",
     "DemoGovDesk"),

    # Cluster B — phone-charging hoax (expected: contradicted; 3 refutations)
    ("[DEMO] Viral post claims a new battery charges a phone in 10 seconds",
     "A viral post claims a new battery charges a phone fully in 10 seconds.",
     "DemoSocialDesk"),
    ("[DEMO] Experts say the 10 second phone charging claim is false",
     "Battery experts said the claim that a battery charges a phone in 10 seconds is false and has no evidence.",
     "DemoScience"),
    ("[DEMO] Fact check finds no evidence a battery charges a phone in 10 seconds",
     "A fact check found no evidence that any battery charges a phone in 10 seconds and the claim is false.",
     "DemoFactCheck"),
    ("[DEMO] Scientists debunk claim that a phone battery charges in 10 seconds",
     "Scientists debunked the claim that a phone battery charges in 10 seconds as false.",
     "DemoLabReport"),

    # Cluster C — diet/diabetes (expected: disputed; 2 support + 2 contradict)
    ("[DEMO] New study claims a specific diet reverses type 2 diabetes",
     "A new study claims that a specific diet can reverse type 2 diabetes in patients.",
     "DemoHealth"),
    ("[DEMO] Clinical trial finds the diet can reverse type 2 diabetes",
     "A clinical trial found the specific diet can reverse type 2 diabetes in some patients.",
     "DemoTrials"),
    ("[DEMO] Researchers say the diet does not reverse type 2 diabetes",
     "Researchers said the specific diet does not reverse type 2 diabetes and the claim is misleading.",
     "DemoMedJournal"),
    ("[DEMO] Review finds no strong evidence the diet reverses type 2 diabetes",
     "A medical review found no strong evidence that the specific diet reverses type 2 diabetes.",
     "DemoReview"),

    # Standalone (expected: insufficient_evidence / unverified — no corroboration)
    ("[DEMO] City council approves a 4 million dollar cybersecurity budget",
     "The city council voted to approve a 4 million dollar cybersecurity budget on Tuesday.",
     "DemoCityNews"),
]

DEMO_SPAM_MESSAGES = [
    "URGENT: Your PayPal account has been suspended. Verify your identity now at http://paypal-secure-login.xyz",
    "Congratulations! You've won a $1000 Amazon gift card. Claim your prize at http://bit.ly/claim-now",
    "Hi, are we still meeting for lunch tomorrow at noon?",
    "Final notice: update your billing information immediately or your account will be closed. http://192.168.3.9/update",
    "Limited time crypto investment opportunity, send bitcoin to double your money fast!",
]


def ensure_demo_services(db: Session) -> list[MonitoredService]:
    services = []
    for name, country, city, lat, lon, _base in DEMO_LOCATIONS:
        svc = db.scalar(select(MonitoredService).where(MonitoredService.name == name))
        if svc is None:
            svc = MonitoredService(
                name=name, description=f"Demo edge node — {city}",
                authorized=True, is_demo=True,
                latitude=lat, longitude=lon, country=country, city=city,
            )
            db.add(svc)
        services.append(svc)
    db.commit()
    for s in services:
        db.refresh(s)
    return services


def generate_metrics(db: Session, hours: int = 48, step_minutes: int = 15) -> int:
    """Generate diurnal demo metrics with a couple of injected anomalies."""
    services = ensure_demo_services(db)
    now = utcnow()
    points = int(hours * 60 / step_minutes)
    written = 0
    # Choose anomaly windows (indices) to inject spikes.
    anomaly_points = {int(points * 0.4), int(points * 0.72)}

    base_map = {t[0]: t[5] for t in DEMO_LOCATIONS}

    for svc in services:
        base_rps = base_map.get(svc.name, 400)
        for i in range(points):
            ts = now - timedelta(minutes=(points - i) * step_minutes)
            # Diurnal pattern (sine over 24h) + noise.
            hour = ts.hour + ts.minute / 60.0
            diurnal = 0.6 + 0.4 * math.sin((hour / 24.0) * 2 * math.pi - math.pi / 2)
            rps = base_rps * diurnal * (0.9 + 0.2 * RNG.random())
            err_rate = max(0.0, 0.01 + 0.01 * RNG.random())
            lat95 = 60 + 40 * diurnal + 20 * RNG.random()
            spike = i in anomaly_points and svc.name in ("edge-sfo", "edge-fra")
            if spike:
                rps *= 4.5
                err_rate = min(0.9, err_rate + 0.25)
                lat95 *= 3.2
            m = Metric(
                service_id=svc.id, timestamp=ts, source="demo", is_demo=True,
                request_rate=round(rps, 2),
                request_count=round(rps * step_minutes * 60, 0),
                bytes_in=round(rps * 1800 * (0.9 + 0.3 * RNG.random()), 0),
                bytes_out=round(rps * 1200 * (0.9 + 0.3 * RNG.random()), 0),
                latency_p50_ms=round(lat95 * 0.5, 1),
                latency_p95_ms=round(lat95, 1),
                latency_p99_ms=round(lat95 * 1.4, 1),
                error_rate=round(err_rate, 4),
                error_count=round(rps * step_minutes * 60 * err_rate, 0),
                available=not (spike and RNG.random() < 0.3),
            )
            db.add(m)
            written += 1
    db.commit()
    return written


def generate_connections(db: Session) -> int:
    services = ensure_demo_services(db)
    now = utcnow()
    written = 0
    # Hub-and-spoke from the two biggest nodes + a few suspicious ones.
    hubs = [s for s in services if s.name in ("edge-sfo", "edge-nyc", "edge-lon")]
    for hub in hubs:
        for dst in services:
            if dst.id == hub.id:
                continue
            suspicious = RNG.random() < 0.08
            db.add(NetworkConnection(
                src_service_id=hub.id, dst_service_id=dst.id, observed_at=now,
                bytes_transferred=round(RNG.uniform(1e6, 5e8), 0),
                connection_count=RNG.randint(5, 400),
                suspicious=suspicious, is_demo=True,
            ))
            written += 1
    db.commit()
    return written


def generate_news_and_claims(db: Session) -> dict:
    from app.services import pipeline

    source = db.scalar(
        select(IngestionSource).where(IngestionSource.name == "Demo Newswire")
    )
    if source is None:
        source = IngestionSource(
            name="Demo Newswire", source_type=SourceType.rss,
            url="demo://newswire", enabled=True, authorized=True,
            config={"demo": True},
        )
        db.add(source)
        db.commit()
        db.refresh(source)

    created_articles = 0
    for headline, summary, publisher in DEMO_ARTICLES:
        chash = content_hash(headline, f"demo://{publisher}/{headline[:30]}")
        if db.scalar(select(Article).where(Article.content_hash == chash)):
            continue
        art = Article(
            source_id=source.id, headline=headline, summary=summary,
            publisher=publisher, url=f"https://demo.example/{chash[:12]}",
            published_at=utcnow(), language="en",
            topic=None, content_hash=chash,
        )
        db.add(art)
        db.flush()
        from app.services.news import assign_story, classify_topic
        art.topic = classify_topic(f"{headline} {summary}")
        assign_story(db, art)
        created_articles += 1
    db.commit()

    # Run the REAL assessment pipeline on the demo corpus (no external calls).
    claims_count = pipeline.analyze_recent_articles(
        db, limit=len(DEMO_ARTICLES), use_factcheck=False
    )
    return {"articles": created_articles, "claims": claims_count}


def generate_spam(db: Session) -> int:
    written = 0
    for msg in DEMO_SPAM_MESSAGES:
        result = spam_mod.analyze_message(msg, source="demo")
        db.add(SpamAssessment(
            content_hash=result.content_hash, preview=result.preview,
            category=result.category, score=result.score,
            score_is_calibrated=result.score_is_calibrated,
            indicators=result.indicators, urls=result.urls,
            explanation=result.explanation, recommendation=result.recommendation,
            model_version=result.model_version, source="demo",
        ))
        written += 1
    db.commit()
    return written


def generate_all(db: Session) -> dict:
    """Generate a full demo dataset and run detection pipelines over it."""
    from app.services import anomaly_runner

    metrics = generate_metrics(db)
    conns = generate_connections(db)
    news = generate_news_and_claims(db)
    spam = generate_spam(db)
    anomalies = anomaly_runner.scan_all_services(db, only_demo=True)
    return {
        "metrics": metrics,
        "connections": conns,
        "articles": news["articles"],
        "claims": news["claims"],
        "spam": spam,
        "anomalies": anomalies,
    }
