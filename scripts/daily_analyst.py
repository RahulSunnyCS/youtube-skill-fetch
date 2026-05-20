#!/usr/bin/env python3
"""
daily_analyst.py — Phase 5–8: fetch today's post-market analyst video,
transcribe it, distill it via the Claude API, summarize it, and append to a
rolling journal.

Designed to run unattended in GitHub Actions once per evening.

Env vars:
    ANALYST_CHANNEL_URL   YouTube channel URL (e.g. https://www.youtube.com/@handle/videos)
    ANTHROPIC_API_KEY     Claude API key
    DAILY_OUT_DIR         (optional) output root, default "daily"
    CLAUDE_MODEL          (optional) default "claude-sonnet-4-6"

Idempotent: if today's folder already exists, exits 0 without re-running.
"""

import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Reuse Phase 1's transcript code.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_playlist import get_transcript  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = REPO_ROOT / "prompts"
DISTILL_PROMPT = (PROMPTS_DIR / "02_distill_video.md").read_text(encoding="utf-8")
SUMMARY_PROMPT = (PROMPTS_DIR / "05_daily_summary.md").read_text(encoding="utf-8")

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")


def log(msg: str) -> None:
    print(f"[daily_analyst] {msg}", flush=True)


def resolve_latest_video(channel_url: str) -> dict | None:
    """Return {id, title, url, upload_date} for the channel's newest upload, or None."""
    # Ensure we're hitting the uploads listing, not a channel home page.
    url = channel_url.rstrip("/")
    if not url.endswith("/videos"):
        url = f"{url}/videos"

    res = subprocess.run(
        ["yt-dlp", "--flat-playlist", "--playlist-end", "1", "--dump-json", url],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        log(f"yt-dlp failed: {res.stderr.strip()[:400]}")
        sys.exit(1)

    line = res.stdout.strip().splitlines()[0] if res.stdout.strip() else ""
    if not line:
        log("yt-dlp returned no entries.")
        return None
    j = json.loads(line)
    vid = j.get("id")
    if not vid:
        return None

    # --flat-playlist often omits upload_date; fetch it with a second cheap call.
    upload_date = j.get("upload_date")
    if not upload_date:
        meta = subprocess.run(
            ["yt-dlp", "--skip-download", "--print", "%(upload_date)s",
             f"https://youtu.be/{vid}"],
            capture_output=True, text=True,
        )
        upload_date = (meta.stdout or "").strip() or None

    return {
        "id": vid,
        "title": j.get("title") or vid,
        "url": j.get("url") or f"https://youtu.be/{vid}",
        "upload_date": upload_date,  # YYYYMMDD or None
    }


def call_claude(client, system_prompt: str, user_text: str) -> str:
    """Single Claude call with prompt caching on the (static) system prompt."""
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_text}],
    )
    return "".join(block.text for block in resp.content if block.type == "text").strip()


def extract_json(text: str) -> dict:
    """Pull the JSON object out of a model response, tolerating code fences."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced:
        return json.loads(fenced.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in model output: {text[:200]}")
    return json.loads(text[start:end + 1])


def prepend_to_journal(journal: Path, date_str: str, video: dict, summary_md: str) -> None:
    entry = (
        f"## {date_str} — {video['title']}\n\n"
        f"[Watch on YouTube]({video['url']})\n\n"
        f"{summary_md.strip()}\n\n"
        f"---\n\n"
    )
    existing = journal.read_text(encoding="utf-8") if journal.exists() else (
        "# Daily analyst journal\n\nNewest first.\n\n---\n\n"
    )
    header, _, rest = existing.partition("---\n\n")
    journal.write_text(header + "---\n\n" + entry + rest, encoding="utf-8")


def main() -> int:
    channel = os.environ.get("ANALYST_CHANNEL_URL")
    if not channel:
        log("ANALYST_CHANNEL_URL not set; nothing to do.")
        return 1

    out_root = Path(os.environ.get("DAILY_OUT_DIR", "daily"))
    out_root.mkdir(parents=True, exist_ok=True)

    today = dt.date.today().strftime("%Y-%m-%d")
    today_compact = today.replace("-", "")
    vdir = out_root / today
    if vdir.exists():
        log(f"{vdir} already exists; skipping (idempotent).")
        return 0

    log(f"Resolving latest video on {channel}...")
    video = resolve_latest_video(channel)
    if not video:
        log("No video resolved.")
        return 0

    log(f"Latest: {video['title']} (id={video['id']}, upload_date={video['upload_date']})")
    if video["upload_date"] and video["upload_date"] != today_compact:
        log(f"Latest upload is {video['upload_date']}, not today ({today_compact}); skipping.")
        return 0

    vdir.mkdir(parents=True, exist_ok=True)

    # Phase 6: transcript (captions only — no Whisper in CI).
    if not get_transcript(video, vdir, whisper_model="base"):
        log("No transcript available yet (captions may still be processing).")
        # Leave the folder so a follow-up manual run can fill it in; but remove
        # if empty so a later cron retries cleanly.
        if not any(vdir.iterdir()):
            vdir.rmdir()
        return 0

    transcript = (vdir / "transcript.txt").read_text(encoding="utf-8")
    if not transcript.strip():
        log("Empty transcript; skipping API calls.")
        return 0

    try:
        from anthropic import Anthropic
    except ImportError:
        log("anthropic SDK not installed. pip install anthropic")
        return 1
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log("ANTHROPIC_API_KEY not set.")
        return 1
    client = Anthropic()

    # Phase 7: distill.
    log("Distilling transcript via Claude...")
    distill_raw = call_claude(client, DISTILL_PROMPT, transcript)
    try:
        distilled = extract_json(distill_raw)
    except (ValueError, json.JSONDecodeError) as e:
        log(f"Failed to parse distillation JSON: {e}")
        (vdir / "distilled.raw.txt").write_text(distill_raw, encoding="utf-8")
        return 1
    distilled.setdefault("video_title", video["title"])
    (vdir / "distilled.json").write_text(
        json.dumps(distilled, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Phase 8: short summary from the distilled JSON.
    log("Summarizing...")
    summary_md = call_claude(
        client, SUMMARY_PROMPT, json.dumps(distilled, ensure_ascii=False)
    )
    (vdir / "summary.md").write_text(summary_md + "\n", encoding="utf-8")

    # Phase 9: journal.
    prepend_to_journal(out_root / "JOURNAL.md", today, video, summary_md)

    log(f"Done. Artifacts in {vdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
