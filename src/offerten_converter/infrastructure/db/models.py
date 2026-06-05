"""SQLAlchemy ORM models.

Models are imported by init_db() so they register on Base.metadata before
create_all() runs. The User model is added in phase 1b.
"""

from __future__ import annotations

from offerten_converter.infrastructure.db.base import Base  # noqa: F401  (re-exported for init_db)
