# youtube-skill-fetch

**Turn a YouTube creator's playlist into something you can re-use.**

You give it a playlist. It watches the videos for you (locally, on your own
computer), then asks Claude to figure out the patterns — and gives you back
one of:

- a **Skill** Claude can load to think the way that creator does, or
- a **report (PDF)** answering a specific question like *"what does this
  person think about commodities?"* or *"how is this person learning AI?"*, or
- a **summary**, **word/topic stats**, or **a list of quotes** on a theme.

You decide which one you want. The downloads, transcripts, and OCR run on
your machine for free. Only the *thinking* steps use Claude.

---

## Is this for me?

You might find this useful if:

- You follow a YouTube creator and wish you could **ask Claude questions
  in their style** without manually re-watching everything.
- You want a **PDF report** of one creator's views on a specific topic,
  with citations back to the exact video and timestamp.
- You're a researcher or learner and you want to **stop re-watching the
  same recurring ideas** spread across 30 videos.
- You make videos yourself and want a Skill that helps you **work in
  your own established style**.

You probably **don't** need this if:

- You only watch one or two videos casually. Just watch them.
- You want to download videos to keep or republish. This tool is **not**
  a content downloader — the raw transcripts stay on your machine and are
  not meant to be shared.

---

## ⚠️ Read this before you use it

This is a tool, not a service. **You** are responsible for what you point
it at. Some plain-English rules:

- **Only use it on content you have the right to use.** That means: your
  own videos, Creative Commons / openly-licensed content (lots of
  conference talks fall here), or content the creator has explicitly
  permitted you to use.
- **Don't share what comes out.** Transcripts and downloaded audio stay
  on your computer. The repo's `.gitignore` already keeps them out of
  Git, but don't email them around or upload them either.
- **Credit the creator.** If you do produce a Skill or report, name the
  creator and link the playlist.
- **This is not for commercial repackaging.** Don't sell what this
  produces. The project is open source, free, and meant for personal /
  research use only.
- **No warranty.** It's free software under the Apache-2.0 license.
  We accept no liability if you misuse it.

If you're a creator and you want your content out of someone's local
copy of this tool, contact that person directly — the project itself
doesn't host any content, so there's nothing for us to take down.

Full compliance notes are in [`docs/PRD.md`](docs/PRD.md) §12.

---

## How it works (for non-technical readers)

Imagine doing this by hand:

