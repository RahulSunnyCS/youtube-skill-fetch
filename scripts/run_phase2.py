"""
Phase 2 orchestrator: per-video distillation via the Anthropic SDK.

Reads transcript.clean.txt (produced by preprocess_transcript.py) for
each video under output/<playlist>/ and writes distilled JSON to
distilled/<playlist>/video_NN.json.

Resumable: skips videos whose JSON already exists.
Parallel: runs up to --concurrency calls in flight.
Cached: the Phase 2 system prompt is marked for prompt-cache reuse.
Accounted: writes distilled/<playlist>/cost.json after the run.
Model: read from scope.json's models.phase2 (default Haiku); overridable.

Usage:
    export ANTHROPIC_API_KEY=...
    python scripts/run_phase2.py --playlist <name> [--concurrency 4] [--model ...]
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
import threading
from pathlib import Path

import scope as scope_module
from accounting import CostAccumulator
from claude_client import ClaudeClient


PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "02_distill_video.md"


def load_system_prompt() -> str:
    if not PROMPT_PATH.exists():
        sys.exit(f"Missing prompt file: {PROMPT_PATH}")
    return PROMPT_PATH.read_text()


def find_inputs(playlist_dir: Path) -> list[tuple[str, Path]]:
    """Return (video_id, transcript_path) pairs.

    Prefer transcript.clean.txt; fall back to transcript.txt if the
    cleaned version doesn't exist (user skipped preprocessing).
    """
    pairs: list[tuple[str, Path]] = []
    for video_dir in sorted(playlist_dir.glob("video_*")):
        if not video_dir.is_dir():
            continue
        vid = "_".join(video_dir.name.split("_")[:2])  # video_NN
        clean = video_dir / "transcript.clean.txt"
        raw = video_dir / "transcript.txt"
        chosen = clean if clean.exists() else raw if raw.exists() else None
        if chosen:
            pairs.append((vid, chosen))
    return pairs


def distill_one(
    client: ClaudeClient,
    system_prompt: str,
    video_id: str,
    transcript: Path,
    out_path: Path,
    accumulator: CostAccumulator,
    lock: threading.Lock,
) -> tuple[str, bool, str]:
    if out_path.exists():
        return (video_id, True, "skipped (already exists)")

    transcript_text = transcript.read_text()
    result = client.complete(
        system=system_prompt,
        user=f"Video ID: {video_id}\n\nTranscript:\n\n{transcript_text}",
        cache_system=True,
    )
    with lock:
        accumulator.record(phase="phase2", result=result)

    try:
        json.loads(result.text)
        out_path.write_text(result.text)
        return (video_id, True, f"ok ({result.output_tokens} out tokens)")
    except json.JSONDecodeError:
        out_path.with_suffix(".raw.txt").write_text(result.text)
        return (video_id, False, "non-JSON response; saved as .raw.txt")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--playlist", required=True, help="Playlist name under output/ and distilled/")
    parser.add_argument("--output-root", default="output")
    parser.add_argument("--distilled-root", default="distilled")
    parser.add_argument("--model", help="Override scope.json model for Phase 2")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--videos", help="Comma-separated list to limit to (e.g. video_03,video_07)")
    args = parser.parse_args()

    distilled_root = Path(args.distilled_root)
    playlist_dir = Path(args.output_root) / args.playlist
    distilled_dir = distilled_root / args.playlist
    distilled_dir.mkdir(parents=True, exist_ok=True)

    scope = scope_module.load(distilled_root, args.playlist)
    model = args.model or scope.model_for("phase2")

    if scope.intent == "stats":
        sys.exit("intent=stats does not require Phase 2 (local-only). Use scripts/run_stats.py.")
    if scope.intent == "quote-mining":
        sys.exit("intent=quote-mining is local by default. Use scripts/quote_mine.py.")

    inputs = find_inputs(playlist_dir)
    if not inputs:
        sys.exit(f"No transcripts found under {playlist_dir}")

    if args.videos:
        allow = set(args.videos.split(","))
        inputs = [(vid, t) for vid, t in inputs if vid in allow]
        if not inputs:
            sys.exit(f"No videos matched --videos={args.videos}")

    system_prompt = load_system_prompt()
    client = ClaudeClient(model=model)
    accumulator = CostAccumulator(playlist=args.playlist)
    lock = threading.Lock()

    print(f"Phase 2: model={model}, intent={scope.intent}, "
          f"{len(inputs)} videos, concurrency={args.concurrency}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = []
        for vid, t in inputs:
            out_path = distilled_dir / f"{vid}.json"
            futures.append(pool.submit(
                distill_one, client, system_prompt, vid, t, out_path, accumulator, lock,
            ))
        for fut in concurrent.futures.as_completed(futures):
            name, ok, msg = fut.result()
            marker = "✓" if ok else "✗"
            print(f"  {marker} {name}: {msg}  [running total: ${accumulator.running_total():.4f}]")

    accumulator.write(distilled_dir / "cost.json")
    print(f"\nPhase 2 done. Estimated cost: ${accumulator.running_total():.4f}")
    print(f"Cost breakdown: {distilled_dir / 'cost.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
