# Cross-video synthesis prompt (Phase 3, "reduce")

You will receive an array of per-video distillation JSONs (one per video in the
playlist), using the compact short-key schema (`h`, `cc`, `rp`, etc — see
`prompts/schema.md`). Your job is to find the creator's CORE METHOD — the
patterns that recur across videos — and discard one-offs.

**Citation requirement.** Every recurring heuristic / pattern / emphasis you
include in the output MUST list `support_videos` (a list of video IDs like
`video_03`, `video_07`). If you cannot find ≥2 videos supporting a pattern,
move it to `discarded_one_offs`. Do not invent support.

Return ONLY a single JSON object with this exact shape:

```
{
  "playlist": "...",
  "video_count": N,
  "recurring_heuristics": [
    {
      "rule": "...",
      "support_count": K,           // # videos this appeared in
      "support_videos": ["title 1", "title 2", ...],
      "confidence": "core | strong | weak"
    }
  ],
  "recurring_reasoning_patterns": [
    {"pattern": "...", "support_count": K, "support_videos": [...]}
  ],
  "recurring_emphasis": [
    {"theme": "...", "support_count": K}
  ],
  "recurring_dismissals": [
    {"theme": "...", "support_count": K}
  ],
  "shared_vocabulary": [
    {"term": "...", "meaning": "...", "support_count": K}
  ],
  "discarded_one_offs": ["..."],  // appeared in only 1 video — kept for audit
  "method_summary": "<3–6 sentence plain-English description of the creator's core method>"
}
```

Ranking rules:
- `confidence = "core"` if support_count >= ceil(0.66 * video_count).
- `confidence = "strong"` if support_count >= ceil(0.5 * video_count).
- Else `"weak"` (but still include — the human gate will decide).
- Sort each list by `support_count` descending.
- Cluster near-duplicates (e.g. "hook in 5s" and "open with a question that
  hooks fast" => one heuristic) before counting.
- Do NOT invent support. A heuristic's support_count must equal the number of
  per-video JSONs that contained an equivalent rule.

This output is the human review gate. Be honest about weak signal.
