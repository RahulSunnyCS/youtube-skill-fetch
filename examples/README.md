# Examples

Vetted, sanitized example outputs from running the pipeline on
**Creative Commons** or **explicitly creator-authorized** playlists.

This directory is intentionally empty in the initial release. Examples
require:

1. A source playlist that is **CC-licensed or explicitly permitted**
   for this use.
2. A run through the full pipeline:
   `extract → preprocess → run_phase2 → run_phase3 → run_phase4`.
3. A score from `run_eval.py` above a baseline threshold (we use
   `overall ≥ 0.60` as the minimum bar for inclusion).
4. A `LICENSE` note documenting the source content's license.

## Layout per example

```
examples/<short-slug>/
  SOURCE.md          # link to source playlist, license, why it was chosen
  SKILL.md           # generated skill (citation-free)
  citations.md       # citations sidecar
  score.json         # eval result
```

## Contributing an example

Open a PR using the prompt-improvement issue template as a model. The
maintainers will sanity-check:

- License of the source playlist is clearly declared.
- `score.json` shows `overall ≥ 0.60`.
- `SKILL.md` does not contain verbatim copyrighted material — only
  distilled method.
- Attribution to the source creator is present in `SOURCE.md`.

PRs that include third-party content without a clear license or
permission trail will be rejected per `CONTRIBUTING.md`.

## What examples are NOT for

- Pasting transcripts (do not commit `output/`).
- Showcasing methods of specific creators who haven't authorized use.
- Marketing material.
