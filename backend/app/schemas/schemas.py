"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---- Auth ----------------------------------------------------------------- #
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    is_admin: bool


# ---- Metrics -------------------------------------------------------------- #
class MetricIn(BaseModel):
    service: str = Field(min_length=1, max_length=128)
    timestamp: datetime | None = None
    source: str = Field(default="http_push", max_length=64)
    request_count: float | None = None
    request_rate: float | None = Field(default=None, ge=0)
    bytes_in: float | None = Field(default=None, ge=0)
    bytes_out: float | None = Field(default=None, ge=0)
    latency_p50_ms: float | None = Field(default=None, ge=0)
    latency_p95_ms: float | None = Field(default=None, ge=0)
    latency_p99_ms: float | None = Field(default=None, ge=0)
    error_count: float | None = Field(default=None, ge=0)
    error_rate: float | None = Field(default=None, ge=0, le=1)
    status_2xx: float | None = Field(default=None, ge=0)
    status_3xx: float | None = Field(default=None, ge=0)
    status_4xx: float | None = Field(default=None, ge=0)
    status_5xx: float | None = Field(default=None, ge=0)
    available: bool | None = None


class MetricBatchIn(BaseModel):
    metrics: list[MetricIn] = Field(min_length=1, max_length=500)


class ConnectionIn(BaseModel):
    src_service: str = Field(min_length=1, max_length=128)
    dst_service: str = Field(min_length=1, max_length=128)
    timestamp: datetime | None = None
    bytes_transferred: float | None = Field(default=None, ge=0)
    connection_count: int = Field(default=1, ge=1)
    # Only set suspicious when backed by a real detector/event.
    suspicious: bool = False


class ConnectionBatchIn(BaseModel):
    connections: list[ConnectionIn] = Field(min_length=1, max_length=500)


class PrometheusScrapeIn(BaseModel):
    service: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1)
    mapping: dict[str, str] = Field(
        default_factory=dict,
        description="Map of metric-column -> prometheus metric name.",
    )


# ---- Spam ----------------------------------------------------------------- #
class SpamAnalyzeIn(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    source: str = Field(default="user_submission", max_length=64)
    store: bool = True


class SpamResultOut(BaseModel):
    category: str
    score: float
    score_is_calibrated: bool
    indicators: list[dict]
    urls: list[dict]
    explanation: str
    recommendation: str
    model_version: str


# ---- Claims --------------------------------------------------------------- #
class ClaimAnalyzeIn(BaseModel):
    text: str = Field(min_length=20, max_length=50_000)
    use_factcheck: bool = True


class ClaimReviewIn(BaseModel):
    label: Literal[
        "supported", "contradicted", "misleading",
        "disputed", "unverified", "insufficient_evidence",
    ]
    explanation: str = Field(min_length=1, max_length=5000)
    reviewer: str = Field(default="admin", max_length=64)


# ---- Sources -------------------------------------------------------------- #
class SourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    source_type: Literal[
        "rss", "newsapi", "factcheck", "prometheus", "http_push", "network_sensor", "other"
    ]
    url: str | None = Field(default=None, max_length=1024)
    config: dict[str, Any] | None = None
    enabled: bool = True
    authorized: bool = True

    @field_validator("authorized")
    @classmethod
    def _must_authorize(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Sources must be explicitly authorized to be ingested.")
        return v


class ServiceIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    country: str | None = None
    city: str | None = None
    authorized: bool = True


# ---- Alerts --------------------------------------------------------------- #
class AlertAckIn(BaseModel):
    actor: str = Field(default="admin", max_length=64)
