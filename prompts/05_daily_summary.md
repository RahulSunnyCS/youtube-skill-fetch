# Daily post-market analyst summary (Phase 8)

You will receive a JSON object distilled from one post-market analyst video
(schema from `prompts/02_distill_video.md`). Produce a tight markdown recap a
reader can scan in under 20 seconds.

Output rules:
- Markdown bullets only. No headings, no preamble, no closing remarks.
- Total under 200 words.
- 3–6 bullets, each one line where possible.
- Cover, in this order, only if the source supports it:
  1. **Market view** — overall stance for tomorrow (bullish / bearish / range).
  2. **Sectoral bias** — which sectors the analyst is leaning into or avoiding.
  3. **Key levels / specific calls** — index/stock levels, named tickers,
     trigger prices. Quote numbers exactly as the analyst stated them.
  4. **Risks flagged** — events, data prints, or technicals they're watching.
  5. **Conviction** — how strongly the analyst holds the view (hedged vs. firm).
  6. **Tomorrow's watchlist** — specific names or setups to monitor.

Hard rules:
- Do NOT invent levels, tickers, or claims that aren't in the JSON.
- If a category has nothing in the source, skip it — don't pad.
- Bold each bullet's lead label (e.g. `- **Market view:** ...`).
