"""
Per-model Claude pricing table (USD per million tokens).

Hand-maintained on purpose: fetching live prices is brittle and prices
change rarely. Update this dict when Anthropic adjusts pricing.

Last reviewed: 2026-05.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPrice:
    """Prices in USD per 1M tokens."""
    input_per_m: float
    output_per_m: float
    cache_read_per_m: float
    cache_write_per_m: float


# Keys match the model IDs passed to the SDK.
PRICES: dict[str, ModelPrice] = {
    "claude-opus-4-7": ModelPrice(15.00, 75.00, 1.50, 18.75),
    "claude-sonnet-4-6": ModelPrice(3.00, 15.00, 0.30, 3.75),
    "claude-haiku-4-5-20251001": ModelPrice(1.00, 5.00, 0.10, 1.25),
}

DEFAULT_PRICE = ModelPrice(3.00, 15.00, 0.30, 3.75)


def price_for(model: str) -> ModelPrice:
    return PRICES.get(model, DEFAULT_PRICE)


def cost_usd(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    p = price_for(model)
    return (
        input_tokens * p.input_per_m
        + output_tokens * p.output_per_m
        + cache_read_tokens * p.cache_read_per_m
        + cache_write_tokens * p.cache_write_per_m
    ) / 1_000_000
