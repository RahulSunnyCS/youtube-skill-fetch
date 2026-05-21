"""
Capture screenshots at moments where the creator says "look at this",
"see this chart", etc. Keyword-based, no Claude.

Reads transcript.timestamped.json (produced by extract_playlist.py),
scans for trigger phrases, clusters nearby hits, downloads the video if
needed, and extracts frames with ffmpeg.

Usage:
    # All videos under a playlist:
    python scripts/capture_screenshots.py --playlist <name>

    # Single video directory:
    python scripts/capture_screenshots.py --video-dir output/<playlist>/video_07_*

    # Custom triggers from a file (one per line):
    python scripts/capture_screenshots.py --playlist <name> --triggers-file my_triggers.txt

Outputs:
    output/<playlist>/video_NN_*/screenshots/001_t0234_look_at_this.jpg
    output/<playlist>/video_NN_*/screenshots.json
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import statistics
import subprocess
import sys
from pathlib import Path


DEFAULT_TRIGGERS = [
    "look at", "look here", "look at this", "look at that",
    "see this", "see here", "see that",
    "as you can see", "as you'll see", "as we can see",
    "on this slide", "on the slide", "on this chart",
    "this chart", "this graph", "this diagram", "this image",
    "right here", "right there",
    "notice", "notice that", "notice how",
    "if you look at", "if you see",
    "watch this", "check this out",
    "pay attention to",
    "the chart shows", "this shows", "the graph shows",
]


def _slug(text: str, limit: int = 30) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return s[:limit] or "frame"


def _safe_name(idx: int, ts: float, trigger: str) -> str:
    return f"{idx:03d}_t{int(ts):04d}_{_slug(trigger)}.jpg"


def load_triggers(path: Path | None) -> list[str]:
    if path is None:
        return list(DEFAULT_TRIGGERS)
    raw = path.read_text(encoding="utf-8").splitlines()
    out = [line.strip().lower() for line in raw if line.strip() and not line.startswith("#")]
    return out or list(DEFAULT_TRIGGERS)


def scan_segments(
    segments: list[dict],
    triggers: list[str],
) -> list[tuple[float, str, str]]:
    """Return (start_seconds, trigger_phrase, segment_text) for each hit."""
    hits: list[tuple[float, str, str]] = []
    # Sort triggers by length so longer phrases win when they share a prefix.
    triggers_sorted = sorted(triggers, key=len, reverse=True)
    for seg in segments:
        text = seg.get("text", "")
        if not text:
            continue
        lowered = text.lower()
        for trig in triggers_sorted:
            if trig in lowered:
                hits.append((float(seg["start"]), trig, text))
                break
    return hits


def cluster_hits(
    hits: list[tuple[float, str, str]],
    *,
    cluster_window: float = 10.0,
) -> list[tuple[float, str, str]]:
    """Collapse hits within `cluster_window` seconds into one at the median."""
    if not hits:
        return []
    hits = sorted(hits, key=lambda h: h[0])
    clusters: list[list[tuple[float, str, str]]] = [[hits[0]]]
    for h in hits[1:]:
        last_cluster = clusters[-1]
        if h[0] - last_cluster[-1][0] <= cluster_window:
            last_cluster.append(h)
        else:
            clusters.append([h])
    out: list[tuple[float, str, str]] = []
    for c in clusters:
        median_ts = statistics.median([item[0] for item in c])
        # Keep the trigger + text of the cluster's middle hit for naming.
        mid = c[len(c) // 2]
        out.append((median_ts, mid[1], mid[2]))
    return out


def context_window(
    segments: list[dict],
    ts: float,
    *,
    seconds: float = 5.0,
) -> str:
    """Return ±seconds of caption text around timestamp ts."""
    lo, hi = ts - seconds, ts + seconds
    picks = [s["text"] for s in segments if s["start"] >= lo and s["start"] <= hi]
    return " ".join(picks).strip()


def ensure_video(video_dir: Path, video_url: str | None) -> Path | None:
    """Return path to a video file in video_dir, downloading via yt-dlp if needed."""
    existing = list(video_dir.glob("video.*"))
    existing = [p for p in existing if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}]
    if existing:
        return existing[0]
    if not video_url:
        return None
    if not shutil.which("yt-dlp"):
        print("ERROR: yt-dlp not on PATH; cannot download video.", file=sys.stderr)
        return None
    out_tpl = str(video_dir / "video.%(ext)s")
    print(f"  ↓ downloading video (720p max) to {out_tpl}")
    res = subprocess.run(
        ["yt-dlp", "-f", "best[height<=720]/best",
         "-o", out_tpl, video_url],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        print(f"ERROR: yt-dlp failed:\n{res.stderr[-500:]}", file=sys.stderr)
        return None
    found = [p for p in video_dir.glob("video.*")
             if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}]
    return found[0] if found else None


def extract_frame(video_path: Path, ts: float, out_path: Path) -> bool:
    if not shutil.which("ffmpeg"):
        print("ERROR: ffmpeg not on PATH.", file=sys.stderr)
        return False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # -ss before -i for fast seek; acceptable accuracy for screenshot purposes.
    res = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y",
         "-ss", f"{ts:.2f}", "-i", str(video_path),
         "-frames:v", "1", "-q:v", "2", str(out_path)],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        print(f"ERROR ffmpeg @ {ts:.2f}s: {res.stderr[-200:]}", file=sys.stderr)
        return False
    return out_path.exists() and out_path.stat().st_size > 0


def load_video_metadata(video_dir: Path) -> dict:
    """Best-effort: read info.json or url file if present."""
    for name in ("info.json", "metadata.json"):
        p = video_dir / name
        if p.exists():
            try:
                return json.loads(p.read_text())
            except Exception:
                pass
    return {}


def process_video(
    video_dir: Path,
    *,
    triggers: list[str],
    cluster_window: float,
    lead_seconds: float,
    max_shots: int,
    skip_download: bool,
) -> dict:
    """Returns a manifest dict for the video."""
    timestamped_path = video_dir / "transcript.timestamped.json"
    if not timestamped_path.exists():
        return {"video_dir": str(video_dir), "error": "no transcript.timestamped.json"}

    data = json.loads(timestamped_path.read_text())
    segments = data.get("segments") or []
    if not segments:
        return {"video_dir": str(video_dir), "error": "empty segments list"}

    raw_hits = scan_segments(segments, triggers)
    clustered = cluster_hits(raw_hits, cluster_window=cluster_window)
    if len(clustered) > max_shots:
        clustered = clustered[:max_shots]

    if not clustered:
        return {"video_dir": str(video_dir), "frames": [], "note": "no triggers matched"}

    meta = load_video_metadata(video_dir)
    video_url = meta.get("url") or meta.get("webpage_url")
    video_path = None if skip_download else ensure_video(video_dir, video_url)
    if video_path is None:
        # Persist a candidates-only manifest so users can preview without downloading.
        candidates = [
            {
                "ts": round(ts, 2),
                "trigger": trig,
                "context": context_window(segments, ts),
            }
            for ts, trig, _ in clustered
        ]
        manifest = {
            "video_dir": str(video_dir),
            "source_segments": str(timestamped_path),
            "trigger_count_raw": len(raw_hits),
            "trigger_count_clustered": len(clustered),
            "candidates_only": True,
            "note": "skip-download set or video not available; no frames extracted",
            "candidates": candidates,
        }
        (video_dir / "screenshots.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2)
        )
        return manifest

    shots_dir = video_dir / "screenshots"
    shots_dir.mkdir(exist_ok=True)
    frames: list[dict] = []
    for idx, (ts, trig, _src_text) in enumerate(clustered, start=1):
        capture_ts = max(0.0, ts + lead_seconds)
        out_path = shots_dir / _safe_name(idx, capture_ts, trig)
        ok_flag = extract_frame(video_path, capture_ts, out_path)
        frames.append({
            "frame": out_path.name,
            "ts": round(capture_ts, 2),
            "trigger_ts": round(ts, 2),
            "trigger": trig,
            "context": context_window(segments, ts),
            "ok": ok_flag,
        })

    manifest_path = video_dir / "screenshots.json"
    manifest = {
        "video_dir": str(video_dir),
        "source_segments": str(timestamped_path),
        "trigger_count_raw": len(raw_hits),
        "trigger_count_clustered": len(clustered),
        "frames": frames,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--playlist", help="Playlist name under output/")
    p.add_argument("--video-dir", help="Single video directory")
    p.add_argument("--output-root", default="output")
    p.add_argument("--triggers-file", type=Path, default=None,
                   help="Text file with one trigger phrase per line (overrides defaults)")
    p.add_argument("--cluster-window", type=float, default=10.0,
                   help="Seconds — collapse hits within this window into one")
    p.add_argument("--lead-seconds", type=float, default=1.5,
                   help="Seconds to wait after the trigger before grabbing the frame")
    p.add_argument("--max-shots", type=int, default=15,
                   help="Cap per video")
    p.add_argument("--skip-download", action="store_true",
                   help="Do not download videos; only emit candidate timestamps")
    args = p.parse_args()

    if not args.playlist and not args.video_dir:
        sys.exit("--playlist or --video-dir is required")

    triggers = load_triggers(args.triggers_file)

    if args.video_dir:
        dirs = [Path(args.video_dir)]
    else:
        root = Path(args.output_root) / args.playlist
        dirs = sorted(d for d in root.glob("video_*") if d.is_dir())
        if not dirs:
            sys.exit(f"No video_* dirs under {root}")

    grand_total = 0
    for vd in dirs:
        m = process_video(
            vd,
            triggers=triggers,
            cluster_window=args.cluster_window,
            lead_seconds=args.lead_seconds,
            max_shots=args.max_shots,
            skip_download=args.skip_download,
        )
        if "error" in m:
            print(f"  ✗ {vd.name}: {m['error']}")
            continue
        if m.get("note") == "no triggers matched":
            print(f"  - {vd.name}: no triggers matched")
        elif m.get("candidates_only"):
            print(f"  · {vd.name}: {m['trigger_count_clustered']} candidates "
                  f"({m['trigger_count_raw']} raw hits) — see screenshots.json")
        else:
            n = len([f for f in m.get("frames", []) if f.get("ok")])
            grand_total += n
            print(f"  ✓ {vd.name}: {n} screenshots ({m.get('trigger_count_raw', 0)} raw hits)")

    print(f"\nDone. {grand_total} screenshots captured across {len(dirs)} videos. $0 spent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
