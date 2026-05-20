# Per-video summary prompt (Phase 2, summary intent)

You will receive one video's transcript from a creator's playlist.

Return ONLY a single JSON object with this compact shape:

```
{
  "vid": "<video id>",
  "title_guess": "<inferred from the transcript>",
  "tl_dr": "<one tight sentence>",
  "key_points": ["...", "...", "..."],
  "examples": ["...", "..."],
  "duration_estimate_min": <integer>
}
```

Rules:
- `tl_dr` is one sentence, ≤ 25 words.
- `key_points` are 3–6 bullets, each one sentence, capturing what a
  viewer would walk away with.
- `examples` are 0–3 short concrete things the creator showed or
  referenced. Skip generic platitudes.
- No filler ("Welcome back to the channel..."), no sponsor reads, no
  outro CTA. Focus on substance only.
- If the transcript is too short to summarise, return a minimal JSON
  with empty `key_points` and `examples`.
