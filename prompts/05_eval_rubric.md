# Hold-one-out evaluation prompt

You will receive:
1. A `SKILL.md` generated from N-1 videos of a playlist.
2. The transcript of the **held-out** Nth video.

Your job: predict what the held-out video contains using ONLY the
SKILL.md, then score the SKILL.md against what the held-out video
actually contains.

Return ONLY a single JSON object with this shape:

```
{
  "predicted_heuristics": ["..."],   // up to 8, what you expect from SKILL.md alone
  "observed_heuristics": ["..."],    // up to 8, what's actually in the held-out transcript
  "overlap_count": N,                 // strict count of predicted items that materialised
  "scores": {
    "method_recall": 0.0-1.0,         // does SKILL.md anticipate what the held-out video shows?
    "method_precision": 0.0-1.0,      // does SKILL.md avoid claiming methods the creator doesn't use?
    "vocabulary_match": 0.0-1.0,      // does the skill's vocabulary match the held-out video?
    "tone_match": 0.0-1.0,            // does the skill's framing match the creator's style?
    "overall": 0.0-1.0
  },
  "notes": "<2-4 sentences: what the SKILL.md got right, what it missed>"
}
```

Rules:
- Be honest. A `method_recall` of 0.4 with good notes is more useful
  than 0.95 with no specifics.
- `observed_heuristics` is what the held-out video actually demonstrates,
  in your reading of it. This is your ground truth.
- `overlap_count` is a strict count, not a fuzzy estimate.
- `overall` is your judgement, not a formula. Weight `method_recall`
  more than `tone_match`.
