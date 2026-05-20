"""
Stats intent: local analyzer. Zero Claude calls.

Computes:
  - Word/phrase frequencies (top 200 + user-supplied terms)
  - Bigram/trigram frequencies (top 100)
  - Per-video word counts and duration (when timestamps available)
  - Vocabulary size
  - Optional: speaker time (when diarization adds speaker labels — future)

Outputs:
  distilled/<playlist>/stats.json
  distilled/<playlist>/stats.md

Usage:
    python scripts/run_stats.py --playlist <name> [--terms 'word1,phrase 2,...']
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import scope as scope_module


# Minimal English stopword set — enough to keep the top-words list meaningful
# without dragging in a dependency.
STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "in", "on", "at", "to", "for",
    "with", "by", "from", "as", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "can", "this", "that", "these",
    "those", "i", "you", "we", "they", "he", "she", "it", "him", "her", "us",
    "them", "my", "your", "our", "their", "his", "its", "me", "mine", "yours",
    "ours", "theirs", "hers", "if", "then", "so", "than", "into", "out",
    "up", "down", "over", "under", "again", "more", "most", "less", "least",
    "very", "just", "now", "here", "there", "when", "where", "why", "how",
    "all", "any", "some", "no", "not", "only", "own", "same", "such", "too",
    "what", "which", "who", "whom", "whose", "about", "above", "after",
    "before", "below", "between", "during", "while", "of", "off", "on", "off",
    "yes", "yeah", "okay", "ok", "going", "gonna", "really", "kind", "sort",
    "thing", "things", "way", "ways", "lot", "lots", "much", "many", "also",
    "even", "actually", "well", "right", "got", "get", "gets", "getting",
    "go", "goes", "went", "gone", "say", "says", "said", "saying", "see",
    "seen", "sees", "seeing", "know", "knew", "known", "knows", "think",
    "thought", "thinks", "thinking", "make", "made", "makes", "making",
    "like", "liked", "likes", "want", "wants", "wanted", "use", "used",
    "using", "uses", "look", "looks", "looked", "looking",
}


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[a-zA-Z][a-zA-Z'-]+", text)]


def _ngrams(toks: list[str], n: int) -> list[str]:
    return [" ".join(toks[i:i+n]) for i in range(len(toks) - n + 1)]


def _count_term_hits(text: str, term: str) -> int:
    if not term:
        return 0
    return len(re.findall(rf"\b{re.escape(term)}\b", text, flags=re.IGNORECASE))


def analyse_video(video_dir: Path, user_terms: list[str]) -> dict:
    clean = video_dir / "transcript.clean.txt"
    raw = video_dir / "transcript.txt"
    transcript_path = clean if clean.exists() else raw
    if not transcript_path.exists():
        return {"video": video_dir.name, "skipped": "no transcript"}
    text = transcript_path.read_text()

    toks = _tokens(text)
    content = [t for t in toks if t not in STOPWORDS and len(t) > 2]
    word_freq = Counter(content)
    bigrams = Counter(_ngrams(toks, 2))
    trigrams = Counter(_ngrams(toks, 3))

    # Duration from timestamped sidecar when available
    duration = None
    ts_path = video_dir / "transcript.timestamped.json"
    if ts_path.exists():
        try:
            payload = json.loads(ts_path.read_text())
            segments = payload.get("segments") or []
            if segments:
                duration = float(segments[-1].get("end", 0.0))
        except Exception:
            pass

    term_counts = {t: _count_term_hits(text, t) for t in user_terms}

    return {
        "video": video_dir.name,
        "word_count_raw": len(toks),
        "word_count_content": len(content),
        "vocab_size_content": len(set(content)),
        "duration_sec": duration,
        "top_words": word_freq.most_common(30),
        "top_bigrams": [(b, c) for b, c in bigrams.most_common(15) if c > 1],
        "top_trigrams": [(b, c) for b, c in trigrams.most_common(10) if c > 1],
        "user_term_counts": term_counts,
    }


def aggregate(per_video: list[dict], user_terms: list[str]) -> dict:
    global_word_freq: Counter = Counter()
    global_bigram_freq: Counter = Counter()
    global_trigram_freq: Counter = Counter()
    total_words = 0
    total_content_words = 0
    total_duration = 0.0
    user_term_total: dict[str, int] = {t: 0 for t in user_terms}

    for v in per_video:
        if v.get("skipped"):
            continue
        for word, count in v.get("top_words", []):
            global_word_freq[word] += count
        for bg, count in v.get("top_bigrams", []):
            global_bigram_freq[bg] += count
        for tg, count in v.get("top_trigrams", []):
            global_trigram_freq[tg] += count
        total_words += v.get("word_count_raw", 0)
        total_content_words += v.get("word_count_content", 0)
        if v.get("duration_sec"):
            total_duration += v["duration_sec"]
        for t, c in (v.get("user_term_counts") or {}).items():
            user_term_total[t] = user_term_total.get(t, 0) + c

    return {
        "videos_analysed": sum(1 for v in per_video if not v.get("skipped")),
        "videos_skipped": sum(1 for v in per_video if v.get("skipped")),
        "total_words_raw": total_words,
        "total_words_content": total_content_words,
        "total_duration_sec": round(total_duration, 1) if total_duration else None,
        "top_words": global_word_freq.most_common(50),
        "top_bigrams": global_bigram_freq.most_common(30),
        "top_trigrams": global_trigram_freq.most_common(15),
        "user_term_counts": user_term_total,
    }


def render_markdown(playlist: str, agg: dict, per_video: list[dict]) -> str:
    lines = [f"# Stats — {playlist}\n"]
    lines.append(f"- Videos analysed: **{agg['videos_analysed']}** "
                 f"(skipped: {agg['videos_skipped']})")
    lines.append(f"- Total words (raw): **{agg['total_words_raw']:,}**")
    lines.append(f"- Total words (content, after stopword strip): "
                 f"**{agg['total_words_content']:,}**")
    if agg.get("total_duration_sec"):
        h = agg["total_duration_sec"] / 3600
        lines.append(f"- Total duration: **{h:.1f} hr** "
                     f"({int(agg['total_duration_sec'])} sec)")
    lines.append("")

    if agg["user_term_counts"]:
        lines.append("## Your term counts\n")
        for term in sorted(agg["user_term_counts"]):
            lines.append(f"- `{term}` — **{agg['user_term_counts'][term]}** hits")
        lines.append("")

    lines.append("## Top words (cross-playlist)\n")
    for word, count in agg["top_words"][:30]:
        lines.append(f"- `{word}` — {count}")
    lines.append("")

    lines.append("## Top bigrams\n")
    for bg, count in agg["top_bigrams"][:20]:
        lines.append(f"- `{bg}` — {count}")
    lines.append("")

    lines.append("## Top trigrams\n")
    for tg, count in agg["top_trigrams"][:15]:
        lines.append(f"- `{tg}` — {count}")
    lines.append("")

    lines.append("## Per video\n")
    for v in per_video:
        if v.get("skipped"):
            lines.append(f"- {v['video']} — _skipped: {v['skipped']}_")
            continue
        d = v.get("duration_sec") or 0
        lines.append(f"- **{v['video']}** — "
                     f"{v['word_count_content']} content words, "
                     f"{v['vocab_size_content']} unique, "
                     f"{int(d/60)}m{int(d%60):02d}s")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--playlist", required=True)
    p.add_argument("--output-root", default="output")
    p.add_argument("--distilled-root", default="distilled")
    p.add_argument("--terms", default="",
                   help="Comma-separated terms to count (overrides scope.themes)")
    args = p.parse_args()

    distilled_root = Path(args.distilled_root)
    distilled_dir = distilled_root / args.playlist
    distilled_dir.mkdir(parents=True, exist_ok=True)

    if args.terms:
        user_terms = [t.strip() for t in args.terms.split(",") if t.strip()]
    else:
        try:
            scope = scope_module.load(distilled_root, args.playlist)
            user_terms = list(scope.themes)
        except Exception:
            user_terms = []

    playlist_dir = Path(args.output_root) / args.playlist
    video_dirs = sorted(d for d in playlist_dir.glob("video_*") if d.is_dir())
    if not video_dirs:
        sys.exit(f"No videos under {playlist_dir}")

    per_video = [analyse_video(d, user_terms) for d in video_dirs]
    agg = aggregate(per_video, user_terms)

    (distilled_dir / "stats.json").write_text(
        json.dumps({"playlist": args.playlist, "aggregate": agg, "per_video": per_video},
                   indent=2, ensure_ascii=False)
    )
    (distilled_dir / "stats.md").write_text(
        render_markdown(args.playlist, agg, per_video)
    )
    print(f"Stats done. {agg['videos_analysed']} videos. $0 spent.")
    print(f"  {distilled_dir / 'stats.json'}")
    print(f"  {distilled_dir / 'stats.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
