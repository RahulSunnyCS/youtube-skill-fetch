# Playlist summary rollup (Phase 3, summary intent)

You will receive an array of per-video summary JSONs (each with `tl_dr`,
`key_points`, `examples`). Write a single Markdown document that:

1. Opens with a 3-sentence playlist-level overview.
2. Lists the top 5–10 recurring themes (one bullet each, with the
   approximate share of videos that touched it).
3. Lists "interesting one-offs" — distinctive points that came up in
   only 1–2 videos but feel worth highlighting.
4. Closes with a per-video index: one line each, `video_NN — <tl_dr>`.

Rules:
- Do NOT include `[video_NN @ MM:SS]` citation markers. Citations live
  in a separate sidecar.
- Be honest about coverage. If the playlist is incoherent (themes don't
  recur), say so.
- Total length: 300–700 words.
