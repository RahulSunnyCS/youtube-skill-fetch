"""
Phase 2 orchestrator: per-video distillation.

Default mode (`claude_code`): emits a single self-contained brief at
tasks/<playlist>/phase2/BRIEF.md and tells the user to hand it off to
their Claude Code session. No API key required.

API mode (`api`): direct calls to the Anthropic API, resumable, parallel,
prompt-cached. Needs ANTHROPIC_API_KEY.

Mode is read from scope.json's `mode` field (set via scope_init.py) and
can be overridden with --mode.

Reads transcript.clean.txt (preferred) or transcript.txt under
output/<playlist>/ and writes distilled JSON to
distilled/<playlist>/video_NN.json.

Usage:
    # default (uses Claude Code session, no API key needed):
    python scripts/run_phase2.py --playlist <name>

    # API mode (existing behaviour):
    export ANTHROPIC_API_KEY=...
    python scripts/run_phase2.py --playlist <name> --mode api [--concurrency 4]
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
from pathlib import Path

import scope as scope_module
import task_emitter


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
    client,
    system_prompt: str,
    video_id: str,
    transcript: Path,
    out_path: Path,
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
            cache_system=False,
        )
        try:
            parsed2 = json.loads(result2.text)
            if isinstance(parsed2, dict) and not _is_verbose_schema(parsed2):
                parsed = parsed2
                result = result2
                notes.append("retry succeeded with compact schema")
            elif isinstance(parsed2, dict):
                parsed = parsed2
                result = result2
                notes.append("retry still verbose-schema; accepting")
        except json.JSONDecodeError:
            notes.append("retry also non-JSON")

    if parsed is None:
        out_path.with_suffix(".raw.txt").write_text(result.text)
        return (video_id, False, "non-JSON response after retry; saved as .raw.txt")

    out_path.write_text(json.dumps(parsed, ensure_ascii=False))
    msg = "ok"
    if notes:
        msg += f"  [{'; '.join(notes)}]"
    return (video_id, True, msg)


def _run_api_mode(args, scope, inputs, system_prompt, distilled_dir) -> int:
    from claude_client import ClaudeClient

    model = args.model or scope.model_for("phase2")
    client = ClaudeClient(model=model)

    print(f"Phase 2 (api): model={model}, intent={scope.intent}, "
          f"{len(inputs)} videos, concurrency={args.concurrency}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = []
        for vid, t in inputs:
            out_path = distilled_dir / f"{vid}.json"
            futures.append(pool.submit(
                distill_one, client, system_prompt, vid, t, out_path,
            ))
        for fut in concurrent.futures.as_completed(futures):
            name, ok, msg = fut.result()
            marker = "✓" if ok else "✗"
            print(f"  {marker} {name}: {msg}")

    print("\nPhase 2 done.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--playlist", required=True, help="Playlist name under output/ and distilled/")
    parser.add_argument("--output-root", default="output")
    parser.add_argument("--distilled-root", default="distilled")
    parser.add_argument("--model", help="(api mode) Override scope.json model for Phase 2")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--videos", help="Comma-separated list to limit to (e.g. video_03,video_07)")
    parser.add_argument("--mode", choices=sorted(scope_module.VALID_MODES),
                        help="Override scope.json mode (claude_code/api/manual)")
    args = parser.parse_args()

    distilled_root = Path(args.distilled_root)
    playlist_dir = Path(args.output_root) / args.playlist
    distilled_dir = distilled_root / args.playlist
    distilled_dir.mkdir(parents=True, exist_ok=True)

    scope = scope_module.load(distilled_root, args.playlist)
    mode = args.mode or scope.mode

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

    if mode == "claude_code":
        # Filter to videos that still need processing (resumable preview).
        pending = [(vid, t) for vid, t in inputs
                   if not (distilled_dir / f"{vid}.json").exists()]
        done = len(inputs) - len(pending)
        if not pending:
            print(f"Phase 2: all {len(inputs)} videos already have outputs at "
                  f"{distilled_dir}. Nothing to do.")
            return 0
        brief = task_emitter.write_phase2_brief(
            playlist=args.playlist,
            inputs=pending,
            distilled_dir=distilled_dir,
            system_prompt=system_prompt,
        )
        print(f"Phase 2 (claude_code): {len(pending)} videos to process"
              f"{f' ({done} already done — skipped)' if done else ''}.")
        task_emitter.announce(brief)
        return 0

    if mode == "manual":
        sys.exit("mode=manual is not implemented yet for Phase 2. Use "
                 "mode=claude_code (default) or mode=api, or follow the "
                 "copy-paste instructions in README.md.")

    return _run_api_mode(args, scope, inputs, system_prompt, distilled_dir)


if __name__ == "__main__":
    sys.exit(main())
