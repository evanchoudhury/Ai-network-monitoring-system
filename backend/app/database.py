"""Database engine, session management, and declarative base."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""


def _make_engine():
    connect_args: dict = {}
    kwargs: dict = {"future": True, "pool_pre_ping": True}
    if settings.is_sqlite:
        # Needed so SQLite connections can be used across threads (workers +
        # request handlers). check_same_thread=False is safe with the
        # session-per-request pattern used here.
        connect_args["check_same_thread"] = False
        # SQLite does not support pool_pre_ping meaningfully; drop pool args.
        kwargs.pop("pool_pre_ping", None)
    return create_engine(settings.database_url, connect_args=connect_args, **kwargs)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator:
    """FastAPI dependency yielding a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
