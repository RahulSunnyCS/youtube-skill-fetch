"""
Phase 3 orchestrator: cross-video synthesis.

Reads every distilled/<playlist>/video_NN.json, sends them to Claude with
prompts/03_synthesize.md, writes synthesis.json. Uses prompt caching on
the per-video JSON corpus so iterating on Phase 4 / prompt edits is cheap.

Usage:
    export ANTHROPIC_API_KEY=...
    python scripts/run_phase3.py --playlist <name> [--model ...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import scope as scope_module
from accounting import CostAccumulator
from claude_client import ClaudeClient


PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "03_synthesize.md"


def load_per_video(distilled_dir: Path) -> tuple[list[dict], list[str]]:
    """Return (json_objects, file_names). Skip files that don't parse."""
    items: list[dict] = []
    names: list[str] = []
    for p in sorted(distilled_dir.glob("video_*.json")):
        try:
            items.append(json.loads(p.read_text()))
            names.append(p.stem)
        except json.JSONDecodeError:
            print(f"  warn: {p.name} does not parse as JSON; skipping")
    return items, names


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--playlist", required=True)
    p.add_argument("--distilled-root", default="distilled")
    p.add_argument("--model", help="Override scope.json model for Phase 3")
    p.add_argument("--force", action="store_true",
                   help="Overwrite an existing synthesis.json")
    args = p.parse_args()

    distilled_root = Path(args.distilled_root)
    distilled_dir = distilled_root / args.playlist
    if not distilled_dir.exists():
        sys.exit(f"No distilled dir: {distilled_dir}")

    out_path = distilled_dir / "synthesis.json"
    if out_path.exists() and not args.force:
        sys.exit(f"{out_path} already exists. Use --force to overwrite.")

    items, names = load_per_video(distilled_dir)
    if len(items) < 2:
        sys.exit(f"Need at least 2 per-video JSONs for synthesis; found {len(items)}.")

    scope = scope_module.load(distilled_root, args.playlist)
    model = args.model or scope.model_for("phase3")

    if not PROMPT_PATH.exists():
        sys.exit(f"Missing prompt: {PROMPT_PATH}")
    system_prompt = PROMPT_PATH.read_text()

    # The full per-video corpus is the cacheable bulk content; goes in user msg.
    payload = {
        "playlist": args.playlist,
        "video_count": len(items),
        "video_ids": names,
        "per_video": items,
    }
    user_msg = (
        "Per-video distillations (compact short-key schema):\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )

    client = ClaudeClient(model=model, max_tokens=8192)
    accumulator = CostAccumulator(playlist=args.playlist)

    print(f"Phase 3: model={model}, {len(items)} videos")
    result = client.complete(system=system_prompt, user=user_msg, cache_system=True)
    accumulator.record(phase="phase3", result=result)

    text = result.text.strip()
    # Be forgiving about an accidental code fence.
    if text.startswith("```"):
        text = text.split("```", 2)[-1]
        text = text.lstrip("json").strip()
        text = text.rsplit("```", 1)[0].strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        (distilled_dir / "synthesis.raw.txt").write_text(result.text)
        sys.exit(f"Synthesis output did not parse as JSON: {e}. "
                 f"Raw response at {distilled_dir / 'synthesis.raw.txt'}.")

    out_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2))
    accumulator.write(distilled_dir / "cost.json")
    print(f"\nPhase 3 done. Synthesis at {out_path}.")
    print(f"  Estimated cost: ${accumulator.running_total():.4f} "
          f"(cumulative across phases: see {distilled_dir / 'cost.json'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
