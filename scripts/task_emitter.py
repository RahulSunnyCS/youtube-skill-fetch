"""
Task emitter: writes Claude-Code-ready briefs for each phase.

When `mode == "claude_code"` in scope.json, the phase runners delegate
the actual Claude calls to the user's Claude Code session. Instead of
hitting the Anthropic API, the runner emits a single self-contained
`BRIEF.md` under `tasks/<playlist>/<phase>/` that the user hands off
to Claude Code with one sentence:

    > Process tasks/<playlist>/phase2/BRIEF.md

The brief contains the system prompt inline, the list of inputs to
read, and the exact output paths to write. Resumability is preserved
because Claude Code is told to skip tasks whose outputs already exist.

This file is intentionally framework-free (stdlib only).
"""

from __future__ import annotations

from pathlib import Path


def tasks_root(playlist: str, phase: str, root: Path | str = "tasks") -> Path:
    return Path(root) / playlist / phase


def _ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def _verify_section(playlist: str, phase: str) -> str:
    return (
        "## After you finish\n\n"
        f"Confirm with the user that {phase} is done. The user can spot-check "
        "one output to validate the schema before moving to the next phase.\n"
    )


def write_phase2_brief(
    playlist: str,
    inputs: list[tuple[str, Path]],
    distilled_dir: Path,
    system_prompt: str,
    tasks_root_path: Path | str = "tasks",
) -> Path:
    """Emit tasks/<playlist>/phase2/BRIEF.md for Claude Code to process."""
    out_dir = _ensure_dir(tasks_root(playlist, "phase2", tasks_root_path))
    brief = out_dir / "BRIEF.md"

    rows = []
    for vid, transcript_path in inputs:
        output_path = distilled_dir / f"{vid}.json"
        rows.append((vid, transcript_path, output_path))

    table = "\n".join(
        f"| {vid} | `{tp}` | `{op}` |" for vid, tp, op in rows
    )

    body = f"""# Phase 2 — per-video distillation ({len(rows)} videos)

You are Claude Code running in the user's session. Process every task
listed in the **Tasks** table below. The user has asked you to do
Phase 2 of the youtube-skill-fetch pipeline for playlist
`{playlist}`.

## How to process each task

For each row in the table:

1. **Skip if done.** If the output file already exists, skip the task.
   Do not overwrite — this loop is resumable.
2. **Read the transcript** at the input path.
3. **Apply the system prompt below** to that transcript.
4. **Parse your response as JSON.** It must be a single JSON object
   using the compact short-key schema described in the system prompt.
5. **Write the JSON** to the output path. No prose, no markdown fence
   in the file — pure JSON.
6. If your response is not valid JSON, save the raw text to a sibling
   `.raw.txt` file and continue to the next task — don't block on one
   failure.

Process tasks in order. You may batch your reads, but write one
output file at a time so the user can see progress.

## System prompt (apply this to every transcript)

```
{system_prompt.rstrip()}
```

## Tasks

| Video | Input (read) | Output (write) |
|-------|--------------|----------------|
{table}

{_verify_section(playlist, "Phase 2")}"""

    brief.write_text(body)
    return brief


def write_phase3_brief(
    playlist: str,
    per_video_paths: list[Path],
    out_path: Path,
    system_prompt: str,
    tasks_root_path: Path | str = "tasks",
) -> Path:
    out_dir = _ensure_dir(tasks_root(playlist, "phase3", tasks_root_path))
    brief = out_dir / "BRIEF.md"
    listing = "\n".join(f"- `{p}`" for p in per_video_paths)

    body = f"""# Phase 3 — cross-video synthesis

You are Claude Code in the user's session. Synthesize the per-video
distillations for playlist `{playlist}` into a single
`synthesis.json`.

## How to process

1. **Skip if done.** If `{out_path}` already exists, ask the user
   whether to overwrite before proceeding.
2. **Read all per-video JSONs** listed below. They use the compact
   short-key schema from Phase 2.
3. **Apply the system prompt** to the combined corpus.
4. **Write the result** as a single JSON object to:
   `{out_path}`
5. If your response is not valid JSON, save the raw text to
   `{out_path.with_suffix(".raw.txt")}` and tell the user.

This is the **human review gate** — after you finish, recommend the
user open `synthesis.json` and eyeball the patterns before paying for
Phase 4 (if they're using API mode).

## System prompt

```
{system_prompt.rstrip()}
```

## Inputs (read all of these)

{listing}

## Output (write here)

`{out_path}`

{_verify_section(playlist, "Phase 3")}"""

    brief.write_text(body)
    return brief


