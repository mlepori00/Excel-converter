"""Use case: manage supplier profiles via the ProfileRepository port."""

from __future__ import annotations

from offerten_converter.application.ports import ProfileRepository


def profile_to_hints(profile: dict | None) -> str:
    """Build a column-hints string from a profile dict."""
    if not profile:
        return ""
    parts: list[str] = []
    if profile.get("typical_currency"):
        parts.append(f"Currency is typically {profile['typical_currency']}.")
    if profile.get("typical_discount"):
        parts.append(f"Typical discount is {profile['typical_discount']}%.")
    if profile.get("column_hints"):
        parts.append(f"Column hints: {profile['column_hints']}")
    return " ".join(parts)


__all__ = ["ProfileRepository", "profile_to_hints"]
