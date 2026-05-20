# youtube-skill-fetch

Local-first pipeline that distills a YouTube creator's playlist into a reusable
Claude Skill (`SKILL.md`) — capturing HOW they think about their domain.

Mechanical work (downloading, captioning, OCR) runs locally and free.
Only distillation + synthesis use Claude.

## Layout

```
scripts/extract_playlist.py   # Phase 1: yt-dlp + captions/Whisper -> transcripts
prompts/02_distill_video.md   # Phase 2: per-video transcript -> JSON
prompts/03_synthesize.md      # Phase 3: aggregate JSONs -> ranked recurring patterns
prompts/04_author_skill.md    # Phase 4: synthesis + mode -> SKILL.md
output/<playlist>/video_NN_*/transcript.txt   # Phase 1 artifacts
distilled/<playlist>/video_NN.json            # Phase 2 artifacts
distilled/<playlist>/synthesis.json           # Phase 3 artifact
distilled/<playlist>/SKILL.md                 # Phase 4 artifact
```

## Setup (local, one time)

```
brew install yt-dlp ffmpeg tesseract     # tesseract only needed for screen-heavy
pip install -r requirements.txt
# whisper only needed if a video has no captions:
# pip install openai-whisper
```

## Pipeline

1. **Extract** (local, deterministic):
   ```
   make test1                                  # 1-video sanity check
   make extract                                # full playlist
   ```
   Pause here, eyeball `output/<playlist>/video_01_*/transcript.txt`.

2. **Distill per video** (Claude, map): for each `transcript.txt`, run the
   prompt in `prompts/02_distill_video.md`. Save output to
   `distilled/<playlist>/video_NN.json`.

3. **Synthesize** (Claude, reduce): concatenate the per-video JSONs and run
   `prompts/03_synthesize.md`. Save to `distilled/<playlist>/synthesis.json`.
   **Human review gate** — verify recurring patterns look right before Phase 4.

4. **Author SKILL.md** (Claude): pick a mode (`Teacher` / `Reviewer` /
   `Advisor`), run `prompts/04_author_skill.md`. Save to
   `distilled/<playlist>/SKILL.md`.

## Modes

- **Teacher** — the skill applies the creator's method to produce new artifacts.
- **Reviewer** — the skill critiques the user's drafts in the creator's style.
- **Advisor** — the skill recommends what the creator would do.
