"""
Universal citations sidecar.

Walks distilled artifacts (per-video Phase 2 JSONs + synthesis.json) and
builds:
  - citations.json — structured map {claim/heuristic -> [video_NN @ MM:SS]}
  - citations.md   — human-readable version

The Phase 4 outputs (SKILL.md, report.md) are kept citation-free; readers
who want to verify a specific point look in citations.md instead.

Usage:
    python scripts/citations.py --playlist <name>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _format_ts(value) -> str:
    """Accept a string like '02:34' or a number of seconds; emit MM:SS."""
    if value is None:
        return "??:??"
    if isinstance(value, str):
        return value or "??:??"
    try:
        secs = float(value)
        m = int(secs // 60)
        s = int(secs % 60)
        return f"{m:02d}:{s:02d}"
    except (TypeError, ValueError):
        return "??:??"


def _iter_items(per_video: dict, video_id: str):
    """Yield (kind, label, evidence, ts) from a compact-schema video JSON."""
    # cc = core_claims
    for c in per_video.get("cc", []) or []:
        yield ("claim", c.get("c", ""), c.get("ev", ""), c.get("ts"))
    # h = heuristics
    for h in per_video.get("h", []) or []:
        yield ("heuristic", h.get("r", ""), h.get("why", ""), h.get("ts"))
    # rp = reasoning_patterns
    for rp in per_video.get("rp", []) or []:
        yield ("pattern", rp.get("p", ""), rp.get("ex", ""), rp.get("ts"))


def build_citations(distilled_dir: Path) -> dict:
    """Walk per-video JSONs and emit a flat citations dict."""
    entries: list[dict] = []
    for vfile in sorted(distilled_dir.glob("video_*.json")):
        video_id = vfile.stem
        try:
            data = json.loads(vfile.read_text())
        except json.JSONDecodeError:
            continue
        for kind, label, evidence, ts in _iter_items(data, video_id):
            if not label.strip():
                continue
            entries.append({
                "kind": kind,
                "label": label.strip(),
                "evidence": (evidence or "").strip(),
                "video": video_id,
                "timestamp": _format_ts(ts),
            })
    return {
        "playlist_dir": str(distilled_dir),
        "n_entries": len(entries),
        "entries": entries,
    }


def render_markdown(citations: dict) -> str:
    """Group by (kind, label) and list every (video, timestamp) source."""
    by_key: dict[tuple[str, str], list[dict]] = {}
    for e in citations["entries"]:
        key = (e["kind"], e["label"])
        by_key.setdefault(key, []).append(e)

    lines = ["# Citations\n"]
    lines.append(f"_{citations['n_entries']} source entries across "
                 f"{len({e['video'] for e in citations['entries']})} videos._\n")

    for kind in ("claim", "heuristic", "pattern"):
        group = [(k, srcs) for k, srcs in by_key.items() if k[0] == kind]
        if not group:
            continue
        lines.append(f"\n## {kind.capitalize()}s\n")
        for (_, label), srcs in sorted(group, key=lambda x: x[0][1]):
            refs = ", ".join(f"`{s['video']} @ {s['timestamp']}`" for s in srcs)
            lines.append(f"- **{label}** — {refs}")
            for s in srcs:
                if s["evidence"]:
                    lines.append(f"  > {s['evidence']}")
            lines.append("")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--playlist", required=True)
    p.add_argument("--distilled-root", default="distilled")
    args = p.parse_args()

    distilled_dir = Path(args.distilled_root) / args.playlist
    if not distilled_dir.exists():
        sys.exit(f"No distilled dir: {distilled_dir}")

    citations = build_citations(distilled_dir)
    (distilled_dir / "citations.json").write_text(
        json.dumps(citations, ensure_ascii=False, indent=2)
    )
    (distilled_dir / "citations.md").write_text(render_markdown(citations))

    print(f"Wrote {distilled_dir / 'citations.json'}")
    print(f"Wrote {distilled_dir / 'citations.md'}")
    print(f"  {citations['n_entries']} entries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
