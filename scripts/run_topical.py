"""
Topical report orchestrator (intent=topical-report).

Phase 1.5 → 2 → 4 collapsed for this intent:
  - Per-video extraction using prompts/02_topical_extract.md
  - Cluster + write report using prompts/04_topical_report.md

Default mode (`claude_code`): emits a single brief at
tasks/<playlist>/topical/BRIEF.md.

API mode (`api`): direct calls to the Anthropic API.

Outputs:
  distilled/<playlist>/topical/video_NN.json
  distilled/<playlist>/report.md
  distilled/<playlist>/report.pdf  (best-effort via pandoc)
  distilled/<playlist>/citations.md
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import shutil
import subprocess
import sys
from pathlib import Path

import scope as scope_module
import task_emitter


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
    client,
    system: str,
    user_prefix: str,
    vid: str,
    transcript: Path,
    out_dir: Path,
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


def _run_api_mode(args, scope, inputs, question, distilled_dir, topical_dir,
                  extract_system, report_system) -> int:
    from claude_client import ClaudeClient

    model_extract = args.model_extract or scope.model_for("phase2")
    model_report = args.model_report or scope.model_for("phase4")
    user_prefix = f"QUESTION: {question}"
    client_extract = ClaudeClient(model=model_extract)

    print(f"Topical extract (api): model={model_extract}, {len(inputs)} videos")
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futs = []
        for vid, t in inputs:
            futs.append(pool.submit(
                _extract_one, client_extract, extract_system, user_prefix,
                vid, t, topical_dir,
            ))
        for f in concurrent.futures.as_completed(futs):
            name, ok, msg = f.result()
            marker = "✓" if ok else "✗"
            print(f"  {marker} {name}: {msg}")

    extractions: list[dict] = []
    for jf in sorted(topical_dir.glob("video_*.json")):
        try:
            extractions.append(json.loads(jf.read_text()))
        except json.JSONDecodeError:
            continue
    if not extractions:
        sys.exit("No usable extractions; aborting before report.")

    user_msg = (
        f"QUESTION: {question}\n\n"
        f"Extractions (one per video):\n{json.dumps(extractions, ensure_ascii=False)}"
    )
    client_report = ClaudeClient(model=model_report, max_tokens=4096)
    print(f"\nReport (api): model={model_report}")
    result = client_report.complete(system=report_system, user=user_msg, cache_system=True)
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
    print("\nDone.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--playlist", required=True)
    p.add_argument("--output-root", default="output")
    p.add_argument("--distilled-root", default="distilled")
    p.add_argument("--question", help="Override scope.json question")
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--model-extract", help="(api mode) Override phase2 model")
    p.add_argument("--model-report", help="(api mode) Override phase4 model")
    p.add_argument("--mode", choices=sorted(scope_module.VALID_MODES),
                   help="Override scope.json mode (claude_code/api/manual)")
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

    extract_system = PROMPT_EXTRACT.read_text()
    report_system = PROMPT_REPORT.read_text()
    mode = args.mode or scope.mode

    if mode == "claude_code":
        pending = [(vid, t) for vid, t in inputs
                   if not (topical_dir / f"{vid}.json").exists()]
        report_path = distilled_dir / "report.md"
        brief = task_emitter.write_topical_brief(
            playlist=args.playlist,
            inputs=pending or inputs,
            topical_dir=topical_dir,
            report_path=report_path,
            question=question,
            extract_prompt=extract_system,
            report_prompt=report_system,
        )
        print(f"Topical (claude_code): {len(pending)} videos to extract, then 1 report.")
        task_emitter.announce(brief)
        return 0

    if mode == "manual":
        sys.exit("mode=manual is not implemented yet for topical. Use "
                 "mode=claude_code (default) or mode=api.")

    return _run_api_mode(args, scope, inputs, question, distilled_dir, topical_dir,
                         extract_system, report_system)


if __name__ == "__main__":
    sys.exit(main())
