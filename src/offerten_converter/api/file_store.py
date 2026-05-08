"""In-memory file store for uploaded supplier offer files.

Files are held as bytes keyed by UUID, with a 1-hour TTL.
No disk writes – compliant with the project's in-memory-only policy.
"""

from __future__ import annotations

import time
import uuid
from typing import NamedTuple


class _Entry(NamedTuple):
    data: bytes
    filename: str
    created_at: float


_TTL_SECONDS = 3600
_store: dict[str, _Entry] = {}


def put(data: bytes, filename: str) -> str:
    """Store file bytes and return a unique file_id."""
    _evict()
    file_id = str(uuid.uuid4())
    _store[file_id] = _Entry(data=data, filename=filename, created_at=time.monotonic())
    return file_id


def get(file_id: str) -> tuple[bytes, str] | None:
    """Return (bytes, filename) or None if not found / expired."""
    entry = _store.get(file_id)
    if entry is None:
        return None
    if time.monotonic() - entry.created_at > _TTL_SECONDS:
        del _store[file_id]
        return None
    return entry.data, entry.filename


def _evict() -> None:
    cutoff = time.monotonic() - _TTL_SECONDS
    stale = [k for k, v in _store.items() if v.created_at < cutoff]
    for k in stale:
        del _store[k]
