"""File-based supplier profile repository – stores JSON files in /profiles/."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_PROFILES_DIR = Path(__file__).parent.parent.parent.parent / "profiles"


def _safe_filename(name: str) -> str:
    """Convert a supplier name to a safe filename slug."""
    slug = re.sub(r"[^\w\-]", "_", name.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "supplier"


class FileProfileRepository:
    """CRUD for supplier profiles stored as JSON files."""

    def __init__(self, profiles_dir: Path | None = None):
        self._dir = profiles_dir or DEFAULT_PROFILES_DIR

    def _ensure_dir(self):
        self._dir.mkdir(parents=True, exist_ok=True)

    def list_profiles(self) -> list[str]:
        self._ensure_dir()
        return sorted(p.stem for p in self._dir.glob("*.json"))

    def load(self, name: str) -> dict | None:
        path = self._dir / f"{_safe_filename(name)}.json"
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Could not load profile %s: %s", path, exc)
            return None

    def save(
        self,
        name: str,
        typical_currency: str = "EUR",
        typical_discount: float = 0.0,
        column_hints: str = "",
    ) -> Path:
        self._ensure_dir()
        profile = {
            "name": name,
            "typical_currency": typical_currency,
            "typical_discount": typical_discount,
            "column_hints": column_hints,
        }
        path = self._dir / f"{_safe_filename(name)}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)
        logger.info("Saved supplier profile: %s", path)
        return path

    def delete(self, name: str) -> bool:
        path = self._dir / f"{_safe_filename(name)}.json"
        if path.exists():
            path.unlink()
            logger.info("Deleted supplier profile: %s", path)
            return True
        return False


def profile_to_hints(profile: dict) -> str:
    """Convert a profile dict to a context string for the extraction prompt."""
    parts = []
    if profile.get("typical_currency"):
        parts.append(f"Typical currency: {profile['typical_currency']}")
    if profile.get("typical_discount"):
        parts.append(f"Typical discount: {profile['typical_discount']}%")
    if profile.get("column_hints"):
        parts.append(f"Column mapping hints: {profile['column_hints']}")
    return "; ".join(parts)
