"""
Token + cost accounting. Aggregates CompletionResult objects per phase
and persists a cost.json next to the artifacts.

Usage:
    from accounting import CostAccumulator
    acc = CostAccumulator(playlist="my-playlist")
    acc.record(phase="phase2", result=completion_result)
    print(acc.running_total())
    acc.write(Path("distilled/my-playlist/cost.json"))
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from claude_client import CompletionResult
from pricing import cost_usd


@dataclass
class PhaseTotals:
    model: str = ""
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    def add(self, r: CompletionResult) -> None:
        self.model = r.model
        self.calls += 1
        self.input_tokens += r.input_tokens
        self.output_tokens += r.output_tokens
        self.cache_read_tokens += r.cache_read_tokens
        self.cache_write_tokens += r.cache_write_tokens

    def cost(self) -> float:
        return cost_usd(
            self.model,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cache_read_tokens=self.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens,
        )

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "estimated_cost_usd": round(self.cost(), 4),
        }


@dataclass
class CostAccumulator:
    playlist: str
    phases: dict[str, PhaseTotals] = field(default_factory=dict)

    def record(self, *, phase: str, result: CompletionResult) -> None:
        self.phases.setdefault(phase, PhaseTotals()).add(result)

    def running_total(self) -> float:
        return sum(p.cost() for p in self.phases.values())

    def to_dict(self) -> dict:
        return {
            "playlist": self.playlist,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "phases": {name: p.to_dict() for name, p in self.phases.items()},
            "total_estimated_cost_usd": round(self.running_total(), 4),
        }

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Merge with an existing cost.json so re-running one phase doesn't
        # wipe totals from other phases.
        merged = self.to_dict()
        if path.exists():
            try:
                prior = json.loads(path.read_text())
                for name, totals in prior.get("phases", {}).items():
                    if name not in merged["phases"]:
                        merged["phases"][name] = totals
                merged["total_estimated_cost_usd"] = round(
                    sum(p.get("estimated_cost_usd", 0.0) for p in merged["phases"].values()), 4
                )
            except (json.JSONDecodeError, OSError):
                pass
        path.write_text(json.dumps(merged, indent=2))
