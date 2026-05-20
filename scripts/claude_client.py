"""
Thin adapter over the Anthropic Python SDK.

Only used when scope.mode == "api". The default mode (claude_code) hands
work off to the user's Claude Code session via a BRIEF.md and never
imports this file.

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
                "Export it before running phases 2-4 in mode=api."
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
                return CompletionResult(
                    text=resp.content[0].text,
                    model=self.model,
                )
            except (RateLimitError, APIError) as exc:
                last_exc = exc
                time.sleep(delay)
                delay *= 2

        raise RuntimeError(
            f"Anthropic API call failed after {self.max_retries} retries"
        ) from last_exc
