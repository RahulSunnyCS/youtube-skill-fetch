#!/usr/bin/env python3
"""
extract_playlist.py — Local-First Playlist Extractor
=====================================================
Turns a YouTube playlist (or single video, or local file) into a clean,
chunked, paste-ready folder for distilling a creator's domain expertise
into a Claude Skill.

EVERYTHING here runs locally and FREE. No API calls. No paid services.

Pipeline per video:
    1. Get transcript  -> YouTube captions FIRST (free, instant)
                          -> Whisper fallback only if no captions
    2. (optional) Scene-frame extraction for screen-heavy creators
    3. (optional) OCR frames -> on-screen code/text becomes plain text
    4. Write clean, numbered files ready to paste into Claude Pro chat

Output layout:
    output/<playlist_name>/
        00_INDEX.md                  <- overview + paste instructions
        video_01_<slug>/
            transcript.txt
            frames/ scene_001.jpg ...
            ocr.txt                  <- text pulled off the frames
        video_02_<slug>/
            ...

------------------------------------------------------------------------
SETUP (one time, on your Mac):
    brew install yt-dlp ffmpeg tesseract
    pip install openai-whisper youtube-transcript-api imagehash pillow
    # (whisper + transcript-api are only needed for the transcript step;
    #  imagehash + pillow only for frame dedup)
------------------------------------------------------------------------

USAGE:
    # Talking-head creator (transcript only, cheapest/fastest):
    python extract_playlist.py <PLAYLIST_URL> --mode talking-head

    # Screen-heavy creator (transcript + scene frames + OCR):
    python extract_playlist.py <PLAYLIST_URL> --mode screen-heavy

    # A single video:
    python extract_playlist.py <VIDEO_URL> --mode screen-heavy

    # A local file you already have:
    python extract_playlist.py /path/to/video.mp4 --local --mode screen-heavy

OPTIONS:
    --mode {talking-head, screen-heavy}   default: talking-head
    --whisper-model {tiny,base,small,medium}   default: base
    --scene-threshold FLOAT   default: 0.4 (lower=more frames; tune per creator)
    --max-videos INT          cap how many playlist items to process
    --out DIR                 output root (default: ./output)
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ── Pretty console ────────────────────────────────────────────────────────────
C = {
    "cyan": "\033[96m", "green": "\033[92m", "yellow": "\033[93m",
    "red": "\033[91m", "bold": "\033[1m", "dim": "\033[2m", "reset": "\033[0m",
}
def say(msg, color="reset"):  print(f"{C[color]}{msg}{C['reset']}")
def step(msg):                say(f"  → {msg}", "dim")
def ok(msg):                  say(f"  ✓ {msg}", "green")
def warn(msg):                say(f"  ! {msg}", "yellow")
def err(msg):                 say(f"  ✗ {msg}", "red")


# ── Tool availability ───────────────────────────────────────────────────────
def has(tool: str) -> bool:
    return shutil.which(tool) is not None

def require(tool: str):
    if not has(tool):
        err(f"'{tool}' not found. Install it first (see header of this script).")
        sys.exit(1)


# ── Helpers ──────────────────────────────────────────────────────────────────
def slugify(text: str, maxlen: int = 40) -> str:
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:maxlen].strip("-") or "untitled"

def run(cmd: list, capture=True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=capture, text=True)


# ── Stage 0: enumerate playlist ───────────────────────────────────────────────
def enumerate_videos(source: str, is_local: bool, max_videos: int | None):
    """Return list of dicts: {id, title, url} (or local file entry)."""
    if is_local:
        title = Path(source).stem
        return [{"id": "local", "title": title, "url": source, "local_path": source}]

    require("yt-dlp")
    step("Enumerating playlist via yt-dlp...")
    # --flat-playlist is fast: metadata only, no download
    res = run(["yt-dlp", "--flat-playlist", "--dump-json", source])
    if res.returncode != 0:
        err(f"yt-dlp failed:\n{res.stderr.strip()[:400]}")
        sys.exit(1)

    videos = []
    for line in res.stdout.strip().splitlines():
        try:
            j = json.loads(line)
        except json.JSONDecodeError:
            continue
        vid = j.get("id")
        if not vid:
            continue
        videos.append({
            "id": vid,
            "title": j.get("title") or vid,
            "url": j.get("url") or f"https://youtu.be/{vid}",
        })
    if max_videos:
        videos = videos[:max_videos]
    ok(f"Found {len(videos)} video(s).")
    return videos


# Markers that genuinely aren't speech — safe to strip.
# Other bracketed cues like [laughter], [applause], [sighs] carry meaning
# and are kept (they're rare and don't bloat token count materially).
_NOISE_BRACKETS_RE = re.compile(
    r"\[\s*(music|música|musique|musik|silence|no audio)\s*\]",
    re.IGNORECASE,
)


def _fetch_captions(video_id: str) -> tuple[str, list[dict], str] | None:
    """Fetch English captions if available; fall back to default track.

    Returns (cleaned_text, segments, language) or None if nothing usable.
    `segments` is a list of {"start": float, "end": float, "text": str}.
    """
    from youtube_transcript_api import YouTubeTranscriptApi
    api = YouTubeTranscriptApi()

    fetched = None
    language = "unknown"
    try:
        listing = api.list(video_id)
        try:
            track = listing.find_manually_created_transcript(["en", "en-US", "en-GB"])
        except Exception:
            try:
                track = listing.find_generated_transcript(["en", "en-US", "en-GB"])
            except Exception:
                track = None
        if track is not None:
            language = getattr(track, "language_code", "en")
            fetched = track.fetch()
    except Exception:
        pass

    if fetched is None:
        fetched = api.fetch(video_id)  # default track, whatever language

    segments: list[dict] = []
    for s in fetched:
        # youtube_transcript_api exposes start (float seconds) and duration.
        start = float(getattr(s, "start", 0.0))
        dur = float(getattr(s, "duration", 0.0))
        text = (s.text or "").strip()
        if not text:
            continue
        # Apply the same [Music]-style strip we do to the flat text.
        text = _NOISE_BRACKETS_RE.sub("", text).strip()
        if not text:
            continue
        segments.append({"start": start, "end": start + dur, "text": text})

    raw = " ".join(seg["text"] for seg in segments)
    cleaned = re.sub(r"\s+", " ", raw).strip()
    if not cleaned:
        return None
    return cleaned, segments, language


def _write_timestamped(
    vdir: Path,
    *,
    source: str,
    language: str,
    segments: list[dict],
) -> None:
    """Persist transcript.timestamped.json alongside transcript.txt."""
    import json
    payload = {
        "source": source,
        "language": language,
        "segments": segments,
    }
    (vdir / "transcript.timestamped.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── Stage 1: transcript (captions first, Whisper fallback) ─────────────────────
def get_transcript(
    video: dict,
    vdir: Path,
    whisper_model: str,
    *,
    min_caption_words: int = 100,
    force_whisper: bool = False,
) -> bool:
    """Write transcript.txt. Return True on success."""
    tpath = vdir / "transcript.txt"

    # Path 1: YouTube captions (free, instant) — only for real YT videos
    if not force_whisper and video["id"] != "local":
        try:
            captions = _fetch_captions(video["id"])
            if captions:
                text, segments, language = captions
                word_count = len(text.split())
                if word_count < min_caption_words:
                    warn(f"Captions only {word_count} words "
                         f"(below --min-caption-words={min_caption_words}); "
                         f"falling back to Whisper.")
                else:
                    tpath.write_text(text, encoding="utf-8")
                    _write_timestamped(
                        vdir, source="youtube_captions",
                        language=language, segments=segments,
                    )
                    ok(f"Transcript via YouTube captions ({word_count:,} words) — FREE")
                    return True
        except Exception as e:
            warn(f"No captions ({type(e).__name__}); falling back to Whisper.")

    # Path 2: Whisper fallback (free, local, slower)
    # Need a media file. For YT video without captions, download audio first.
    media = video.get("local_path")
    if media is None:
        require("yt-dlp")
        step("Downloading audio for Whisper...")
        audio_out = str(vdir / "audio.%(ext)s")
        res = run(["yt-dlp", "-x", "--audio-format", "wav",
                   "-o", audio_out, video["url"]])
        if res.returncode != 0:
            err("Audio download failed.")
            return False
        cand = list(vdir.glob("audio.*"))
        media = str(cand[0]) if cand else None
        if not media:
            err("Audio file not found after download.")
            return False

    if not has("ffmpeg"):
        require("ffmpeg")
    try:
        import whisper  # openai-whisper
    except ImportError:
        err("openai-whisper not installed and no captions available. "
            "Run: pip install openai-whisper")
        return False

    step(f"Transcribing with Whisper ({whisper_model})... this can take a while")
    model = whisper.load_model(whisper_model)
    result = model.transcribe(media, verbose=False)
    text = re.sub(r"\s+", " ", result["text"]).strip()
    tpath.write_text(text, encoding="utf-8")
    segments = [
        {
            "start": float(seg.get("start", 0.0)),
            "end": float(seg.get("end", 0.0)),
            "text": (seg.get("text") or "").strip(),
        }
        for seg in result.get("segments", [])
        if (seg.get("text") or "").strip()
    ]
    _write_timestamped(
        vdir, source="whisper",
        language=result.get("language", "unknown"),
        segments=segments,
    )
    ok(f"Transcript via Whisper ({len(text.split()):,} words)")
    # tidy: drop the big audio file
    for a in vdir.glob("audio.*"):
        a.unlink(missing_ok=True)
    return True


# ── Stage 2: scene frames (screen-heavy only) ──────────────────────────────────
def extract_frames(media_path: str, vdir: Path, threshold: float) -> int:
    require("ffmpeg")
    fdir = vdir / "frames"
    fdir.mkdir(exist_ok=True)
    step(f"Extracting scene-change frames (threshold={threshold})...")
    run([
        "ffmpeg", "-i", media_path,
        "-vf", f"select='gt(scene,{threshold})'",
        "-vsync", "vfr", str(fdir / "scene_%03d.jpg"), "-y",
    ])
    frames = sorted(fdir.glob("scene_*.jpg"))
    ok(f"Captured {len(frames)} scene frame(s).")
    return len(frames)


# ── Stage 2b: perceptual-hash dedup ────────────────────────────────────────────
def dedup_frames(vdir: Path) -> int:
    fdir = vdir / "frames"
    frames = sorted(fdir.glob("scene_*.jpg"))
    if len(frames) < 2:
        return len(frames)
    try:
        from PIL import Image
        import imagehash
    except ImportError:
        warn("imagehash/pillow not installed; skipping dedup. "
             "(pip install imagehash pillow)")
        return len(frames)

    step("Deduplicating near-identical frames (perceptual hash)...")
    kept, seen = [], []
    for f in frames:
        try:
            h = imagehash.phash(Image.open(f))
        except Exception:
            continue
        if any(abs(h - s) <= 5 for s in seen):   # 5 = similarity tolerance
            f.unlink(missing_ok=True)
        else:
            seen.append(h)
            kept.append(f)
    # renumber survivors
    for i, f in enumerate(kept, 1):
        f.rename(fdir / f"key_{i:03d}.jpg")
    ok(f"Kept {len(kept)} unique frame(s) after dedup.")
    return len(kept)


# ── Stage 3: OCR frames -> text (free, the cost-saving lever) ──────────────────
def ocr_frames(vdir: Path):
    require("tesseract")
    fdir = vdir / "frames"
    frames = sorted(fdir.glob("*.jpg"))
    if not frames:
        return
    step("OCR-ing frames into text (free, replaces paid vision tokens)...")
    chunks = []
    for f in frames:
        res = run(["tesseract", str(f), "stdout"])
        text = (res.stdout or "").strip()
        # keep only frames where OCR found meaningful text
        if len(text) >= 20:
            chunks.append(f"--- {f.name} ---\n{text}")
    if chunks:
        (vdir / "ocr.txt").write_text("\n\n".join(chunks), encoding="utf-8")
        ok(f"OCR text extracted from {len(chunks)} frame(s) -> ocr.txt")
    else:
        warn("No meaningful on-screen text found (likely a talking-head video).")


# ── Index / paste instructions ─────────────────────────────────────────────────
def write_index(root: Path, playlist_name: str, videos: list, mode: str):
    lines = [
        f"# Extraction: {playlist_name}",
        "",
        f"**Mode:** {mode}  |  **Videos:** {len(videos)}",
        "",
        "## How to use with Claude Pro chat (free)",
        "",
        "Work PER VIDEO first (the context window can't hold all transcripts at once):",
        "",
        "1. Open each `video_NN_*/transcript.txt`, paste into Claude, ask it to DISTILL",
        "   into structured JSON (claims, heuristics, reasoning patterns).",
        "2. For screen-heavy videos, also paste that video's `ocr.txt` and/or drag a few",
        "   `frames/key_*.jpg` in alongside the transcript.",
        "3. Save each distilled JSON.",
        "4. Once ALL videos are distilled, paste the small JSONs together and ask Claude",
        "   to SYNTHESIZE — find the patterns that RECUR across videos = the creator's",
        "   core method. That synthesis becomes the SKILL.md.",
        "",
        "## Videos",
        "",
    ]
    for i, v in enumerate(videos, 1):
        lines.append(f"{i:>2}. {v['title']}")
    (root / "00_INDEX.md").write_text("\n".join(lines), encoding="utf-8")


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(
        description="Local-first playlist extractor for YouTuber-skill distillation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("source", help="Playlist URL, video URL, or local file path")
    p.add_argument("--local", action="store_true", help="Source is a local file")
    p.add_argument("--mode", choices=["talking-head", "screen-heavy"],
                   default="talking-head")
    p.add_argument("--whisper-model", default="base",
                   choices=["tiny", "base", "small", "medium"])
    p.add_argument("--scene-threshold", type=float, default=0.4)
    p.add_argument("--max-videos", type=int, default=None)
    p.add_argument("--out", default="output")
    p.add_argument("--min-caption-words", type=int, default=100,
                   help="If YouTube captions produce fewer than this many words, "
                        "fall back to Whisper. Set to 0 to always trust captions.")
    p.add_argument("--force-whisper", action="store_true",
                   help="Skip YouTube captions; always use Whisper.")
    args = p.parse_args()

    say(f"\n{C['bold']}{C['cyan']}━━━ Local Playlist Extractor ━━━{C['reset']}")
    say(f"{C['dim']}Mode: {args.mode}  |  Source: {args.source}{C['reset']}\n")

    videos = enumerate_videos(args.source, args.local, args.max_videos)
    if not videos:
        err("No videos to process.")
        sys.exit(1)

    playlist_name = slugify(
        Path(args.source).stem if args.local else "playlist"
    )
    root = Path(args.out) / playlist_name
    root.mkdir(parents=True, exist_ok=True)

    for i, v in enumerate(videos, 1):
        say(f"\n{C['bold']}[{i}/{len(videos)}] {v['title']}{C['reset']}")
        vdir = root / f"video_{i:02d}_{slugify(v['title'])}"
        vdir.mkdir(exist_ok=True)

        # 1. transcript
        if not get_transcript(
            v, vdir, args.whisper_model,
            min_caption_words=args.min_caption_words,
            force_whisper=args.force_whisper,
        ):
            warn("Skipping video (no transcript).")
            continue

        # 2+3. visuals — only for screen-heavy + only if we have a media file
        if args.mode == "screen-heavy":
            media = v.get("local_path")
            if media is None:
                # download the video for frame extraction
                if has("yt-dlp"):
                    step("Downloading video for frame extraction...")
                    out_tmpl = str(vdir / "video.%(ext)s")
                    run(["yt-dlp", "-f", "worst[ext=mp4]/worst",
                         "-o", out_tmpl, v["url"]])
                    cand = list(vdir.glob("video.*"))
                    media = str(cand[0]) if cand else None
            if media and Path(media).exists():
                extract_frames(media, vdir, args.scene_threshold)
                dedup_frames(vdir)
                ocr_frames(vdir)
                # drop the downloaded video to save disk (keep local originals)
                if v.get("local_path") is None:
                    for f in vdir.glob("video.*"):
                        f.unlink(missing_ok=True)
            else:
                warn("No media available for frames; transcript only.")

    write_index(root, playlist_name, videos, args.mode)
    say(f"\n{C['bold']}{C['green']}━━━ Done ━━━{C['reset']}")
    say(f"Output: {C['cyan']}{root}{C['reset']}")
    say(f"{C['dim']}Open {root}/00_INDEX.md for paste instructions.{C['reset']}\n")


if __name__ == "__main__":
    main()
