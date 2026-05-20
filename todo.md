# todo — next workflow

What's left to build, in priority order. Each item lists what it is, why
it matters, and what files it touches.

---

## Now (next 1–2 sessions)

### 1. Phase 0 interactive scoping CLI
**Why:** Today `scope.json` has to be hand-written. Users won't do that.
**What:** `scripts/scope_init.py` — interactive prompt: intent, language,
depth, themes, question, audience, rights confirmation. Estimates cost
+ time based on playlist length and intent, asks for confirmation,
writes `scope.json` and `consent.json`.
**Touches:** `scripts/scope_init.py` (new), `scripts/scope.py` (already
exists, may need helpers).
**Done when:** `python scripts/scope_init.py --playlist demo` walks the
user through, writes both files, and `run_phase2.py` reads them.

### 2. Phase 3 orchestrator
**Why:** Currently Phase 3 is copy-paste only.
**What:** `scripts/run_phase3.py` — reads all `video_NN.json`, calls
Sonnet with `prompts/03_synthesize.md`, writes `synthesis.json` +
records cost. Uses prompt caching on the per-video JSON corpus so
iterating on the prompt is cheap.
**Touches:** `scripts/run_phase3.py` (new), uses existing
`claude_client.py`, `accounting.py`, `scope.py`.
**Done when:** Phase 2 → Phase 3 runs end-to-end on a small playlist.

### 3. Phase 4 orchestrator
**Why:** Same reason — manual today.
**What:** `scripts/run_phase4.py` — reads `synthesis.json`, takes mode
(`Teacher` / `Reviewer` / `Advisor`), emits `SKILL.md` plus
`citations.md` (split: skill stays citation-free).
**Touches:** `scripts/run_phase4.py` (new), update
`prompts/04_author_skill.md` to emit citation refs separately.
**Done when:** Full method-distillation path runs from extract → SKILL.md.

### 4. Validate + auto-retry on Phase 2 schema regressions
**Why:** Claude occasionally returns verbose keys despite the prompt.
**What:** In `run_phase2.py`, after each call: detect long keys
(`heuristics` vs `h`); if found, re-prompt once with a stricter system
message; if still wrong, accept verbose form and log a warning.
**Touches:** `scripts/run_phase2.py`.
**Done when:** Schema-drift cases produce a warning, not a silent
verbose-form output that costs extra tokens downstream.

---

## Next (after the core path is automated)

### 5. `topical-report` intent — extraction prompt + report writer
**Why:** This is the "what does X think about commodities?" use case.
The biggest UX-shaped feature not yet built.
**What:**
- `prompts/02_topical_extract.md` — extracts only statements relevant
  to `scope.question`.
- `prompts/04_topical_report.md` — writes a structured report with
  deduped/clustered findings.
- `scripts/run_topical.py` — orchestrates the topical-only path.
- Optional: `scripts/render_pdf.py` (pandoc wrapper) for `report.pdf`.
**Done when:** A question like "how is X learning AI?" yields a
readable `report.md` + `report.pdf` with citations.

### 6. `stats` intent — local analyzer
**Why:** PRD specifies $0 cost for this intent; it doesn't exist yet.
**What:** `scripts/run_stats.py` — word/phrase frequency, topic counts,
speaker time (when diarization is added). Outputs `stats.json` and a
human-readable `stats.md`.
**Done when:** `make stats PLAYLIST_NAME=demo TERMS='ai,model'` works
and writes both files.

### 7. `summary` intent
**Why:** Lightweight option for users who don't want a full skill.
**What:** Reuse Phase 2 with a simpler prompt; aggregate per-video
summaries into a playlist-level summary.md.
**Done when:** `intent=summary` produces `summary.md` end-to-end.

### 8. Citation extractor + universal sidecar
**Why:** Per PRD, every Claude-produced artifact should ship a separate
`citations.json` / `citations.md`.
**What:** A small `scripts/citations.py` that walks `SKILL.md` / `report.md`,
finds claims that reference `[video_NN @ MM:SS]` markers in Phase 2
output, and emits a clean sidecar.
**Done when:** Every output has a matching `citations.*` file; SKILL.md
itself stays citation-free.

---

## Quality (cross-cutting)

### ✓ faster-whisper as default backend (done)
**Status:** shipped. `extract_playlist.py` now prefers `faster-whisper`
(~4× faster, half the memory, same model weights) with `openai-whisper`
as a documented fallback. VAD filter enabled by default — cuts the
"hallucination on silence" failure mode. Both backends emit the same
`transcript.timestamped.json` shape via the new
`_transcribe_with_whisper` adapter.

### Whisper quality follow-ups (open)

These are the upgrades the adapter pattern unlocks. Each is independent.

