"""
Compare two synthesis.json snapshots and emit a CHANGELOG entry.

Typical use: re-run extract → preprocess → phase2 → phase3 against a
playlist that has grown over time, then run this to see what changed in
the creator's recurring patterns.

Usage:
    python scripts/diff_synthesis.py --old <path> --new <path> [--out CHANGELOG.md]

If --out is provided, the diff is *prepended* to the existing file so
recent changes appear first.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _index_by_rule(items: list[dict], key_field: str) -> dict[str, dict]:
    return {item.get(key_field, "").strip().lower(): item
            for item in items if item.get(key_field)}


def _diff_lists(old: list[dict], new: list[dict], key_field: str) -> dict:
    old_idx = _index_by_rule(old, key_field)
    new_idx = _index_by_rule(new, key_field)
    added = [new_idx[k] for k in new_idx if k not in old_idx]
    removed = [old_idx[k] for k in old_idx if k not in new_idx]
    confidence_changes = []
    for k in set(old_idx) & set(new_idx):
        oc = (old_idx[k].get("confidence") or "").lower()
        nc = (new_idx[k].get("confidence") or "").lower()
        if oc != nc:
            confidence_changes.append({
                "label": old_idx[k].get(key_field),
                "old": oc, "new": nc,
            })
    return {"added": added, "removed": removed, "confidence_changes": confidence_changes}


def diff_synth(old: dict, new: dict) -> dict:
    return {
        "playlist": new.get("playlist") or old.get("playlist"),
        "video_count_old": old.get("video_count"),
        "video_count_new": new.get("video_count"),
        "heuristics": _diff_lists(
            old.get("recurring_heuristics") or [],
            new.get("recurring_heuristics") or [],
            key_field="rule",
        ),
        "patterns": _diff_lists(
            old.get("recurring_reasoning_patterns") or [],
            new.get("recurring_reasoning_patterns") or [],
            key_field="pattern",
        ),
    }


def render(diff: dict) -> str:
    when = datetime.now(timezone.utc).isoformat()
    lines = [
        f"## Diff @ {when}",
        f"- Playlist: `{diff['playlist']}`",
        f"- Video count: {diff['video_count_old']} → {diff['video_count_new']}",
        "",
    ]

    def section(label: str, body: dict) -> None:
        added, removed, confidence = body["added"], body["removed"], body["confidence_changes"]
        if not added and not removed and not confidence:
            return
        lines.append(f"### {label}")
        if added:
            lines.append("**Added:**")
            for item in added:
                lab = item.get("rule") or item.get("pattern") or "?"
                conf = item.get("confidence", "")
                lines.append(f"- ➕ {lab}  _(conf: {conf})_")
        if removed:
            lines.append("**Removed:**")
            for item in removed:
                lab = item.get("rule") or item.get("pattern") or "?"
                lines.append(f"- ➖ {lab}")
        if confidence:
            lines.append("**Confidence shifts:**")
            for c in confidence:
                lines.append(f"- 🔄 {c['label']}: {c['old']} → {c['new']}")
        lines.append("")

    section("Heuristics", diff["heuristics"])
    section("Reasoning patterns", diff["patterns"])
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--old", required=True, type=Path)
    p.add_argument("--new", required=True, type=Path)
    p.add_argument("--out", type=Path,
                   help="CHANGELOG.md to prepend diff entry to. "
                        "If omitted, diff is printed to stdout.")
    args = p.parse_args()

    if not args.old.exists() or not args.new.exists():
        sys.exit("Both --old and --new must exist.")

    old = json.loads(args.old.read_text())
    new = json.loads(args.new.read_text())
    diff = diff_synth(old, new)
    body = render(diff)

    if args.out:
        prior = args.out.read_text() if args.out.exists() else ""
        if not prior.startswith("#"):
            prior = f"# Synthesis changelog\n\n{prior}"
        args.out.write_text(prior.split("\n\n", 1)[0] + "\n\n" + body + "\n" +
                            ("\n\n".join(prior.split("\n\n", 1)[1:]) if "\n\n" in prior else ""))
        print(f"Prepended diff to {args.out}")
    else:
        print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
