"""
Thin adapter over the Anthropic Python SDK.

Why an adapter:
- Phases 2-4 should not know whether they're calling the SDK, direct HTTP,
  or a mock. This file is the single seam.
- Lets us swap models / providers / mocks without touching pipeline code.

Usage:
    from scripts.claude_client import ClaudeClient
    client = ClaudeClient(model="claude-sonnet-4-6")
    text = client.complete(
        system="You are a careful distiller.",
        user="...transcript...",
        cache_system=True,
    )

Environment:
    ANTHROPIC_API_KEY must be set. The adapter never logs the key.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class CompletionResult:
    text: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    model: str


class ClaudeClient:
    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 4096,
        max_retries: int = 4,
    ) -> None:
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise RuntimeError(
                "anthropic package not installed. "
                "Run: pip install anthropic"
            ) from exc

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. "
                "Export it before running phases 2-4."
            )

        self._client = Anthropic()
        self.model = model
        self.max_tokens = max_tokens
        self.max_retries = max_retries

    def complete(
        self,
        *,
        system: str,
        user: str,
        cache_system: bool = True,
        max_tokens: Optional[int] = None,
    ) -> CompletionResult:
        """One round-trip. Retries with exponential backoff on transient errors."""
        from anthropic import APIError, RateLimitError

        if cache_system:
            system_param = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system_param = system

        delay = 2.0
        last_exc: Optional[Exception] = None
        for _ in range(self.max_retries):
            try:
                resp = self._client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens or self.max_tokens,
                    system=system_param,
                    messages=[{"role": "user", "content": user}],
                )
                usage = resp.usage
                return CompletionResult(
                    text=resp.content[0].text,
                    input_tokens=getattr(usage, "input_tokens", 0),
                    output_tokens=getattr(usage, "output_tokens", 0),
                    cache_read_tokens=getattr(
                        usage, "cache_read_input_tokens", 0
                    ),
                    cache_write_tokens=getattr(
                        usage, "cache_creation_input_tokens", 0
                    ),
                    model=self.model,
                )
            except (RateLimitError, APIError) as exc:
                last_exc = exc
                time.sleep(delay)
                delay *= 2

        raise RuntimeError(
            f"Anthropic API call failed after {self.max_retries} retries"
        ) from last_exc
