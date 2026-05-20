"""
Eval harness: hold-one-out scoring.

Workflow:
  1. Pick a held-out video (default: the last one numerically).
  2. Re-synthesise + author SKILL.md using only the other N-1 videos.
  3. Send SKILL.md + held-out transcript to Claude with prompts/05_eval_rubric.md.
  4. Write distilled/<playlist>/score.json.

Limitations: this is a meta-eval (Claude scoring Claude), which has known
biases. Use it as a relative signal across runs, not an absolute quality
score. Pair with manual inspection.

Usage:
    python scripts/run_eval.py --playlist <name> [--holdout video_07]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import scope as scope_module


P5_PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "05_eval_rubric.md"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--playlist", required=True)
    p.add_argument("--output-root", default="output")
    p.add_argument("--distilled-root", default="distilled")
    p.add_argument("--holdout", help="video_NN to hold out (default: last)")
    p.add_argument("--skill-path",
                   help="Pre-generated SKILL.md to evaluate. "
                        "If omitted, uses distilled/<playlist>/SKILL.md.")
    p.add_argument("--model", help="(api mode) Override scope.json model for evaluation")
    p.add_argument("--mode", choices=sorted(scope_module.VALID_MODES),
                   help="Override scope.json mode (claude_code/api/manual)")
    args = p.parse_args()

    distilled_root = Path(args.distilled_root)
    distilled_dir = distilled_root / args.playlist
    if not distilled_dir.exists():
        sys.exit(f"No distilled dir: {distilled_dir}")

    skill_path = Path(args.skill_path) if args.skill_path else (distilled_dir / "SKILL.md")
    if not skill_path.exists():
        sys.exit(f"No SKILL.md to evaluate at {skill_path}.")

    # Find candidate held-out video
    playlist_dir = Path(args.output_root) / args.playlist
    video_dirs = sorted(d for d in playlist_dir.glob("video_*") if d.is_dir())
    if not video_dirs:
        sys.exit(f"No videos under {playlist_dir}")

    if args.holdout:
        matches = [d for d in video_dirs if d.name.startswith(args.holdout)]
        if not matches:
            sys.exit(f"--holdout {args.holdout!r} did not match any video dir.")
        holdout_dir = matches[0]
    else:
        holdout_dir = video_dirs[-1]

    transcript_path = holdout_dir / "transcript.clean.txt"
    if not transcript_path.exists():
        transcript_path = holdout_dir / "transcript.txt"
    if not transcript_path.exists():
        sys.exit(f"No transcript in held-out dir {holdout_dir}")

    scope = scope_module.load(distilled_root, args.playlist)
    mode = args.mode or scope.mode

    system_prompt = P5_PROMPT.read_text()
    skill_text = skill_path.read_text()
    transcript_text = transcript_path.read_text()
    user_msg = (
        f"SKILL.md:\n\n{skill_text}\n\n"
        f"---\n\n"
        f"Held-out video transcript ({holdout_dir.name}):\n\n{transcript_text}"
    )
    score_path = distilled_dir / "score.json"

    if mode == "claude_code":
        brief_dir = Path("tasks") / args.playlist / "eval"
        brief_dir.mkdir(parents=True, exist_ok=True)
        brief = brief_dir / "BRIEF.md"
        brief.write_text(f"""# Eval — hold-one-out scoring

You are Claude Code in the user's session. Score the SKILL.md by
predicting what it would say about a held-out video.

## How to process

1. Read the SKILL.md at `{skill_path}`.
2. Read the held-out transcript at `{transcript_path}`.
3. Apply the system prompt below.
4. Write the resulting JSON score record to `{score_path}`. Include
   these top-level keys in addition to whatever the prompt produces:
   - `playlist`: `{args.playlist}`
   - `held_out_video`: `{holdout_dir.name}`
   - `skill_path`: `{skill_path}`

## System prompt

```
{system_prompt.rstrip()}
```
""")
        print(f"Eval (claude_code): held-out={holdout_dir.name}")
        from task_emitter import announce
        announce(brief)
        return 0

    if mode == "manual":
        sys.exit("mode=manual is not implemented yet for eval. Use "
                 "mode=claude_code (default) or mode=api.")

    # api mode
    from claude_client import ClaudeClient
    model = args.model or scope.model_for("phase3")
    client = ClaudeClient(model=model, max_tokens=2048)

    print(f"Eval (api): model={model}, held-out={holdout_dir.name}")
    result = client.complete(system=system_prompt, user=user_msg, cache_system=False)

    text = result.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]

    try:
        score = json.loads(text)
    except json.JSONDecodeError:
        (distilled_dir / "score.raw.txt").write_text(result.text)
        sys.exit(f"Eval output did not parse. Raw at {distilled_dir / 'score.raw.txt'}.")

    score_record = {
        "playlist": args.playlist,
        "held_out_video": holdout_dir.name,
        "model": model,
        "skill_path": str(skill_path),
        **score,
    }
    score_path.write_text(json.dumps(score_record, indent=2))

    overall = score.get("scores", {}).get("overall")
    print(f"\nDone. Overall: {overall}")
    print(f"  Wrote {score_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
