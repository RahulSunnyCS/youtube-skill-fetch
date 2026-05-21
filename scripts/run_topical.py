"""
Topical report orchestrator (intent=topical-report).

Phase 1.5 → 2 → 4 collapsed for this intent:
  - Phase 2: targeted per-video extraction using prompts/02_topical_extract.md
  - Phase 4: cluster + write report using prompts/04_topical_report.md

Outputs:
  distilled/<playlist>/topical/video_NN.json
  distilled/<playlist>/report.md
  distilled/<playlist>/report.pdf  (best-effort via pandoc; skipped if missing)
  distilled/<playlist>/citations.md (sidecar referencing video timestamps)

Usage:
    python scripts/run_topical.py --playlist <name> [--question "..."] [--concurrency 4]
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import scope as scope_module
from accounting import CostAccumulator
from claude_client import ClaudeClient


PROMPT_EXTRACT = Path(__file__).resolve().parent.parent / "prompts" / "02_topical_extract.md"
PROMPT_REPORT  = Path(__file__).resolve().parent.parent / "prompts" / "04_topical_report.md"


def _find_inputs(playlist_dir: Path) -> list[tuple[str, Path]]:
    pairs = []
    for vd in sorted(playlist_dir.glob("video_*")):
        if not vd.is_dir():
            continue
        vid = "_".join(vd.name.split("_")[:2])
        clean = vd / "transcript.clean.txt"
        raw = vd / "transcript.txt"
        chosen = clean if clean.exists() else raw if raw.exists() else None
        if chosen:
            pairs.append((vid, chosen))
    return pairs


def _extract_one(
    client: ClaudeClient,
    system: str,
    user_prefix: str,
    vid: str,
    transcript: Path,
    out_dir: Path,
    accumulator: CostAccumulator,
    lock: threading.Lock,
) -> tuple[str, bool, str]:
    out_path = out_dir / f"{vid}.json"
    if out_path.exists():
        return (vid, True, "skipped (exists)")
    transcript_text = transcript.read_text()
    result = client.complete(
        system=system,
        user=f"{user_prefix}\n\nVideo ID: {vid}\n\nTranscript:\n\n{transcript_text}",
        cache_system=True,
    )
    with lock:
        accumulator.record(phase="phase2_topical", result=result)
    text = result.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        data = json.loads(text)
        out_path.write_text(json.dumps(data, ensure_ascii=False))
        n = len(data.get("stmts", []))
        return (vid, True, f"ok ({n} statements)")
    except json.JSONDecodeError:
        out_path.with_suffix(".raw.txt").write_text(result.text)
        return (vid, False, "non-JSON; saved .raw.txt")


def _render_pdf(md_path: Path, pdf_path: Path) -> bool:
    if not shutil.which("pandoc"):
        return False
    res = subprocess.run(
        ["pandoc", str(md_path), "-o", str(pdf_path)],
        capture_output=True, text=True,
    )
    return res.returncode == 0 and pdf_path.exists()


def _render_citations(extractions: list[dict], dest: Path) -> None:
    by_facet: dict = {}
    for ex in extractions:
        vid = ex.get("vid", "?")
        for s in ex.get("stmts", []):
            facet = s.get("facet") or "uncategorized"
            by_facet.setdefault(facet, []).append({
                "video": vid,
                "ts": s.get("ts", "??:??"),
                "stance": s.get("stance", "asserts"),
                "quote": s.get("q", ""),
                "statement": s.get("s", ""),
            })
    lines = ["# Topical report — citations\n"]
    for facet in sorted(by_facet):
        lines.append(f"\n## {facet}\n")
        for c in by_facet[facet]:
            lines.append(f"- _[{c['stance']}]_ `{c['video']} @ {c['ts']}` — {c['statement']}")
            if c["quote"]:
                lines.append(f"  > {c['quote']}")
            lines.append("")
    dest.write_text("\n".join(lines))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--playlist", required=True)
    p.add_argument("--output-root", default="output")
    p.add_argument("--distilled-root", default="distilled")
    p.add_argument("--question", help="Override scope.json question")
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--model-extract", help="Override phase2 model")
    p.add_argument("--model-report", help="Override phase4 model")
    args = p.parse_args()

    distilled_root = Path(args.distilled_root)
    scope = scope_module.load(distilled_root, args.playlist)
    question = args.question or scope.question
    if not question:
        sys.exit("No question. Set scope.question (via scope_init.py) or pass --question.")

    playlist_dir = Path(args.output_root) / args.playlist
    inputs = _find_inputs(playlist_dir)
    if not inputs:
        sys.exit(f"No transcripts under {playlist_dir}")

    distilled_dir = distilled_root / args.playlist
    topical_dir = distilled_dir / "topical"
    topical_dir.mkdir(parents=True, exist_ok=True)

    model_extract = args.model_extract or scope.model_for("phase2")
    model_report = args.model_report or scope.model_for("phase4")

    extract_system = PROMPT_EXTRACT.read_text()
    user_prefix = f"QUESTION: {question}"

    client_extract = ClaudeClient(model=model_extract)
    accumulator = CostAccumulator(playlist=args.playlist)
    lock = threading.Lock()

    print(f"Topical extract: model={model_extract}, {len(inputs)} videos")
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futs = []
        for vid, t in inputs:
            futs.append(pool.submit(
                _extract_one, client_extract, extract_system, user_prefix,
                vid, t, topical_dir, accumulator, lock,
            ))
        for f in concurrent.futures.as_completed(futs):
            name, ok, msg = f.result()
            marker = "✓" if ok else "✗"
            print(f"  {marker} {name}: {msg}")

    # Aggregate extractions and write the report
    extractions: list[dict] = []
    for jf in sorted(topical_dir.glob("video_*.json")):
        try:
            extractions.append(json.loads(jf.read_text()))
        except json.JSONDecodeError:
            continue
    if not extractions:
        sys.exit("No usable extractions; aborting before report.")

    report_system = PROMPT_REPORT.read_text()
    user_msg = (
        f"QUESTION: {question}\n\n"
        f"Extractions (one per video):\n{json.dumps(extractions, ensure_ascii=False)}"
    )
    client_report = ClaudeClient(model=model_report, max_tokens=4096)
    print(f"\nReport: model={model_report}")
    result = client_report.complete(system=report_system, user=user_msg, cache_system=True)
    accumulator.record(phase="phase4_topical", result=result)
    body = result.text.strip()
    if body.startswith("```"):
        body = body.split("\n", 1)[1].rsplit("```", 1)[0]

    md_path = distilled_dir / "report.md"
    md_path.write_text(body)
    print(f"  Wrote {md_path}")

    pdf_path = distilled_dir / "report.pdf"
    if _render_pdf(md_path, pdf_path):
        print(f"  Wrote {pdf_path}")
    else:
        print("  (skipped PDF — install pandoc to enable)")

    _render_citations(extractions, distilled_dir / "citations.md")
    print(f"  Wrote {distilled_dir / 'citations.md'}")

    accumulator.write(distilled_dir / "cost.json")
    print(f"\nDone. Estimated cost: ${accumulator.running_total():.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
