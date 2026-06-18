"""Disk-based cache for extracted DataFrames.

Cache key: SHA-256 of the raw file bytes (+ version + selected sheet) → avoids
re-extraction after page reload.
Storage: ~/.offerten_converter/cache/<hash>.json  (one file per unique upload)

IMPORTANT: every key is version-stamped via `_CACHE_VERSION`. Bump it whenever the
extraction logic changes in a way that would make previously cached results wrong
(e.g. a fixed column mapping or quantity parse) — otherwise users re-uploading the
same file keep getting the old, stale extraction. There is deliberately no
unversioned key: an unversioned hash would silently defeat this invalidation.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_CACHE_DIR = Path.home() / ".offerten_converter" / "cache"
_MAX_ENTRIES = 50  # keep at most N cache files; oldest removed first

# Bump on any extraction-logic change that invalidates previously cached results.
# v3: fixed size-matrix quantity (was the per-product Total) and European/mojibake
#     price parsing — all v2 entries are stale.
_CACHE_VERSION = "v3"


def cache_key(file_bytes: bytes, sheet_name: str | None = None) -> str:
    """Return a stable, version-stamped cache key for one file + selected sheet."""
    digest = hashlib.sha256()
    digest.update(_CACHE_VERSION.encode("utf-8"))
    digest.update(b"\0")
    digest.update((sheet_name or "").encode("utf-8"))
    digest.update(b"\0")
    digest.update(file_bytes)
    return digest.hexdigest()


def _cache_path(key: str) -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR / f"{key}.json"


def load(key: str) -> pd.DataFrame | None:
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            records = json.load(f)
        df = pd.DataFrame(records)
        logger.info("Extraction cache hit: %s", key[:12])
        return df
    except Exception as exc:
        logger.warning("Cache load failed (%s): %s", key[:12], exc)
        path.unlink(missing_ok=True)
        return None


def save(key: str, df: pd.DataFrame) -> None:
    try:
        path = _cache_path(key)
        with path.open("w", encoding="utf-8") as f:
            records = df.where(pd.notna(df), other=None).to_dict(orient="records")
            json.dump(records, f, ensure_ascii=False)
        _evict_oldest()
    except Exception as exc:
        logger.warning("Cache save failed: %s", exc)


def _evict_oldest() -> None:
    entries = sorted(_CACHE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
    for old in entries[:-_MAX_ENTRIES]:
        old.unlink(missing_ok=True)
