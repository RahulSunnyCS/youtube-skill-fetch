# PRD: youtube-skill-fetch

**Status:** Draft
**Owner:** TBD
**Last updated:** 2026-05-20

## 1. Summary

`youtube-skill-fetch` is a local-first pipeline that turns a YouTube creator's
playlist into a reusable Claude Skill (`SKILL.md`). It captures *how* a creator
thinks about their domain — their recurring patterns, heuristics, and moves —
so that Claude can apply that style on demand.

Mechanical work (downloading, captioning, OCR) runs locally and free via
`yt-dlp`, `ffmpeg`, `tesseract`, and optionally Whisper. Only the
distillation and synthesis steps use Claude.

## 2. Problem

Creators encode meaningful expertise in long-form video, but that knowledge is
trapped in audio + slides. Practitioners who want to *work in the creator's
style* — write like them, review like them, decide like them — have no
mechanical way to extract that style into a tool they can reuse.

Manually watching hours of video and taking notes is expensive and
inconsistent. Feeding raw transcripts to an LLM at query time is wasteful and
loses the cross-video patterns that make the creator's approach distinctive.

## 3. Goals

- **G1.** From a playlist URL, produce a `SKILL.md` that captures the
  creator's recurring patterns, usable as a Claude Skill.
- **G2.** Keep the bulk-data path (download, transcript, OCR) local, free,
  and deterministic. Reserve Claude for distillation/synthesis only.
- **G3.** Make each phase resumable and inspectable — every intermediate
  artifact is a flat file the human can eyeball.
- **G4.** Support both talking-head and screen-heavy content (slides, code,
  diagrams) via OCR.
- **G5.** Support multiple output modes: `Teacher`, `Reviewer`, `Advisor`.

## 4. Non-goals

- Real-time / streaming ingestion.
- A hosted service, web UI, or multi-user system.
- Fine-tuning a model. The output is a skill prompt, not weights.
- Scraping content the user is not entitled to use.
- Bit-for-bit reproduction of a creator's voice; the goal is method, not mimicry.

## 5. Users & use cases

- **Practitioner** wants to draft work in a respected creator's method
  (Teacher mode).
- **Learner** wants their own drafts critiqued the way the creator would
  critique them (Reviewer mode).
- **Operator** wants a "what would X do here?" oracle while making a
  decision (Advisor mode).

## 6. User journey

1. User picks a playlist URL and a content mode (`talking-head` or
   `screen-heavy`).
2. `make test1` extracts one video as a sanity check; user eyeballs the
   transcript.
3. `make extract` runs the full playlist; transcripts (and OCR text for
   screen-heavy) land under `output/<playlist>/video_NN_*/`.
4. For each video, user runs the Phase 2 prompt with Claude; saves JSON to
   `distilled/<playlist>/video_NN.json`.
5. User runs the Phase 3 synthesis prompt over the concatenated JSONs;
   reviews `synthesis.json` at the **human review gate**.
6. User picks a mode and runs the Phase 4 prompt to produce
   `distilled/<playlist>/SKILL.md`.
7. User installs `SKILL.md` as a Claude Skill and uses it.

## 7. Functional requirements

### Phase 1 — Extract (local)
- **F1.1** Accept a YouTube playlist URL (or single video URL).
- **F1.2** Honor `--mode {talking-head, screen-heavy}` and `--max-videos N`.
- **F1.3** Prefer existing captions; fall back to Whisper only when absent.
- **F1.4** For `screen-heavy`, sample frames and run OCR (`tesseract`),
  emitting an OCR sidecar.
- **F1.5** Produce one directory per video with `transcript.txt` and
  metadata; never overwrite existing artifacts.
- **F1.6** Be resumable: re-running skips videos already extracted.

### Phase 2 — Distill per video (Claude, map)
- **F2.1** Prompt `prompts/02_distill_video.md` takes one transcript and
  emits structured JSON of claims, heuristics, examples, and moves.
- **F2.2** One JSON file per video at `distilled/<playlist>/video_NN.json`.