1. **Download captions** for every video in the playlist (or transcribe
   them if captions aren't there). This is the boring mechanical part —
   it runs locally and is free.
2. **For each video, take notes** on the key ideas. We ask Claude to do
   this, producing one JSON file per video.
3. **Look across all the notes** and pull out the patterns that come up
   again and again. Claude does this once, across everything.
4. **Write up the final output** — either a Skill, a topical report (PDF),
   a summary, or stats. You pick the shape upfront.

Every step writes a file you can open in a text editor and read. Nothing
is hidden. If something looks wrong, you can stop and fix it.

---

## Outputs you can ask for

You tell the tool what you want before it starts. Options:

| Choose this           | When you want…                                                         | You get                          |
| --------------------- | ---------------------------------------------------------------------- | -------------------------------- |
| `method-distillation` | A Skill that thinks like the creator                                    | `SKILL.md`                       |
| `topical-report`      | A PDF answering "what does X think about Y?"                            | `report.md` + `report.pdf`       |
| `summary`             | A short summary of every video + the whole playlist                     | `summary.md`                     |
| `stats`               | How often a creator says a word, mentions a topic, etc. (no Claude cost) | `stats.json` / `stats.md`        |
| `quote-mining`        | A list of verbatim quotes matching themes you specify                   | `quotes.md`                      |
| `style-clone`         | A Skill that mimics the creator's *phrasing*, not just method           | `SKILL.md`                       |

Every output (except `stats`) also produces a separate `citations.md`
file mapping each claim back to **the exact video and timestamp** it
came from. The Skill or report stays clean and readable; if you want
to verify a specific point, open the citations file.

---

## What does it cost?

The downloading part is **free** — it just uses your computer.

Claude charges by tokens (think: words it reads and writes). Rough
estimates for a **10-hour playlist** (about 40 videos × 15 minutes):

| Model         | Approximate cost per playlist |
| ------------- | ----------------------------- |
| Sonnet 4.6    | ~$1.50–2.00                   |
| Opus 4.7      | ~$6–8                         |

`stats` mode is free (no Claude calls). Other modes are cheaper than
the table above because they do less work.

The tool always **shows you the estimate and asks you to confirm**
before it starts spending. No surprises.

Full cost model: [`docs/PRD.md`](docs/PRD.md) §8.

---

## How to set it up

**On Mac:**

```
brew install yt-dlp ffmpeg tesseract
pip install -r requirements.txt
```

**On Linux:**

```
sudo apt install yt-dlp ffmpeg tesseract-ocr
pip install -r requirements.txt
```

If a video has no captions, the tool will transcribe it with Whisper.
Whisper is optional and installed separately. We prefer **faster-whisper**
(same model weights, ~4× faster, half the memory):

```
pip install faster-whisper      # recommended
# or, as a fallback:
pip install openai-whisper
```

faster-whisper also enables voice-activity detection by default, which
dramatically reduces the "hallucination on silence" failure mode of
Whisper on long videos with pauses.

On Apple Silicon Macs, `mlx-whisper` is another fast option (not yet
wired in — see `todo.md`).

If you want the programmatic workflow (recommended — automates Phases
2–4 instead of copy-pasting prompts), also install:

```
pip install anthropic
export ANTHROPIC_API_KEY=sk-...
```

---

## How to run it

There are two ways to drive the Claude steps (Phases 2–4):

| Path                          | How                                                          | When to use                                                              |
| ----------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------ |
| **A. API key** (automated)    | `pip install anthropic && export ANTHROPIC_API_KEY=sk-...`   | You want the pipeline to run end-to-end with one command per phase.      |
| **B. Claude Code / Claude Pro** | Paste the prompts from `prompts/` into Claude Code or claude.ai | You already pay for a Pro/Max subscription and want zero per-token spend. |

Local steps (extract, preprocess, screenshots, stats, quote-mine) are
the same on both paths and never need an API key.

The examples below walk through the full flow on Path A. The section
**"Path B — running it without an API key"** further down shows the
exact equivalent using Claude Code or claude.ai.

### Example A — Build a Skill that thinks like a creator (API key)

**Scenario:** You follow a creator who runs a CC-licensed conference talk
playlist. You want a Claude Skill that gives advice in their style.

**Step 1: sanity-check one video.**

```
make test1 PLAYLIST="https://youtube.com/playlist?list=<id>" PLAYLIST_NAME=mycreator
```

This downloads one video's captions to
`output/mycreator/video_01_*/transcript.txt`. Open it and skim — make
sure it looks like real text from the talk.

**Step 2: extract the full playlist.**

```
make extract PLAYLIST="https://youtube.com/playlist?list=<id>" PLAYLIST_NAME=mycreator
```

When this finishes you'll have 40-ish `transcript.txt` files under
`output/mycreator/`.

**Step 3: clean the transcripts.** This strips filler ("um", "you
know"), sponsor reads, intros/outros, and repeats. It runs locally and
typically removes ~30–50% of the text *before* anything goes to Claude,
which saves you ~30–50% on the next step's cost.

```
make preprocess PLAYLIST_NAME=mycreator
```

Each video now has a `transcript.clean.txt` and a `preprocess.json`
showing what was cut. If the cuts look too aggressive, re-run with
`--no-sponsor-detect` or `--intro-sec 10`.

**Step 4: configure intent (write `scope.json`).** Until the interactive
scoper ships, drop this file at `distilled/mycreator/scope.json`:

```json
{
  "intent": "method-distillation",
  "language": "auto",
  "depth": "standard",
  "themes": [],
  "question": "",
  "target_audience": "personal",
  "models": {
    "phase2": "claude-haiku-4-5-20251001",
    "phase3": "claude-sonnet-4-6",
    "phase4": "claude-sonnet-4-6"
  }
}
```

**Step 5: distill each video (Phase 2).** This is the first step that
uses Claude. The defaults use Haiku to keep cost low.

```
python scripts/run_phase2.py --playlist mycreator
```

You'll see live progress and a running total:

```
Phase 2: model=claude-haiku-4-5-20251001, intent=method-distillation, 40 videos, concurrency=4
  ✓ video_01: ok (820 out tokens)  [running total: $0.0034]
  ✓ video_02: ok (760 out tokens)  [running total: $0.0067]
  ...
Phase 2 done. Estimated cost: $0.1240
Cost breakdown: distilled/mycreator/cost.json
```

Open `distilled/mycreator/video_01.json` to spot-check the extraction
(it uses short keys; `python scripts/expand_schema.py
distilled/mycreator/video_01.json` pretty-prints to verbose form).

**Step 6: synthesize across videos.**

```
make phase3 PLAYLIST_NAME=mycreator
```

Writes `distilled/mycreator/synthesis.json`. **Eyeball it** — this is
the human review gate. Confirm the recurring patterns look right
before paying for Phase 4.

**Step 7: author the Skill.**

```
make phase4 PLAYLIST_NAME=mycreator SKILL_MODE=Teacher
```

Writes a versioned, citation-free `SKILL.md`, updates `CHANGELOG.md`,
and regenerates `citations.md` (the sidecar that maps every claim back
to a video and timestamp). Re-running bumps the version and backs up
the previous SKILL.md.

You now have a Skill. Load it into Claude (via Claude Code, claude.ai
Projects, or the API) and it will answer in the creator's method.

**Optional Step 8: evaluate the Skill.**

```
make eval PLAYLIST_NAME=mycreator
```

Hold-one-out scoring: the last video is withheld and Claude is asked
to predict its content using only the SKILL.md. Result lands in
`distilled/mycreator/score.json`.

---

### Example B — Answer a question with a topical PDF report

**Scenario:** You want to know "what does this creator think about
compound interest?" — without watching all 40 videos.

**Steps 1–3** are the same as Example A (extract + preprocess).

**Step 4: set intent to `topical-report` with your question.**
`distilled/mycreator/scope.json`:

```json
{
  "intent": "topical-report",
  "language": "auto",
  "depth": "standard",
  "themes": [],
  "question": "What does the creator say about compound interest and long-term investing?",
  "target_audience": "personal",
  "models": {
    "phase2": "claude-haiku-4-5-20251001",
    "phase3": "claude-sonnet-4-6",
    "phase4": "claude-sonnet-4-6"
  }
}
```

**Step 5: run the topical pipeline.**

```
make topical PLAYLIST_NAME=mycreator
```

This calls the targeted extraction prompt on each cleaned transcript
(only statements relevant to the question), then writes
`distilled/mycreator/report.md` plus a `citations.md` sidecar. If
`pandoc` is installed, a `report.pdf` is rendered too.

---

### Example C — Just retrieve data: every quote about a topic ($0, no Claude)

**Scenario:** You don't need a Skill or a report — you just want every
place the creator says "passive income" or "index funds," with
timestamps.

**Steps 1–3** same as Example A.

**Step 4: run quote-mining locally.** No Claude needed; costs nothing.

```
make quote-mine PLAYLIST_NAME=mycreator THEMES="passive income,index funds,compound interest"
```

Output: `distilled/mycreator/quotes.md` (human-readable) and
`citations.json` (machine-readable). Each quote includes the video it
came from and whether the match was exact, stemmed, or via an alias.

If you want fuzzy/paraphrase matching (e.g., "money working for you"
should also match `passive income`), add a `distilled/mycreator/themes.aliases.json`:

```json
{
  "passive income": ["money working for you", "recurring revenue"],
  "compound interest": ["compounding", "interest on interest"]
}
```

---

### Example D — Grab screenshots when the creator says "look at this"

**Scenario:** The creator points at slides, charts, or code on screen.
You want a folder of frames at exactly those moments, so you can scan
them visually instead of re-watching everything.

**Step 1: extract.** Same as Example A; produces transcripts **and**
the timestamped sidecar (`transcript.timestamped.json`) automatically.

**Step 2: capture screenshots.**

```
make screenshots PLAYLIST_NAME=mycreator
```

This:
1. Reads the timestamped transcript and scans for trigger phrases:
   `look at this`, `see here`, `as you can see`, `notice`, `the chart
   shows`, etc.
2. Clusters nearby triggers (within 10s) so you don't get 5 frames of
   the same slide.
3. Downloads the video at 720p if it's not already local (yt-dlp).
4. Uses ffmpeg to grab the frame 1.5s *after* the trigger — creators
   usually say "look at this" right before the visual appears.
5. Writes frames to `output/mycreator/video_NN_*/screenshots/` with
   filenames like `001_t0234_look_at_this.jpg` so false positives are
   obvious and easy to `rm`.

Cost: **$0** (pure local). Per-video cap is 15 screenshots by default
(`--max-shots`); customize triggers with `--triggers-file mine.txt`.

**Preview without downloading the video:**

```
python scripts/capture_screenshots.py --playlist mycreator --skip-download
```

Writes a `screenshots.json` per video listing the candidate timestamps
and the speech context around each, so you can decide whether the
detection looks right before committing to downloads.

---

### Path B — Running it without an API key (Claude Code / Claude Pro)

If you pay for **Claude Pro/Max** or use **Claude Code**, you can run
every "thinking" step through the chat / agent interface — no
`ANTHROPIC_API_KEY`, no per-token spend on top of your subscription.
The trade-off: you process one video at a time instead of batch-parallel,
and the synthesis call can be large enough that you may want a Max plan
for a long playlist.

The local extraction/preprocess/screenshot/quote-mine commands are
**identical to Path A** — they don't call Claude, so an API key is
irrelevant to them. Run them first:

```
make extract     PLAYLIST="https://youtube.com/playlist?list=<id>" PLAYLIST_NAME=mycreator
make preprocess  PLAYLIST_NAME=mycreator
```

After preprocess you should have, for each video, a folder like:

```
output/mycreator/video_01_<title-slug>/
  transcript.txt              # raw
  transcript.timestamped.json # segment-level start/end
  transcript.clean.txt        # what you feed to Claude
  preprocess.json             # what was cut
```

From here, everything below replaces `make phase2 / phase3 / phase4`.
The total work is **three rounds with Claude**: distill each video,
synthesize across all of them, then write the Skill.

---

#### B-1. Distill each video → one JSON per video

**What this round does:** turns each `transcript.clean.txt` into a
small JSON file that captures the creator's *method* in that video
(heuristics, recurring claims, vocabulary). This is the "map" step.

**Inputs:** the prompt at `prompts/02_distill_video.md` + one cleaned
transcript.

**Output:** one file per video at
`distilled/mycreator/video_01.json` … `video_40.json`.

**Using Claude Code (easiest — it can read/write files for you):**

Open the project in Claude Code and paste this single instruction:

```
We're running Phase 2 by hand on a Pro subscription.

For each output/mycreator/video_*/transcript.clean.txt file:
  1. Read prompts/02_distill_video.md — that's the system prompt.
  2. Send it the transcript as the user message.
  3. The response will be a single JSON object (no prose, no fences).
  4. Save it verbatim to distilled/mycreator/video_NN.json, where NN
     is the same 2-digit number as the video folder.
  5. Skip any video_NN.json that already exists (so we can resume).

Process them one at a time and tell me when you're done.
```

Claude Code will iterate through the folders itself. You can watch
each JSON appear under `distilled/mycreator/`. **Spot-check one or
two** — open `video_01.json` and confirm it has `t`, `cc`, `h`, `rp`
keys with real content from the talk. If you want a human-readable
view, run:

```
python scripts/expand_schema.py distilled/mycreator/video_01.json
```

**Using claude.ai (Pro chat, no Claude Code):**

For each video, do this:

1. Open a new chat. Paste the **entire contents** of
   `prompts/02_distill_video.md` as your first message — it's only
   ~50 lines.
2. In the same message (or as a follow-up), paste the contents of
   `output/mycreator/video_01_*/transcript.clean.txt`. If the file is
   very long, attach it instead of pasting — claude.ai accepts `.txt`
   uploads.
3. Claude replies with a single JSON object that starts with `{"t":` …
   and ends with `}`. **Copy that whole object** (no prose, no
   markdown fences around it) and save it to a new file at
   `distilled/mycreator/video_01.json`.
4. Start a fresh chat for `video_02` and repeat. (Fresh chat per
   video keeps the context small and the output consistent.)

Tip: if Claude wraps the JSON in a ```json fence, strip the fence
lines before saving. The downstream scripts expect a raw JSON object.

---

#### B-2. Synthesize across videos → one `synthesis.json`

**What this round does:** reads *all* of the per-video JSONs at once
and pulls out the patterns that recur in ≥2 videos. One-offs get
moved to a `discarded_one_offs` list. This is the "reduce" step and
the **human review gate** — eyeball the output before paying for the
final write.

**Inputs:** `prompts/03_synthesize.md` + every
`distilled/mycreator/video_*.json` you produced in B-1.

**Output:** `distilled/mycreator/synthesis.json`.

**Using Claude Code:**

```
Now Phase 3. Read prompts/03_synthesize.md as the system prompt,
then send all distilled/mycreator/video_*.json files (concatenated
as a JSON array, in numeric order) as the user message. Save the
single JSON object you get back to distilled/mycreator/synthesis.json.
```

**Using claude.ai:**

1. New chat. Paste `prompts/03_synthesize.md` first.
2. Paste a JSON array of all the per-video JSONs. The easiest way:

   ```
   jq -s '.' distilled/mycreator/video_*.json > /tmp/all_videos.json
   ```

   Then attach `/tmp/all_videos.json` to the chat (or paste its
   contents if it fits).
3. Save Claude's JSON reply to `distilled/mycreator/synthesis.json`.

**Review gate:** open `synthesis.json` and read the
`recurring_heuristics` list. Each item has a `confidence` of `core`,
`strong`, or `weak`. If the `core` items don't sound like the creator,
something went wrong upstream — re-check a few `video_NN.json` files
before continuing.

---

#### B-3. Author the Skill → `SKILL.md`

**What this round does:** turns the synthesis into a reusable
`SKILL.md` you can load into Claude. Only `core` and `strong`
patterns become part of the active method; weak ones get parked in an
appendix.

**Inputs:** `prompts/04_author_skill.md` + `synthesis.json` + a mode
(`Teacher`, `Reviewer`, or `Advisor` — see "Skill modes" below).

**Output:** `distilled/mycreator/SKILL.md`.

**Using Claude Code:**

```
Phase 4. Read prompts/04_author_skill.md as the system prompt. Send
distilled/mycreator/synthesis.json plus the line "MODE: Teacher" as
the user message. Save the SKILL.md markdown you get back to
distilled/mycreator/SKILL.md. Leave the {{VERSION}} placeholder in
the frontmatter — we'll set it next.
```

**Using claude.ai:**

1. New chat. Paste `prompts/04_author_skill.md`.
2. Paste `synthesis.json` and add a line: `MODE: Teacher` (or
   `Reviewer` / `Advisor`).
3. Save the markdown reply to `distilled/mycreator/SKILL.md`.

**Then generate the citations sidecar** (this part is local, no
Claude needed):

```
make citations PLAYLIST_NAME=mycreator
```

This walks `synthesis.json` + the per-video JSONs and writes
`distilled/mycreator/citations.md`, mapping each claim in `SKILL.md`
back to the exact video and timestamp it came from.

---

#### Using the Skill you just built

You now have `distilled/mycreator/SKILL.md`. To use it:

- **In Claude Code:** copy it into `.claude/skills/<name>/SKILL.md`
  in any project; Claude Code will auto-load it. Ask Claude something
  in the creator's domain and it will apply the method.
- **In claude.ai (Pro):** create a Project, upload `SKILL.md` as a
  project file, and the chat will use it as standing instructions.
- **Via the API:** send `SKILL.md` as a system prompt.

---

#### Other intents on Path B

The same pattern works for the other outputs — just swap prompts:

| Intent           | Replace 02 prompt with         | Replace 03/04 with                |
| ---------------- | ------------------------------ | --------------------------------- |
| `topical-report` | `prompts/02_topical_extract.md` (one per video) | `prompts/04_topical_report.md` (run once on all extracts) |
| `summary`        | `prompts/02_summary.md` (one per video)         | `prompts/03_summary_rollup.md` (run once on all summaries) |
| `quote-mining`   | — (no Claude needed: `make quote-mine`)         | —                                 |
| `stats`          | — (no Claude needed: `make stats`)              | —                                 |

> **Note:** `make eval` (hold-one-out scoring) still needs an API key
> — it programmatically grades the Skill against a held-out video.
> Skip it on Path B, or grade by hand using
> `prompts/05_eval_rubric.md` (paste the rubric + your `SKILL.md` +
> a held-out transcript into a chat).

---

## Where things end up

After a full run you'll find:

```
output/mycreator/                     # raw transcripts (do not share)
  video_01_*/transcript.txt
  video_01_*/transcript.timestamped.json  # segment-level start/end for each line
  video_01_*/transcript.clean.txt     # preprocessor output
  video_01_*/preprocess.json          # what was removed and why
  video_01_*/screenshots/*.jpg        # frames at "look at this" moments (optional)
  video_01_*/screenshots.json         # manifest: frame -> ts + trigger + context

distilled/mycreator/                  # everything Claude touched
  scope.json                          # your intent + model choices
  video_01.json ... video_40.json     # Phase 2 output
  synthesis.json                      # Phase 3 output (review gate)
  SKILL.md                            # Phase 4 output (citation-free)
  citations.md                        # which video + timestamp backs each claim
  cost.json                           # exactly what you spent
```

---

## Skill modes (when you pick `method-distillation`)

- **Teacher** — the Skill applies the creator's method to make new things
  in their style.
- **Reviewer** — the Skill critiques *your* drafts the way that creator
  would.
- **Advisor** — the Skill answers "what would they recommend here?"

---

## Project documents

- [`docs/PRD.md`](docs/PRD.md) — product requirements: every phase, every
  output, cost model, compliance notes. Start here if you want the full picture.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — how to contribute.
- [`SECURITY.md`](SECURITY.md) — how to report a security issue privately.
- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) — community standards.
- [`LICENSE`](LICENSE) — Apache-2.0.

---

## License

Apache-2.0 — free, open source, no warranty. See [`LICENSE`](LICENSE).

The code and prompts in this repo are Apache-2.0 licensed. Anything you
**generate** by running the tool (a Skill, a report, etc.) is yours — but
your right to use it is limited by your rights in the source content.
