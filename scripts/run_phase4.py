"""
Phase 4 orchestrator: author SKILL.md from synthesis.json.

Reads distilled/<playlist>/synthesis.json, calls Claude with
prompts/04_author_skill.md, and writes:
  - SKILL.md         (citation-free)
  - citations.md     (sidecar, via scripts/citations.py)

Adds a `version` to the SKILL.md frontmatter; on re-runs, increments it
and writes a CHANGELOG.md describing what changed.

Usage:
    export ANTHROPIC_API_KEY=...
    python scripts/run_phase4.py --playlist <name> --mode Teacher
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import scope as scope_module
from accounting import CostAccumulator
from claude_client import ClaudeClient
from citations import build_citations, render_markdown as render_citations_md


PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "04_author_skill.md"


def _read_existing_version(skill_path: Path) -> tuple[int, int]:
    """Return (major, minor) of an existing SKILL.md, or (0, 0)."""
    if not skill_path.exists():
        return (0, 0)
    text = skill_path.read_text(encoding="utf-8")
    m = re.search(r"^version:\s*([0-9]+)\.([0-9]+)", text, re.MULTILINE)
    if not m:
        return (1, 0)
    return (int(m.group(1)), int(m.group(2)))


def _set_version(text: str, version: str) -> str:
    """Replace the {{VERSION}} placeholder or insert version into frontmatter."""
    if "{{VERSION}}" in text:
        return text.replace("{{VERSION}}", version)
    if re.search(r"^version:\s*", text, re.MULTILINE):
        return re.sub(r"^version:\s*.+$", f"version: {version}", text, count=1, flags=re.MULTILINE)
    # Insert after the first frontmatter line (`---`).
    if text.startswith("---"):
        head, _, rest = text[3:].partition("---")
        return f"---{head.rstrip()}\nversion: {version}\n---{rest}"
    return f"---\nversion: {version}\n---\n\n{text}"


def _strip_citation_markers(text: str) -> str:
    """Defensive: remove any [video_NN @ MM:SS] markers the model emits."""
    return re.sub(r"\[\s*video_\d+\s*@\s*[0-9:]+\s*\]", "", text)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--playlist", required=True)
    p.add_argument("--distilled-root", default="distilled")
    p.add_argument("--mode", default="Teacher",
                   choices=["Teacher", "Reviewer", "Advisor"])
    p.add_argument("--model", help="Override scope.json model for Phase 4")
    p.add_argument("--force", action="store_true",
                   help="Overwrite existing SKILL.md (otherwise version-bumps)")
    args = p.parse_args()

    distilled_root = Path(args.distilled_root)
    distilled_dir = distilled_root / args.playlist
    synthesis_path = distilled_dir / "synthesis.json"
    if not synthesis_path.exists():
        sys.exit(f"No synthesis.json at {synthesis_path}. Run run_phase3.py first.")

    scope = scope_module.load(distilled_root, args.playlist)
    model = args.model or scope.model_for("phase4")

    system_prompt = PROMPT_PATH.read_text()
    synthesis_text = synthesis_path.read_text()
    user_msg = (
        f"MODE: {args.mode}\n\n"
        f"Synthesis JSON:\n{synthesis_text}"
    )

    client = ClaudeClient(model=model, max_tokens=8192)
    accumulator = CostAccumulator(playlist=args.playlist)

    print(f"Phase 4: model={model}, mode={args.mode}")
    result = client.complete(system=system_prompt, user=user_msg, cache_system=True)
    accumulator.record(phase="phase4", result=result)

    skill_text = result.text.strip()
    if skill_text.startswith("```"):
        skill_text = skill_text.split("\n", 1)[1].rsplit("```", 1)[0]

    skill_text = _strip_citation_markers(skill_text)

    skill_path = distilled_dir / "SKILL.md"
    major, minor = _read_existing_version(skill_path)
    if skill_path.exists() and not args.force:
        new_version = f"{major}.{minor + 1}"
    else:
        new_version = "1.0"
    skill_text = _set_version(skill_text, new_version)

    # Save previous SKILL.md before overwriting (for diff/audit).
    if skill_path.exists():
        backup = distilled_dir / f"SKILL.v{major}.{minor}.md"
        if not backup.exists():
            backup.write_text(skill_path.read_text())

    skill_path.write_text(skill_text)
    print(f"  Wrote {skill_path} (version {new_version})")

    # Update CHANGELOG.md
    changelog_path = distilled_dir / "CHANGELOG.md"
    when = datetime.now(timezone.utc).isoformat()
    line = f"- **{new_version}** ({when}, mode={args.mode}, model={model})\n"
    if changelog_path.exists():
        changelog_path.write_text(line + changelog_path.read_text())
    else:
        changelog_path.write_text(f"# SKILL.md changelog\n\n{line}")
    print(f"  Updated {changelog_path}")

    # Citations sidecar
    citations = build_citations(distilled_dir)
    (distilled_dir / "citations.json").write_text(
        json.dumps(citations, ensure_ascii=False, indent=2)
    )
    (distilled_dir / "citations.md").write_text(render_citations_md(citations))
    print(f"  Wrote citations.md ({citations['n_entries']} entries)")

    accumulator.write(distilled_dir / "cost.json")
    print(f"\nPhase 4 done. Estimated cost: ${accumulator.running_total():.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
