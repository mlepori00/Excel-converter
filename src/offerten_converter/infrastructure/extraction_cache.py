"""Disk-based cache for extracted DataFrames.

Cache key: SHA-256 of the raw file bytes → avoids re-extraction after page reload.
Storage: ~/.offerten_converter/cache/<hash>.json  (one file per unique upload)
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


def file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


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
            json.dump(df.where(pd.notna(df), other=None).to_dict(orient="records"), f, ensure_ascii=False)
        _evict_oldest()
    except Exception as exc:
        logger.warning("Cache save failed: %s", exc)


def _evict_oldest() -> None:
    entries = sorted(_CACHE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
    for old in entries[:-_MAX_ENTRIES]:
        old.unlink(missing_ok=True)
