"""
Summary intent orchestrator.

  - Per-video summary via prompts/02_summary.md
  - Playlist-level rollup via prompts/03_summary_rollup.md

Default mode (`claude_code`): emits a single brief at
tasks/<playlist>/summary/BRIEF.md.

API mode (`api`): direct calls to the Anthropic API.

Outputs:
  distilled/<playlist>/summary/video_NN.json
  distilled/<playlist>/summary.md
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
from pathlib import Path

import scope as scope_module
import task_emitter


P2_PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "02_summary.md"
P3_PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "03_summary_rollup.md"


def _find_inputs(playlist_dir: Path) -> list[tuple[str, Path]]:
    out = []
    for vd in sorted(playlist_dir.glob("video_*")):
        if not vd.is_dir():
            continue
        vid = "_".join(vd.name.split("_")[:2])
        clean = vd / "transcript.clean.txt"
        raw = vd / "transcript.txt"
        chosen = clean if clean.exists() else raw if raw.exists() else None
        if chosen:
            out.append((vid, chosen))
    return out


def _summary_one(client, sys_prompt, vid, transcript, out_dir):
    out_path = out_dir / f"{vid}.json"
    if out_path.exists():
        return (vid, True, "skipped")
    res = client.complete(
        system=sys_prompt,
        user=f"Video ID: {vid}\n\nTranscript:\n\n{transcript.read_text()}",
        cache_system=True,
    )
    text = res.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        data = json.loads(text)
        out_path.write_text(json.dumps(data, ensure_ascii=False))
        return (vid, True, "ok")
    except json.JSONDecodeError:
        out_path.with_suffix(".raw.txt").write_text(res.text)
        return (vid, False, "non-JSON; .raw.txt")


def _run_api_mode(args, scope, inputs, p2_sys, p3_sys, summary_dir, distilled_dir) -> int:
    from claude_client import ClaudeClient

    model2 = scope.model_for("phase2")
    model3 = scope.model_for("phase3")
    client2 = ClaudeClient(model=model2)

    print(f"Per-video summary (api): model={model2}, {len(inputs)} videos")
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futs = [
            pool.submit(_summary_one, client2, p2_sys, vid, t, summary_dir)
            for vid, t in inputs
        ]
        for f in concurrent.futures.as_completed(futs):
            vid, ok, msg = f.result()
            print(f"  {'✓' if ok else '✗'} {vid}: {msg}")

    per_video = []
    for jf in sorted(summary_dir.glob("video_*.json")):
        try:
            per_video.append(json.loads(jf.read_text()))
        except json.JSONDecodeError:
            continue
    if not per_video:
        sys.exit("No per-video summaries to roll up.")

    client3 = ClaudeClient(model=model3, max_tokens=4096)
    print(f"\nRollup (api): model={model3}")
    res = client3.complete(
        system=p3_sys,
        user="Per-video summaries:\n\n" + json.dumps(per_video, ensure_ascii=False),
        cache_system=True,
    )
    body = res.text.strip()
    if body.startswith("```"):
        body = body.split("\n", 1)[1].rsplit("```", 1)[0]

    (distilled_dir / "summary.md").write_text(body)
    print(f"\nDone. Wrote {distilled_dir / 'summary.md'}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--playlist", required=True)
    p.add_argument("--output-root", default="output")
    p.add_argument("--distilled-root", default="distilled")
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--mode", choices=sorted(scope_module.VALID_MODES),
                   help="Override scope.json mode (claude_code/api/manual)")
    args = p.parse_args()

    distilled_root = Path(args.distilled_root)
    distilled_dir = distilled_root / args.playlist
    distilled_dir.mkdir(parents=True, exist_ok=True)
    summary_dir = distilled_dir / "summary"
    summary_dir.mkdir(exist_ok=True)

    scope = scope_module.load(distilled_root, args.playlist)
    inputs = _find_inputs(Path(args.output_root) / args.playlist)
    if not inputs:
        sys.exit("No transcripts found.")

    p2_sys = P2_PROMPT.read_text()
    p3_sys = P3_PROMPT.read_text()
    mode = args.mode or scope.mode

    if mode == "claude_code":
        pending = [(vid, t) for vid, t in inputs
                   if not (summary_dir / f"{vid}.json").exists()]
        rollup_path = distilled_dir / "summary.md"
        brief = task_emitter.write_summary_brief(
            playlist=args.playlist,
            inputs=pending or inputs,
            summary_dir=summary_dir,
            rollup_path=rollup_path,
            per_video_prompt=p2_sys,
            rollup_prompt=p3_sys,
        )
        print(f"Summary (claude_code): {len(pending)} videos to summarize, then 1 rollup.")
        task_emitter.announce(brief)
        return 0

    if mode == "manual":
        sys.exit("mode=manual is not implemented yet for summary. Use "
                 "mode=claude_code (default) or mode=api.")

    return _run_api_mode(args, scope, inputs, p2_sys, p3_sys, summary_dir, distilled_dir)


if __name__ == "__main__":
    sys.exit(main())
