"""Sentinel AI — FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from app.config import settings
from app.core.logging import configure_logging, get_logger
from app.api import auth, ingest, intelligence, network, ops

configure_logging("DEBUG" if settings.debug else "INFO")
logger = get_logger("sentinel.main")

# Prometheus instrumentation (the backend also *exposes* its own metrics).
REQUEST_COUNT = Counter(
    "sentinel_http_requests_total", "HTTP requests", ["method", "path", "status"]
)
REQUEST_LATENCY = Histogram(
    "sentinel_http_request_duration_seconds", "Request latency", ["method", "path"]
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.bootstrap import run_bootstrap
    from app.workers.scheduler import shutdown_scheduler, start_scheduler

    # Create schema automatically for SQLite/dev. For Postgres production use
    # Alembic; create_all is idempotent and harmless if migrations already ran.
    run_bootstrap(create_schema=True)
    start_scheduler()
    logger.info("Sentinel AI backend started",
                extra={"extra_fields": {"env": settings.environment}})
    try:
        yield
    finally:
        shutdown_scheduler()


app = FastAPI(
    title="Sentinel AI API",
    description="Network & Truth Intelligence platform — authorized network "
                "monitoring, anomaly detection, news intelligence, evidence-based "
                "claim assessment, and spam/phishing analysis.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def instrument(request: Request, call_next):
    import time

    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    path = request.url.path
    REQUEST_COUNT.labels(request.method, path, response.status_code).inc()
    REQUEST_LATENCY.labels(request.method, path).observe(duration)
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Safe error response: never leak internals/secrets to clients.
    logger.error("Unhandled error",
                 extra={"extra_fields": {"path": request.url.path, "error": str(exc)}})
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Liveness/readiness probes (unprefixed, for orchestrators).
@app.get("/healthz", tags=["meta"])
def healthz():
    return {"status": "ok"}


@app.get("/readyz", tags=["meta"])
def readyz():
    from app.database import SessionLocal
    from app.services.health import check_database

    db = SessionLocal()
    try:
        result = check_database(db)
    finally:
        db.close()
    code = 200 if result["status"] == "ok" else 503
    return JSONResponse(status_code=code, content=result)


@app.get("/metrics", tags=["meta"])
def prometheus_metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Mount API routers under the configured prefix.
_prefix = settings.api_prefix
for r in (auth.router, ingest.router, network.router, intelligence.router, ops.router):
    app.include_router(r, prefix=_prefix)


@app.get("/", tags=["meta"])
def root():
    return {
        "name": settings.app_name,
        "subtitle": "Network & Truth Intelligence",
        "version": "1.0.0",
        "docs": "/docs",
        "api_prefix": _prefix,
    }
