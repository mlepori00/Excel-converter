"""OpenRouter API adapter (sk-or-… keys) – uses OpenAI SDK with custom base URL."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

MODEL_OPENROUTER = "anthropic/claude-opus-4-5"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MAX_TOKENS = 8192


def call_openrouter(
    user_content: str, system_prompt: str, api_key: str,
) -> tuple[str, int, int]:
    """Send a single request to OpenRouter and return (text, input_tokens, output_tokens)."""
    from openai import APIError, OpenAI

    client = OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL)
    try:
        response = client.chat.completions.create(
            model=MODEL_OPENROUTER,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
    except APIError as exc:
        raise RuntimeError(f"OpenRouter API error: {exc}") from exc
    text = response.choices[0].message.content.strip()
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
    output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
    return text, input_tokens, output_tokens
