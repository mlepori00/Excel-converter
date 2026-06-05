"""Integration tests for the SQLAlchemy engine/session foundation (phase 1a)."""

from __future__ import annotations

from sqlalchemy import text

from offerten_converter.infrastructure.db.base import Base
from offerten_converter.infrastructure.db.engine import make_engine


def test_sqlite_engine_uses_wal_mode(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.connect() as conn:
        mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        assert str(mode).lower() == "wal"
        assert conn.execute(text("SELECT 1")).scalar() == 1


def test_sqlite_engine_enforces_foreign_keys(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_make_engine_creates_parent_directory(tmp_path):
    nested = tmp_path / "deeper" / "data"
    engine = make_engine(f"sqlite:///{nested / 'offerten.db'}")
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    assert nested.exists()


def test_create_all_runs_without_models(tmp_path):
    # phase 1a has no tables yet; create_all must still succeed (no-op).
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    from offerten_converter.infrastructure.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)  # must not raise