### Phase 3 — Synthesize (Claude, reduce)
- **F3.1** Prompt `prompts/03_synthesize.md` takes the concatenated per-video
  JSONs and emits ranked recurring patterns to `synthesis.json`.
- **F3.2** Output ranks patterns by frequency and centrality, with
  references back to source videos.
- **F3.3** Phase 3 output is a **human review gate** before Phase 4.

### Phase 4 — Author SKILL.md (Claude)
- **F4.1** Prompt `prompts/04_author_skill.md` takes `synthesis.json` + a
  mode and emits a `SKILL.md` usable as a Claude Skill.
- **F4.2** Mode is one of `Teacher`, `Reviewer`, `Advisor`.
- **F4.3** `SKILL.md` includes a clear trigger description, the method
  distilled to actionable steps, and worked examples drawn from the source.

## 8. Non-functional requirements

- **NFR1.** Local-first: Phase 1 requires no API key and no paid services.
- **NFR2.** Cost: Claude usage is bounded by playlist size; per-video
  distillation is independent and parallelizable.
- **NFR3.** Transparency: every phase writes a flat-file artifact a human
  can read.
- **NFR4.** Portability: runs on macOS and Linux with the dependencies
  listed in `README.md` and `requirements.txt`.
- **NFR5.** Idempotence: re-running a phase on existing artifacts is safe.

## 9. Artifacts (data contract)

```
output/<playlist>/video_NN_<slug>/transcript.txt
output/<playlist>/video_NN_<slug>/ocr.txt          # screen-heavy only
output/<playlist>/video_NN_<slug>/metadata.json
distilled/<playlist>/video_NN.json                 # Phase 2
distilled/<playlist>/synthesis.json                # Phase 3
distilled/<playlist>/SKILL.md                      # Phase 4
```

## 10. Dependencies

- `yt-dlp`, `ffmpeg`, `tesseract` (system).
- Python deps in `requirements.txt`.
- `openai-whisper` only when captions are missing.
- Claude (for Phases 2–4); model choice left to the operator.

## 11. Risks & mitigations

- **YouTube ToS / rate limits.** Mitigation: respect `yt-dlp` defaults;
  document that users are responsible for their entitlements.
- **Caption quality varies.** Mitigation: Whisper fallback; human review gate
  before synthesis.
- **Hallucinated patterns in synthesis.** Mitigation: Phase 3 requires
  source-video citations; Phase 3 is a human review gate.
- **Creator style drift across playlist.** Mitigation: synthesis ranks by
  recurrence; one-off ideas are dropped or flagged.
- **OCR noise on screen-heavy content.** Mitigation: OCR is a sidecar, not a
  transcript replacement; Phase 2 prompt instructs Claude to treat OCR as
  supporting evidence.

## 12. Success metrics

- **M1.** Time from playlist URL → working `SKILL.md` on a 10-video
  playlist: under 1 hour of wall-clock and under 15 minutes of operator
  attention.
- **M2.** ≥ 80% of patterns in `synthesis.json` survive human review without
  edits.
- **M3.** A blind reader can identify the source creator from `SKILL.md`'s
  patterns and examples.
- **M4.** Phase 1 runs end-to-end on a fresh machine following only the
  `README.md` setup steps.

## 13. Open questions

- Should Phases 2–4 ship as scripts that call the Claude API directly, or
  remain copy-paste prompts? (Today: copy-paste.)
- How should we version `SKILL.md` outputs as the upstream playlist grows?
- Do we want a `Critic` mode distinct from `Reviewer` (rebuttal vs. critique)?
- Is there value in cross-creator synthesis (merging two creators' methods)?

## 14. Milestones

- **M0 — Today.** Phase 1 script + Phase 2–4 prompts, manual orchestration.
- **M1.** Convenience target to run Phase 2 over all transcripts via API.
- **M2.** Convenience target for Phase 3 + Phase 4 with mode flag.
- **M3.** Evaluation harness: given a held-out video, score whether the
  produced `SKILL.md` recovers its patterns.
