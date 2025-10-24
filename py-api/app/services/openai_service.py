"""Wrapper utilities around the OpenAI client."""

from __future__ import annotations

import os
from typing import Optional

from openai import OpenAI

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


def get_openai_client() -> OpenAI:
    """Instantiate an OpenAI client using the configured API key."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")
    return OpenAI(api_key=api_key)


def create_response(
    client: OpenAI,
    prompt: str,
    *,
    model: Optional[str] = None,
    max_output_tokens: int = 600,
):
    """Invoke the Responses API with shared defaults."""
    return client.responses.create(
        model=model or DEFAULT_MODEL,
        input=prompt,
        max_output_tokens=max_output_tokens,
    )
