# SKILL.md authoring prompt (Phase 4)

You will receive:
1. The synthesis JSON from Phase 3 (recurring patterns, ranked).
2. A chosen MODE: one of `Teacher`, `Reviewer`, `Advisor`.

Author a `SKILL.md` that encodes the creator's recurring method as a reusable
Claude Skill. Use ONLY items with confidence `core` or `strong` from the
synthesis — weak signals go in a "Notes / weak signals" appendix, not in the
active method.

## Mode behavior

- **Teacher**: the skill APPLIES the creator's method to produce new artifacts
  in their style. Section headings: "When to use", "Method", "Step-by-step",
  "Checklist", "Examples".
- **Reviewer**: the skill CRITIQUES the user's drafts against the creator's
  method. Section headings: "When to use", "What to check", "Critique
  checklist", "How to phrase feedback".
- **Advisor**: the skill RECOMMENDS what the creator would do given a
  situation. Section headings: "When to use", "Decision heuristics",
  "Recommendation patterns", "Common asks".

## Required SKILL.md structure

```
---
name: <playlist-slug>-<mode-lowercase>
description: <one sentence: when Claude should invoke this skill>
---

# <Creator>'s <domain> — <Mode> skill

## When to use
- bulleted triggers

## Core method (recurring across N/M videos)
- numbered list of CORE heuristics with one-line rationale each

## <Mode-specific sections>
...

## Vocabulary
- term — meaning in the creator's usage

## Notes / weak signals (do not over-apply)
- weak-confidence items, flagged
```

Rules:
- Frontmatter `description` must be specific enough that Claude knows when to
  trigger this skill (NOT "helps with videos" — instead "Critique a YouTube
  science-video draft using Veritasium's hooking + payoff method").
- Keep the body tight. A skill that's a wall of text won't get used. Aim for
  <300 lines.
- Every heuristic in "Core method" must trace back to a `core` or `strong` item
  in the synthesis JSON. Do not invent.
