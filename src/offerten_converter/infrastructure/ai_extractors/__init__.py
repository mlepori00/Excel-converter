"""AI extractor adapter factory."""

from __future__ import annotations

from typing import Callable


def get_call_fn(api_key: str) -> Callable:
    """Return the concrete AI call function for *api_key*."""
    if api_key.startswith("sk-or-"):
        from offerten_converter.infrastructure.ai_extractors.openrouter_extractor import (
            call_openrouter,
        )

        return call_openrouter

    from offerten_converter.infrastructure.ai_extractors.anthropic_extractor import (
        call_anthropic,
    )

    return call_anthropic
