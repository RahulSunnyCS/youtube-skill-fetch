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
        # Per-video ID for the output JSON filename. Prefer the canonical
        # youtube_id from extraction.json (handles IDs that contain '_').
        # Fall back to splitting the folder name for legacy folders that
        # predate extraction.json.
        vid: str | None = None
        meta_path = video_dir / "extraction.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
                yt_id = meta.get("youtube_id")
                date = meta.get("upload_date") or "00000000"
                if yt_id and yt_id != "local":
                    vid = f"video_{date}_{yt_id}"
            except (json.JSONDecodeError, OSError):
                pass
        if vid is None:
            # Legacy: folder is `video_NN_<slug>` or `video_NN_<id>_<slug>`.
            # Use the first two segments — unique within a single playlist
            # at extraction time, which is the only invariant we have.
            parts = video_dir.name.split("_")
            vid = "_".join(parts[:2])
        clean = video_dir / "transcript.clean.txt"
        raw = video_dir / "transcript.txt"
        chosen = clean if clean.exists() else raw if raw.exists() else None
        if chosen:
            pairs.append((vid, chosen))
    return pairs


# Compact-schema short keys. If Claude returns verbose keys (heuristics
# vs h), we re-prompt once with a stricter instruction before accepting.
_COMPACT_TOP_KEYS = {"t", "cc", "h", "rp", "emph", "dis", "v"}
_VERBOSE_TOP_KEYS = {
    "video_title", "core_claims", "heuristics", "reasoning_patterns",
    "what_they_emphasize", "what_they_dismiss", "vocabulary",
}


def _is_verbose_schema(data: dict) -> bool:
    top = set(data.keys())
    return bool(top & _VERBOSE_TOP_KEYS) and not bool(top & _COMPACT_TOP_KEYS)


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
    user_msg = f"Video ID: {video_id}\n\nTranscript:\n\n{transcript_text}"

    result = client.complete(
        system=system_prompt,
        user=user_msg,
        cache_system=True,
    )
    with lock:
        accumulator.record(phase="phase2", result=result)

    # Try to parse as JSON. If malformed OR verbose-schema, re-prompt once.
    parsed: dict | None = None
    notes: list[str] = []
    try:
        parsed = json.loads(result.text)
    except json.JSONDecodeError:
        notes.append("first call returned non-JSON")

    needs_retry = parsed is None or (isinstance(parsed, dict) and _is_verbose_schema(parsed))
    if needs_retry:
        retry_system = system_prompt + (
            "\n\nIMPORTANT REMINDER: Return ONLY a single JSON object using the "
            "COMPACT short keys exactly (t, cc, h, rp, emph, dis, v). Do not "
            "use verbose names like 'heuristics' or 'core_claims'. No prose, "
            "no markdown code fence."
        )
        result2 = client.complete(
            system=retry_system,
            user=user_msg,
            cache_system=False,  # different system text; don't cache the retry
        )
        with lock:
            accumulator.record(phase="phase2", result=result2)
        try:
            parsed2 = json.loads(result2.text)
            if isinstance(parsed2, dict) and not _is_verbose_schema(parsed2):
                parsed = parsed2
                result = result2
                notes.append("retry succeeded with compact schema")
            elif isinstance(parsed2, dict):
                parsed = parsed2  # still verbose, but at least JSON
                result = result2
                notes.append("retry still verbose-schema; accepting")
        except json.JSONDecodeError:
            notes.append("retry also non-JSON")

    if parsed is None:
        out_path.with_suffix(".raw.txt").write_text(result.text)
        return (video_id, False, "non-JSON response after retry; saved as .raw.txt")

    out_path.write_text(json.dumps(parsed, ensure_ascii=False))
    msg = f"ok ({result.output_tokens} out tokens)"
    if notes:
        msg += f"  [{'; '.join(notes)}]"
    return (video_id, True, msg)


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
