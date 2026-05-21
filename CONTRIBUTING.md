# Contributing

Thanks for your interest in `youtube-skill-fetch`. This project turns a
YouTube creator's playlist into a reusable Claude Skill. Contributions of
all sizes are welcome — code, prompt improvements, docs, examples.

## Ground rules

- **Be respectful.** See `CODE_OF_CONDUCT.md`.
- **Personal / authorized use only.** Do not submit issues, PRs, or
  examples containing transcripts, OCR, frames, or `SKILL.md` derived
  from third-party content you do not have rights to use. See the
  Compliance section of `docs/PRD.md`.
- **No secrets.** Never commit API keys, tokens, or `.env` files. The
  `.gitignore` covers the obvious cases — check before you push.

## What's most welcome

1. **Prompt improvements.** Phases 2–4 are prompt-driven. If you have a
   better distillation, synthesis, or skill-authoring prompt, open a PR
   against the relevant file in `prompts/` with a short before/after
   comparison on a CC-licensed or own-content playlist.
2. **New intents.** Phase 0 supports `method-distillation`, `style-clone`,
   `summary`, `stats`, `quote-mining`. New intents are welcome — propose
   them in an issue first so we can agree on the data contract.
3. **Language support.** Whisper model selection, OCR language packs,
   non-English caption handling — all useful.
4. **Resumability + idempotence fixes.** Phase 1 should never re-do work
   it has already done. Bug reports here are high-priority.
5. **Examples.** A sanitized, fully-licensed `SKILL.md` example helps
   new users understand the output shape.

## What we won't merge

- Scrapers, downloaders, or features that target specific creators
  without their permission.
- Features that bypass YouTube's auth, rate limits, or paywalls.
- Hosted / SaaS components in the core repo — keep it strictly
  local-execution. A hosted variant belongs in a separate project.
- Anything that ships third-party copyrighted material as test data.

## Dev setup

```bash
brew install yt-dlp ffmpeg tesseract     # or apt-equivalent on Linux
pip install -r requirements.txt
# optional, only when captions are missing:
# pip install openai-whisper
```

Sanity check on a single video you own or that is CC-licensed:

```bash
make test1 PLAYLIST="<your-playlist-url>"
```

## Pull request checklist

Before opening a PR:

- [ ] The change has a clear, single purpose.
- [ ] No third-party content committed (transcripts, audio, frames,
      derived `SKILL.md`).
- [ ] No API keys or secrets in the diff.
- [ ] If you changed a prompt, you tested it on at least one playlist
      and included a short note about what improved.
- [ ] If you changed Phase 1 behavior, you verified resumability —
      re-running the command does not redo work or overwrite artifacts.
- [ ] Docs updated (`README.md`, `docs/PRD.md`) if behavior or
      artifacts changed.

## Filing issues

Use the issue templates in `.github/ISSUE_TEMPLATE/` when present.
Otherwise:

- **Bug:** what you ran, what you expected, what happened, OS + Python
  version, redact any third-party content.
- **Feature:** the problem you're trying to solve, your proposed
  approach, and whether you want to implement it yourself.
- **Prompt improvement:** before/after on a specific playlist
  (own/CC-licensed only), with the diff or rewritten prompt.

## Licensing

By submitting a contribution you agree it is licensed under the project's
Apache-2.0 license (see `LICENSE`). You retain copyright on your
contribution.
