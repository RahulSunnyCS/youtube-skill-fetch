# Compact JSON schema (Phase 2 output)

Phase 2 distills one transcript into a single JSON object with **short
keys** to minimise output tokens. Phase 3 reads this format directly.
Humans can pretty-print it via `scripts/expand_schema.py`.

## Top-level keys

| Short | Long                | Type        | Notes                                 |
| ----- | ------------------- | ----------- | ------------------------------------- |
| `t`   | `video_title`       | string      |                                       |
| `cc`  | `core_claims`       | list[claim] | What the creator asserts as true      |
| `h`   | `heuristics`        | list[rule]  | "if X then Y" rules they apply        |
| `rp`  | `reasoning_patterns`| list[pat]   | How they move problem→solution        |
| `emph`| `what_they_emphasize`| list[str]  | Recurring emphasis (free-form)        |
| `dis` | `what_they_dismiss` | list[str]   | What they reject or downplay          |
| `v`   | `vocabulary`        | list[term]  | Domain terms + their idiosyncratic use |

## Nested item keys

### claim (`cc[i]`)
| Short | Long                     | Type   |
| ----- | ------------------------ | ------ |
| `c`   | `claim`                  | string |
| `ev`  | `evidence_in_transcript` | string |
| `ts`  | `timestamp`              | "MM:SS"|

### heuristic (`h[i]`)
| Short | Long        | Type   |
| ----- | ----------- | ------ |
| `r`   | `rule`      | string |
| `why` | `rationale` | string |
| `ts`  | `timestamp` | "MM:SS"|

### reasoning_pattern (`rp[i]`)
| Short | Long       | Type   |
| ----- | ---------- | ------ |
| `p`   | `pattern`  | string |
| `ex`  | `example`  | string |
| `ts`  | `timestamp`| "MM:SS"|

### term (`v[i]`)
| Short | Long                     | Type   |
| ----- | ------------------------ | ------ |
| `term`| `term`                   | string |
| `m`   | `meaning_in_their_usage` | string |

## Why short keys?

A 40-video playlist with verbose keys emits ~30% more output tokens than
needed. Short keys reduce per-video output by ~25–35% and Phase 3 input
by a similar amount, with no quality impact — Claude reads and writes
both forms equally well.
