"""
Pretty-print compact Phase 2 JSON into the verbose long-key form, for
humans who want to read it. Pure local; reversible.

Usage:
    python scripts/expand_schema.py distilled/<playlist>/video_07.json
    python scripts/expand_schema.py distilled/<playlist>/  # all videos
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


TOP_MAP = {
    "t": "video_title",
    "cc": "core_claims",
    "h": "heuristics",
    "rp": "reasoning_patterns",
    "emph": "what_they_emphasize",
    "dis": "what_they_dismiss",
    "v": "vocabulary",
}

CLAIM_MAP = {"c": "claim", "ev": "evidence_in_transcript", "ts": "timestamp"}
HEUR_MAP = {"r": "rule", "why": "rationale", "ts": "timestamp"}
PAT_MAP = {"p": "pattern", "ex": "example", "ts": "timestamp"}
TERM_MAP = {"term": "term", "m": "meaning_in_their_usage"}


def _expand_list(items, key_map):
    return [{key_map.get(k, k): v for k, v in item.items()} for item in items]


def expand(data: dict) -> dict:
    out: dict = {}
    for short, val in data.items():
        long = TOP_MAP.get(short, short)
        if short == "cc":
            out[long] = _expand_list(val, CLAIM_MAP)
        elif short == "h":
            out[long] = _expand_list(val, HEUR_MAP)
        elif short == "rp":
            out[long] = _expand_list(val, PAT_MAP)
        elif short == "v":
            out[long] = _expand_list(val, TERM_MAP)
        else:
            out[long] = val
    return out


def process(path: Path) -> None:
    if path.is_dir():
        for f in sorted(path.glob("video_*.json")):
            process(f)
        return
    if not path.suffix == ".json":
        return
    data = json.loads(path.read_text())
    print(f"--- {path} ---")
    print(json.dumps(expand(data), indent=2))


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    process(Path(sys.argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
