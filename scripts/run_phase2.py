"""
Phase 2 orchestrator: per-video distillation via the Anthropic SDK.

Reads every transcript under output/<playlist>/video_NN_*/transcript.txt
and writes distilled JSON to distilled/<playlist>/video_NN.json.

Resumable: skips videos whose JSON already exists.
Parallel: runs up to --concurrency calls in flight.
Cached: the Phase 2 system prompt is marked for prompt-cache reuse.

Usage:
    export ANTHROPIC_API_KEY=...
    python scripts/run_phase2.py --playlist <name> [--concurrency 4] [--model claude-sonnet-4-6]
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
from pathlib import Path

from claude_client import ClaudeClient


PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "02_distill_video.md"


def load_system_prompt() -> str:
    if not PROMPT_PATH.exists():
        sys.exit(f"Missing prompt file: {PROMPT_PATH}")
    return PROMPT_PATH.read_text()


def find_transcripts(playlist_dir: Path) -> list[Path]:
    return sorted(playlist_dir.glob("video_*/transcript.txt"))


def video_id_from_transcript(transcript: Path) -> str:
    # output/<playlist>/video_NN_<slug>/transcript.txt -> video_NN
    parts = transcript.parent.name.split("_")
    return f"{parts[0]}_{parts[1]}"


def distill_one(
    client: ClaudeClient,
    system_prompt: str,
    transcript: Path,
    out_path: Path,
) -> tuple[str, bool, str]:
    if out_path.exists():
        return (out_path.name, True, "skipped (already exists)")

    transcript_text = transcript.read_text()
    result = client.complete(
        system=system_prompt,
        user=f"Transcript:\n\n{transcript_text}",
        cache_system=True,
    )

    # The prompt is expected to return JSON. Be forgiving: try to parse;
    # if it doesn't parse, save the raw text under a .raw.txt sibling so
    # the user can see what came back.
    try:
        json.loads(result.text)
        out_path.write_text(result.text)
    except json.JSONDecodeError:
        out_path.with_suffix(".raw.txt").write_text(result.text)
        return (out_path.name, False, "non-JSON response; saved as .raw.txt")

    return (out_path.name, True, f"ok ({result.output_tokens} out tokens)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--playlist", required=True, help="Playlist directory name under output/")
    parser.add_argument("--output-root", default="output")
    parser.add_argument("--distilled-root", default="distilled")
    parser.add_argument("--model", default="claude-sonnet-4-6")
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()

    playlist_dir = Path(args.output_root) / args.playlist
    distilled_dir = Path(args.distilled_root) / args.playlist
    distilled_dir.mkdir(parents=True, exist_ok=True)

    transcripts = find_transcripts(playlist_dir)
    if not transcripts:
        sys.exit(f"No transcripts found under {playlist_dir}")

    system_prompt = load_system_prompt()
    client = ClaudeClient(model=args.model)

    print(f"Phase 2: {len(transcripts)} transcripts, concurrency={args.concurrency}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = []
        for t in transcripts:
            vid = video_id_from_transcript(t)
            out_path = distilled_dir / f"{vid}.json"
            futures.append(pool.submit(distill_one, client, system_prompt, t, out_path))

        for fut in concurrent.futures.as_completed(futures):
            name, ok, msg = fut.result()
            marker = "✓" if ok else "✗"
            print(f"  {marker} {name}: {msg}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