- **WhisperX** — runs faster-whisper then forced-alignment via wav2vec2
  for word-level timestamps (±20ms vs Whisper's ±500ms) and bundles
  speaker diarization. Add as a `--whisperx` flag, not default —
  heavier (extra alignment + diarization models). Big win when:
  (a) screenshots need to land on the exact frame the speaker references,
  (b) interview/panel content needs `Host`/`Guest 1` labels.
  Subsumes item 9 (Speaker diarization) below — consider merging.

- **`--whisper-language` flag** — pass through to the backend
  (`language="en"` for English content). Prevents Whisper from
  misidentifying accented English as another language and producing
  nonsense. Today we auto-detect; explicit is more reliable.

- **Bump default model from `base` to `small` or `medium`** — `base`
  is ~5% WER, `small` ~3.5%, `medium` ~2.8%. Bigger model = slower but
  meaningfully better on accented / noisy content. Make the default
  configurable per playlist via `scope.json`.

- **`mlx-whisper` on Apple Silicon** — Mac-native, fastest option on
  M-series chips. Add as a third branch in `_transcribe_with_whisper`,
  preferred when `platform.processor() == 'arm'` and the package is
  importable. Same model weights, same quality.

- **distil-whisper — DO NOT use.** Distilled smaller model; ~1% worse
  WER and noticeably worse on long-form content (per their paper).
  Bad fit for our use case. Documented here so it doesn't get picked
  up by a future contributor as "the obvious cheap option."

### ✓ Deictic screenshots (done)
**Status:** shipped. `scripts/extract_playlist.py` now writes
`transcript.timestamped.json` for both caption and Whisper paths.
`scripts/capture_screenshots.py` scans for trigger phrases, clusters
nearby hits, downloads the video, and grabs frames with ffmpeg.
`make screenshots PLAYLIST_NAME=...` is wired.

**Optional follow-ups** (only if false-positive rate proves annoying
in practice):
- `--smart` flag: small Haiku pass that re-ranks candidate timestamps
  by visual-relevance confidence. ~$0.003/video. Keep keyword scan as
  the default.
- Per-screenshot OCR — run Tesseract on each frame and append to
  `screenshots.json` so any on-screen text is searchable.

### 9. Speaker diarization (Phase 1)
**Why:** Interview / panel content currently muddies who said what.
**What:** Add `whisperx` or `pyannote` pass when `--diarize` is set.
Label as `Host`, `Guest 1`. Do **not** map voices to names.
**Compliance:** voiceprints are biometric data in some jurisdictions.
Generic labels only.

### 10. Chapter awareness in extractor
**Why:** Preprocessor already supports chapter splitting if a
`description.txt` exists with YouTube-style timestamps. The extractor
needs to actually save the description.
**What:** Update `scripts/extract_playlist.py` to write
`description.txt` per video using `yt-dlp --write-description`.

### 11. Diff mode + skill versioning
**Why:** Re-running on the same playlist months later should show what
changed in the creator's thinking.
**What:** `scripts/diff_synthesis.py` — compares two `synthesis.json`s,
emits `CHANGELOG.md`. `SKILL.md` carries a `version` header.

### 12. Eval harness (`score.json`)
**Why:** Without a score, no skill in a public marketplace can be trusted.
**What:** Hold-one-out: regenerate the skill from N-1 videos, ask Claude
to predict moves on the held-out video, score with a rubric. Output
`score.json`.

---

## Infra / repo hygiene (pre-public-launch)

### 13. CI workflow
**What:** `.github/workflows/ci.yml` — Python lint/syntax,
`requirements.txt` install on 3.10/3.11/3.12, markdown link check,
prompt-file UTF-8 + non-empty check. **No** pipeline execution in CI.

### 14. Issue templates
**What:** `.github/ISSUE_TEMPLATE/` — bug / feature / prompt-improvement.
Pre-fills "OS + Python version", "playlist used (CC/own only)", etc.
Steers reporters away from pasting third-party transcripts.

### 15. GitHub Private Vulnerability Reporting
**What:** Enable in repo Settings → Security; update `SECURITY.md` to
point there instead of a personal email.

### 16. Sanitized example output
**What:** Run the full pipeline on one Creative Commons playlist
(e.g. a Strange Loop conference talk playlist), commit the
`SKILL.md` + `citations.md` + `score.json` under `examples/`. Single
biggest credibility signal for new users.

---

## Open design questions

- **Phase 0 should it use Claude?** Could be cheaper UX: a brief Claude
  conversation that helps the user sharpen a vague `topical-report`
  question. Cost is tiny (one short call). Worth doing once Phase 0 CLI
  exists.
- **Diff cost.json across runs?** When users re-run after preprocessing
  tweaks, knowing the *delta* in cost is more useful than the absolute.
- **Should the marketplace ship in this repo, or a separate one?**
  Coupling: easier discoverability. Decoupling: cleaner license story
  (the tool is Apache-2.0; vetted skills may have varied source licenses).

---

## Won't do (out of scope, per PRD §4)

- Any hosted service / website / SaaS / paid tier.
- Real-time / streaming ingestion.
- Fine-tuning a model.
- Web UI or multi-user system.
- Anything targeting a specific creator without that creator's permission.
