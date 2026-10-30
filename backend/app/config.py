"""Central application configuration.

All configuration is sourced from environment variables (12-factor style) with
safe, local-development defaults. Secrets never have real defaults — they must
be supplied via the environment. See ``.env.example`` for the full list.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Application ---------------------------------------------------
    app_name: str = "Sentinel AI"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = True
    api_prefix: str = "/api"

    # ---- Database ------------------------------------------------------
    # Default is a local SQLite file for zero-config development. In
    # production set DATABASE_URL to a PostgreSQL DSN.
    database_url: str = "sqlite:///./sentinel.db"

    # ---- Security ------------------------------------------------------
    # MUST be overridden in production. A random value is generated per
    # process if left at the default so local dev works, but tokens will
    # not survive a restart.
    secret_key: str = Field(default="dev-insecure-change-me")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12
    # Bootstrap admin account created on first startup if no users exist.
    admin_username: str = "admin"
    admin_password: str = Field(default="changeme-admin")

    # Comma-separated list of allowed CORS origins.
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ---- Rate limiting -------------------------------------------------
    rate_limit_per_minute: int = 120

    # ---- News / evidence providers ------------------------------------
    # Optional API keys. When absent, those providers are simply disabled
    # and the system degrades gracefully to RSS + local evidence only.
    newsapi_key: str | None = None
    google_factcheck_api_key: str | None = None
    http_user_agent: str = "SentinelAI/1.0 (+https://github.com/sentinel-ai)"
    http_timeout_seconds: float = 15.0

    # ---- Optional external LLM (disabled by default) -------------------
    # The deterministic pipeline never requires an LLM. These exist only so
    # an operator can *opt in* to richer claim extraction. Off by default to
    # guarantee zero external AI spend.
    llm_enabled: bool = False
    llm_provider: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None

    # ---- Budget & resource controls -----------------------------------
    budget_daily_usd: float = 1.00
    budget_monthly_usd: float = 10.00
    budget_max_model_requests_per_day: int = 500
    budget_max_tokens_per_day: int = 200_000
    max_article_length_chars: int = 50_000
    max_articles_per_batch: int = 50
    worker_max_concurrency: int = 2
    request_timeout_seconds: float = 30.0
    max_retry_attempts: int = 3
    # Fail closed: if a mandatory budget check cannot be completed, deny.
    budget_fail_closed: bool = True

    # ---- Retention -----------------------------------------------------
    metric_retention_days: int = 30
    article_retention_days: int = 90
    max_stored_articles: int = 50_000

    # ---- Background workers -------------------------------------------
    enable_scheduler: bool = True
    news_ingest_interval_minutes: int = 30
    anomaly_scan_interval_minutes: int = 5
    health_check_interval_minutes: int = 2

    # ---- Anomaly detection defaults -----------------------------------
    anomaly_zscore_threshold: float = 3.5
    anomaly_min_baseline_points: int = 12
    anomaly_baseline_window: int = 48

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("["):
                return json.loads(v)
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
