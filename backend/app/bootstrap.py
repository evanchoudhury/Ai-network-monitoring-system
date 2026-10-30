"""First-run bootstrap: ensure schema, seed admin user and default sources."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.logging import get_logger
from app.core.security import hash_password
from app.database import Base, SessionLocal, engine
from app.models import IngestionSource, SourceType, User

logger = get_logger("sentinel.bootstrap")

# A small set of well-known, freely available RSS feeds. Operators are
# expected to review/replace these; they are disabled-by-default-safe because
# ingestion only runs when the scheduler is enabled or triggered explicitly.
DEFAULT_RSS_SOURCES = [
    ("BBC News - World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("NPR News", "https://feeds.npr.org/1001/rss.xml"),
    ("The Guardian - World", "https://www.theguardian.com/world/rss"),
    ("Al Jazeera - All", "https://www.aljazeera.com/xml/rss/all.xml"),
]


def create_tables() -> None:
    """Create tables directly (used for SQLite/dev and tests).

    Production deployments should use Alembic migrations instead; this is
    idempotent and safe to call either way.
    """
    Base.metadata.create_all(bind=engine)


def seed_admin(db: Session) -> None:
    existing = db.scalar(select(User))
    if existing is not None:
        return
    user = User(
        username=settings.admin_username,
        hashed_password=hash_password(settings.admin_password),
        is_admin=True,
    )
    db.add(user)
    db.commit()
    logger.info("Seeded bootstrap admin user",
                extra={"extra_fields": {"username": settings.admin_username}})


def seed_default_sources(db: Session) -> None:
    for name, url in DEFAULT_RSS_SOURCES:
        existing = db.scalar(
            select(IngestionSource).where(
                IngestionSource.name == name,
                IngestionSource.source_type == SourceType.rss,
            )
        )
        if existing is None:
            db.add(IngestionSource(
                name=name, source_type=SourceType.rss, url=url,
                enabled=True, authorized=True,
                config={"note": "Default source — review per source terms."},
            ))

    # Seed a NewsAPI source only when a key is configured (so the key is
    # actually usable out of the box). Without a key, nothing is added.
    if settings.newsapi_key:
        exists = db.scalar(
            select(IngestionSource).where(
                IngestionSource.source_type == SourceType.newsapi
            )
        )
        if exists is None:
            db.add(IngestionSource(
                name="NewsAPI Top Headlines",
                source_type=SourceType.newsapi,
                url="https://newsapi.org/v2/top-headlines",
                enabled=True, authorized=True,
                config={"endpoint": "top-headlines", "category": "general", "pageSize": 50},
            ))
    db.commit()


def run_bootstrap(create_schema: bool = True) -> None:
    if create_schema:
        create_tables()
    db = SessionLocal()
    try:
        seed_admin(db)
        seed_default_sources(db)
    finally:
        db.close()