def write_phase4_brief(
    playlist: str,
    synthesis_path: Path,
    skill_path: Path,
    system_prompt: str,
    skill_mode: str,
    tasks_root_path: Path | str = "tasks",
) -> Path:
    out_dir = _ensure_dir(tasks_root(playlist, "phase4", tasks_root_path))
    brief = out_dir / "BRIEF.md"

    body = f"""# Phase 4 — author SKILL.md

You are Claude Code in the user's session. Author the final
`SKILL.md` for playlist `{playlist}` from the synthesis.

Skill mode: **{skill_mode}** (one of Teacher / Reviewer / Advisor).

## How to process

1. **Read** `{synthesis_path}`.
2. **Apply the system prompt** with `MODE: {skill_mode}` at the top of
   your reasoning.
3. **Write** the resulting SKILL.md to:
   `{skill_path}`
4. **Strip any `[video_NN @ MM:SS]` markers** the prompt may emit —
   the SKILL.md must be citation-free; citations belong in the
   sidecar.
5. **Versioning.** If `{skill_path}` already exists, bump the
   `version:` in the frontmatter (e.g. 1.0 → 1.1) and back up the old
   file as `SKILL.v<prev>.md` in the same directory.
6. After writing SKILL.md, ask the user to run
   `python scripts/citations.py --playlist {playlist}` to regenerate
   the citations sidecar.

## System prompt

```
{system_prompt.rstrip()}
```

## Input (read this)

`{synthesis_path}`

## Output (write here)

`{skill_path}`

{_verify_section(playlist, "Phase 4")}"""

    brief.write_text(body)
    return brief


def write_topical_brief(
    playlist: str,
    inputs: list[tuple[str, Path]],
    topical_dir: Path,
    report_path: Path,
    question: str,
    extract_prompt: str,
    report_prompt: str,
    tasks_root_path: Path | str = "tasks",
) -> Path:
    out_dir = _ensure_dir(tasks_root(playlist, "topical", tasks_root_path))
    brief = out_dir / "BRIEF.md"

    rows = []
    for vid, transcript_path in inputs:
        output_path = topical_dir / f"{vid}.json"
        rows.append((vid, transcript_path, output_path))
    table = "\n".join(
        f"| {vid} | `{tp}` | `{op}` |" for vid, tp, op in rows
    )

    body = f"""# Topical report — extract + write ({len(rows)} videos)

You are Claude Code in the user's session. Produce a topical report
for playlist `{playlist}` answering the user's question.

## The question

> {question}

This is a two-step task: first extract relevant statements from each
video, then synthesize them into a single report.

---

## Step 1 — Per-video extraction

For each row below, apply the extraction prompt and write a JSON file.
Skip rows whose output already exists.

### Extraction prompt

```
{extract_prompt.rstrip()}
```

Prepend each user message with: `QUESTION: {question}`

### Extraction tasks

| Video | Input (read) | Output (write) |
|-------|--------------|----------------|
{table}

---

## Step 2 — Write the report

Once all extractions are written (or as many as parse), read every
file in `{topical_dir}/video_*.json`, combine them, and apply the
report prompt below. Write the result to `{report_path}`.

### Report prompt

```
{report_prompt.rstrip()}
```

### Final outputs

- `{report_path}` (the report, Markdown)
- After you're done, suggest the user run
  `pandoc {report_path} -o {report_path.with_suffix(".pdf")}` to
  render a PDF if they have pandoc installed.

{_verify_section(playlist, "Topical report")}"""

    brief.write_text(body)
    return brief


def write_summary_brief(
    playlist: str,
    inputs: list[tuple[str, Path]],
    summary_dir: Path,
    rollup_path: Path,
    per_video_prompt: str,
    rollup_prompt: str,
    tasks_root_path: Path | str = "tasks",
) -> Path:
    out_dir = _ensure_dir(tasks_root(playlist, "summary", tasks_root_path))
    brief = out_dir / "BRIEF.md"

    rows = []
    for vid, transcript_path in inputs:
        output_path = summary_dir / f"{vid}.json"
        rows.append((vid, transcript_path, output_path))
    table = "\n".join(
        f"| {vid} | `{tp}` | `{op}` |" for vid, tp, op in rows
    )

    body = f"""# Summary — per-video + playlist rollup ({len(rows)} videos)

You are Claude Code in the user's session. Produce a summary of
playlist `{playlist}`.

This is a two-step task.

---

## Step 1 — Per-video summary

For each row below, apply the per-video prompt and write a JSON file.
Skip rows whose output already exists.

### Per-video prompt

```
{per_video_prompt.rstrip()}
```

### Per-video tasks

| Video | Input (read) | Output (write) |
|-------|--------------|----------------|
{table}

---

## Step 2 — Playlist rollup

After all per-video summaries are written, read every
`{summary_dir}/video_*.json`, combine them, and apply the rollup
prompt. Write the result to `{rollup_path}` (Markdown).

### Rollup prompt

```
{rollup_prompt.rstrip()}
```

### Final output

`{rollup_path}`

{_verify_section(playlist, "Summary")}"""

    brief.write_text(body)
    return brief


def announce(brief_path: Path) -> None:
    """Print a uniform 'tell Claude Code this' message."""
    print()
    print("=" * 64)
    print("BRIEF READY — hand off to Claude Code")
    print("=" * 64)
    print()
    print(f"Brief written to: {brief_path}")
    print()
    print("In your Claude Code session, just say:")
    print()
    print(f"    Process {brief_path}")
    print()
    print("Claude Code will read the brief, do the work locally using")
    print("your subscription, and write outputs to the paths listed in")
    print("the brief. No Anthropic API key needed.")
    print("=" * 64)
