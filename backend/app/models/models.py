"""SQLAlchemy ORM models for Sentinel AI.

The schema is intentionally modular: network monitoring, news intelligence,
claim verification, spam analysis, and operational tables (alerts, health,
usage, audit) each form a coherent group but share one database.

Design notes
------------
* All timestamps are timezone-aware UTC.
* Indexes are added for the fields most often filtered/sorted on
  (timestamps, source identifiers, foreign keys, status).
* We deliberately avoid storing unnecessary personal data. Submitted
  messages for spam analysis store a content hash and a truncated preview,
  not full long-term retention of arbitrary user content.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #
class Severity(str, enum.Enum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AlertCategory(str, enum.Enum):
    traffic_spike = "traffic_spike"
    error_rate = "error_rate"
    latency = "latency"
    availability = "availability"
    suspicious_traffic = "suspicious_traffic"
    news = "news"
    claim_conflict = "claim_conflict"
    phishing = "phishing"
    ingestion_failure = "ingestion_failure"
    provider_error = "provider_error"
    budget = "budget"


class SourceType(str, enum.Enum):
    rss = "rss"
    newsapi = "newsapi"
    factcheck = "factcheck"
    prometheus = "prometheus"
    http_push = "http_push"
    network_sensor = "network_sensor"
    other = "other"


class ClaimLabel(str, enum.Enum):
    supported = "supported"
    contradicted = "contradicted"
    misleading = "misleading"
    disputed = "disputed"
    unverified = "unverified"
    insufficient_evidence = "insufficient_evidence"


class SpamCategory(str, enum.Enum):
    clean = "clean"
    low_risk = "low_risk"
    suspicious = "suspicious"
    high_risk = "high_risk"
    phishing = "phishing"


# --------------------------------------------------------------------------- #
# Auth / audit
# --------------------------------------------------------------------------- #
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    actor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(128), index=True)
    target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)


# --------------------------------------------------------------------------- #
# Network monitoring
# --------------------------------------------------------------------------- #
class MonitoredService(Base):
    __tablename__ = "monitored_services"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Whether the operator has explicitly authorized monitoring of this
    # service. Metrics are only accepted for authorized services.
    authorized: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    # Geolocation for the global network map. Left NULL when unknown — the map
    # must never invent a location for a service without one.
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    city: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    metrics: Mapped[list["Metric"]] = relationship(back_populates="service")


class Metric(Base):
    """A single time-series observation for a service.

    One row carries the standard set of HTTP/network measurements for a
    window. Nullable fields allow partial data from sources that cannot
    report everything.
    """

    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int] = mapped_column(
        ForeignKey("monitored_services.id", ondelete="CASCADE"), index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    source: Mapped[str] = mapped_column(String(64), default="http_push", index=True)

    request_count: Mapped[float | None] = mapped_column(Float, nullable=True)
    request_rate: Mapped[float | None] = mapped_column(Float, nullable=True)  # req/s
    bytes_in: Mapped[float | None] = mapped_column(Float, nullable=True)
    bytes_out: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_p50_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_p95_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_p99_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_count: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_rate: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0..1
    status_2xx: Mapped[float | None] = mapped_column(Float, nullable=True)
    status_3xx: Mapped[float | None] = mapped_column(Float, nullable=True)
    status_4xx: Mapped[float | None] = mapped_column(Float, nullable=True)
    status_5xx: Mapped[float | None] = mapped_column(Float, nullable=True)
    available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    service: Mapped["MonitoredService"] = relationship(back_populates="metrics")

    __table_args__ = (
        Index("ix_metrics_service_ts", "service_id", "timestamp"),
    )


class MetricAggregate(Base):
    """Pre-computed rollups (e.g. hourly) to keep history queries cheap."""

    __tablename__ = "metric_aggregates"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int] = mapped_column(
        ForeignKey("monitored_services.id", ondelete="CASCADE"), index=True
    )
    bucket: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    resolution: Mapped[str] = mapped_column(String(16), default="1h")  # 1m,5m,1h
    metric_name: Mapped[str] = mapped_column(String(64), index=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    min: Mapped[float | None] = mapped_column(Float, nullable=True)
    max: Mapped[float | None] = mapped_column(Float, nullable=True)
    sum: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "service_id", "bucket", "resolution", "metric_name",
            name="uq_metric_agg",
        ),
    )


class NetworkConnection(Base):
    """An observed connection between two monitored locations.

    Only connections backed by configured/authorized data (or clearly flagged
    demo data) are stored. ``suspicious`` is set only when justified by a
    recorded anomaly/alert, never speculatively.
    """

    __tablename__ = "network_connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    src_service_id: Mapped[int] = mapped_column(
        ForeignKey("monitored_services.id", ondelete="CASCADE"), index=True
    )
    dst_service_id: Mapped[int] = mapped_column(
        ForeignKey("monitored_services.id", ondelete="CASCADE"), index=True
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    bytes_transferred: Mapped[float | None] = mapped_column(Float, nullable=True)
    connection_count: Mapped[int] = mapped_column(Integer, default=1)
    suspicious: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


# --------------------------------------------------------------------------- #
# Ingestion sources (news + sensors)
# --------------------------------------------------------------------------- #
class IngestionSource(Base):
    __tablename__ = "ingestion_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType), index=True)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    # Operator attests they are authorized / within terms for this source.
    authorized: Mapped[bool] = mapped_column(Boolean, default=True)
    last_ingested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint("name", "source_type", name="uq_source_name_type"),
    )


# --------------------------------------------------------------------------- #
# News intelligence
# --------------------------------------------------------------------------- #
class Story(Base):
    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    topic: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    article_count: Mapped[int] = mapped_column(Integer, default=0)
    # Number of distinct publishers — the real signal for corroboration.
    source_diversity: Mapped[int] = mapped_column(Integer, default=0)

    articles: Mapped[list["Article"]] = relationship(back_populates="story")


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingestion_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    story_id: Mapped[int | None] = mapped_column(
        ForeignKey("stories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    headline: Mapped[str] = mapped_column(String(512))
    publisher: Mapped[str | None] = mapped_column(String(256), index=True, nullable=True)
    url: Mapped[str] = mapped_column(String(1024))
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    # Hash of normalized title+url used for deduplication.
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    story: Mapped["Story"] = relationship(back_populates="articles")
    claims: Mapped[list["Claim"]] = relationship(back_populates="article")


# --------------------------------------------------------------------------- #
# Claim verification
# --------------------------------------------------------------------------- #
class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), index=True
    )
    # Exact wording of the claim as it appeared in the article.
    text: Mapped[str] = mapped_column(Text)
    entities: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Set by the most recent assessment for quick filtering.
    status: Mapped[ClaimLabel] = mapped_column(
        Enum(ClaimLabel), default=ClaimLabel.unverified, index=True
    )
    # Awaiting human review flag.
    needs_review: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    article: Mapped["Article"] = relationship(back_populates="claims")
    assessments: Mapped[list["ClaimAssessment"]] = relationship(back_populates="claim")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(String(1024))
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(256), nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "support" | "contradict" | "context"
    stance: Mapped[str] = mapped_column(String(16), default="context", index=True)
    relevance: Mapped[float] = mapped_column(Float, default=0.0)
    provider: Mapped[str] = mapped_column(String(64), default="local")
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    evidence_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ClaimAssessment(Base):
    __tablename__ = "claim_assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[ClaimLabel] = mapped_column(Enum(ClaimLabel), index=True)
    explanation: Mapped[str] = mapped_column(Text)
    limitations: Mapped[str | None] = mapped_column(Text, nullable=True)
    supporting_count: Mapped[int] = mapped_column(Integer, default=0)
    contradicting_count: Mapped[int] = mapped_column(Integer, default=0)
    model_version: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    # Distinguishes automated vs human-reviewed assessments.
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)

    claim: Mapped["Claim"] = relationship(back_populates="assessments")


# --------------------------------------------------------------------------- #
# Spam / phishing
# --------------------------------------------------------------------------- #
class SpamAssessment(Base):
    __tablename__ = "spam_assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    # We store a hash + short preview, not the full message indefinitely.
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    preview: Mapped[str | None] = mapped_column(String(280), nullable=True)
    category: Mapped[SpamCategory] = mapped_column(Enum(SpamCategory), index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    # Whether `score` is a calibrated probability (requires evaluation).
    score_is_calibrated: Mapped[bool] = mapped_column(Boolean, default=False)
    indicators: Mapped[list | None] = mapped_column(JSON, nullable=True)
    urls: Mapped[list | None] = mapped_column(JSON, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str] = mapped_column(String(64), default="rules-1.0")
    source: Mapped[str] = mapped_column(String(64), default="user_submission")


# --------------------------------------------------------------------------- #
# Anomalies & alerts
# --------------------------------------------------------------------------- #
class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int | None] = mapped_column(
        ForeignKey("monitored_services.id", ondelete="SET NULL"), nullable=True, index=True
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    metric_name: Mapped[str] = mapped_column(String(64), index=True)
    observed_value: Mapped[float] = mapped_column(Float)
    baseline_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_std: Mapped[float | None] = mapped_column(Float, nullable=True)
    zscore: Mapped[float | None] = mapped_column(Float, nullable=True)
    method: Mapped[str] = mapped_column(String(32), default="zscore")
    window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    window_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    severity: Mapped[Severity] = mapped_column(Enum(Severity), default=Severity.low)
    explanation: Mapped[str] = mapped_column(Text)
    # Anomalies are NOT confirmed attacks. This stays false unless a human
    # or a correlated signal confirms malicious intent.
    confirmed_attack: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    severity: Mapped[Severity] = mapped_column(Enum(Severity), index=True)
    category: Mapped[AlertCategory] = mapped_column(Enum(AlertCategory), index=True)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    title: Mapped[str] = mapped_column(String(256))
    explanation: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Links to related records, e.g. {"anomaly_id": 3, "claim_id": 9}.
    related: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Dedup key: identical active alerts share this and are not duplicated
    # within the cooldown window.
    dedup_key: Mapped[str] = mapped_column(String(128), index=True)

    __table_args__ = (
        Index("ix_alerts_dedup_ack", "dedup_key", "acknowledged"),
    )


# --------------------------------------------------------------------------- #
# Operational: health & AI usage
# --------------------------------------------------------------------------- #
class HealthCheck(Base):
    __tablename__ = "health_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    component: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16))  # ok | degraded | down
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)


class AIUsage(Base):
    __tablename__ = "ai_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    provider: Mapped[str] = mapped_column(String(64), index=True)
    operation: Mapped[str] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    requests: Mapped[int] = mapped_column(Integer, default=1)
    # estimated_cost_usd is an ESTIMATE unless provider_reported is True.
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    provider_reported: Mapped[bool] = mapped_column(Boolean, default=False)
