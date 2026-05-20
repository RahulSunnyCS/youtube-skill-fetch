# youtube-skill-fetch

Local-first pipeline that distills a YouTube creator's playlist into a reusable
Claude Skill (`SKILL.md`) — capturing HOW they think about their domain.

Mechanical work (downloading, captioning, OCR) runs locally and free.
Only distillation + synthesis use Claude.

> ## ⚠️ Disclaimer — read before use
>
> This project is provided **as-is**, for **personal research, learning,
> and creator-authorized use only**.
>
> - **You are responsible for compliance.** Downloading YouTube content
>   may violate YouTube's Terms of Service unless you own the content,
>   it is Creative Commons licensed, or you have the creator's explicit
>   permission. Operators are solely responsible for their use.
>   See [`docs/PRD.md`](docs/PRD.md) §12 for the full compliance notes.
> - **Do not redistribute raw artifacts.** Transcripts, OCR text, frames,
>   and audio in `output/` must not be committed to public repos or
>   shared. `.gitignore` enforces this by default.
> - **Attribute the creator.** Any `SKILL.md` you publish should credit
>   the source creator and link the source playlist.
> - **Not for commercial repackaging.** If you want to build a paid
>   product, license content directly from creators — see the PRD.
> - **No warranty.** Licensed under Apache-2.0; see [`LICENSE`](LICENSE).
>   The authors accept no liability for misuse.
>
> If you are a creator and want content removed from someone's local
> use of this tool, contact the operator directly. This repository
> distributes code, not content.

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

## Project documents

- [`docs/PRD.md`](docs/PRD.md) — product requirements, phases, cost model, compliance.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — how to contribute.
- [`SECURITY.md`](SECURITY.md) — how to report vulnerabilities.
- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) — community standards.
- [`LICENSE`](LICENSE) — Apache-2.0.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
Code and prompts in this repo are licensed under Apache-2.0. Any
`SKILL.md` you generate by running the pipeline is yours — the license
of the output is whatever you choose, subject to the rights you have in
the source content.
