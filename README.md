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
Whisper is optional and installed separately:

```
pip install openai-whisper
```

If you want the programmatic workflow (recommended — automates Phases
2–4 instead of copy-pasting prompts), also install:

```
pip install anthropic
export ANTHROPIC_API_KEY=sk-...
```

---

## How to run it

The simplest path (one video, sanity check):

```
make test1 PLAYLIST="<your-playlist-url>"
```

Look inside `output/<playlist>/video_01_*/transcript.txt` and make sure
the transcript looks correct.

Then the full playlist:

```
make extract PLAYLIST="<your-playlist-url>"
```

For Phases 2–4 (the Claude steps), you have **two options**:

**Option A — Programmatic (recommended).** Single command per phase:

```
python scripts/run_phase2.py --playlist <name>     # distill every video
# (Phase 3 + Phase 4 scripts coming next)
```

**Option B — Copy-paste.** Open `prompts/02_distill_video.md`, paste
the transcript and the prompt into Claude, save the JSON. Repeat for
each video. Then do the same for `prompts/03_synthesize.md` and
`prompts/04_author_skill.md`. Slower but needs no API key.

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
