"""SQLAlchemy engine and session setup.

SQLite runs in WAL mode (concurrent reads alongside one writer) with foreign
keys enforced. The engine is built from config.database_url(); make_engine() is
exposed so tests can spin up isolated databases.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from offerten_converter import config
from offerten_converter.infrastructure.db.base import Base

logger = logging.getLogger(__name__)

_SQLITE_PREFIX = "sqlite:///"


def _ensure_sqlite_dir(url: str) -> None:
    """Create the parent directory for a file-based SQLite database."""
    if not url.startswith(_SQLITE_PREFIX):
        return
    raw_path = url[len(_SQLITE_PREFIX):]
    if not raw_path or raw_path == ":memory:":
        return
    Path(raw_path).parent.mkdir(parents=True, exist_ok=True)


def make_engine(url: str) -> Engine:
    """Build an engine for the given URL, applying SQLite pragmas if relevant."""
    is_sqlite = url.startswith("sqlite")
    _ensure_sqlite_dir(url)
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    engine = create_engine(url, connect_args=connect_args, future=True)

    if is_sqlite:
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, _record):  # noqa: ANN001
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine: Engine = make_engine(config.database_url())
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False, class_=Session
)


def init_db() -> None:
    """Create all tables that don't yet exist. Idempotent; safe on every start."""
    # Import models so they register on Base.metadata before create_all.
    from offerten_converter.infrastructure.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    logger.info("Database ready at %s", engine.url)


def get_db():
    """FastAPI dependency: yield a session and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


__all__ = ["Base", "engine", "SessionLocal", "make_engine", "init_db", "get_db", "text"]
