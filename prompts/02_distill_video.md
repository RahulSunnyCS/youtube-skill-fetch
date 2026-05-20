# Per-video distillation prompt (Phase 2, "map")

You will receive one video's transcript from a creator's playlist. Your job is to
extract HOW the creator thinks about their domain — not just what they said in
this video.

Return ONLY a single JSON object with this exact shape (no prose, no markdown
fence):

```
{
  "video_title": "...",
  "core_claims": [
    {"claim": "...", "evidence_in_transcript": "<short quote or paraphrase>"}
  ],
  "heuristics": [
    {"rule": "if X then Y / always Z / never Q", "rationale": "..."}
  ],
  "reasoning_patterns": [
    {"pattern": "<how they move from problem -> solution>", "example": "..."}
  ],
  "what_they_emphasize": ["..."],
  "what_they_dismiss": ["..."],
  "vocabulary": [
    {"term": "...", "meaning_in_their_usage": "..."}
  ]
}
```

Rules:
- Extract the IMPLICIT method, not surface facts. "Hook the viewer in 5s" is a
  heuristic; "this video got 2M views" is not.
- Prefer concrete, transferable rules over abstract platitudes.
- 3–8 items per list is the sweet spot. If a category truly has nothing, return
  an empty list.
- `evidence_in_transcript` must be grounded in the transcript — short quote or
  tight paraphrase. No invention.
- If the transcript is too short or off-topic, return the JSON with empty lists
  rather than hallucinating.
