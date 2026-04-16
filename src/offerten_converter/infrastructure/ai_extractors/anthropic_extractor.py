"""Anthropic direct API adapter (sk-ant-… keys)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

MODEL_ANTHROPIC = "claude-opus-4-5"
MAX_TOKENS = 8192


def call_anthropic(
    user_content: str, system_prompt: str, api_key: str,
) -> tuple[str, int, int]:
    """Send a single request to Anthropic and return (text, input_tokens, output_tokens)."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    try:
        message = client.messages.create(
            model=MODEL_ANTHROPIC,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
    except anthropic.APIError as exc:
        raise RuntimeError(f"Anthropic API error: {exc}") from exc
    text = message.content[0].text.strip()
    usage = getattr(message, "usage", None)
    input_tokens = getattr(usage, "input_tokens", 0) if usage else 0
    output_tokens = getattr(usage, "output_tokens", 0) if usage else 0
    return text, input_tokens, output_tokens
