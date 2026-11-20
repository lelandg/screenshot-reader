"""Measure what a screenshot costs the main model, with and without delegation.

For each image this runs two fresh headless Claude Code sessions with the same
prompt and the same main model:

  direct     - plugin NOT loaded; the main model Reads the image itself.
  delegated  - plugin loaded; the main model hands the image to the Haiku
               screenshot-reader subagent and only sees its text report.

It parses the stream-json output and records, per model, every API call's
usage. The headline number is the main model's context size on its final
call: that is what the session carries into every later turn. Raw transcripts
go to bench/results/ (gitignored: they contain screenshot text).

Usage:
  python bench/bench.py --model opus IMAGE [IMAGE ...]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "bench" / "results"

BATCH_PROMPT = (
    "Here are {n} screenshots:\n{paths}\nWhich of them shows an error, a warning or a "
    "failing status? For each one that does, quote the message exactly and name the file. "
    "Ignore the rest."
)

PROMPT = (
    "Look at the screenshot at {path} and tell me: what application or page is "
    "shown, the exact text of any error or warning, and the most important text "
    "on screen verbatim. Then say in one sentence what a developer should check next."
)


def run(image: Path, mode: str, model: str, tag: str = "", prompt: str | None = None) -> dict:
    cmd = [
        "claude", "-p", prompt or PROMPT.format(path=image),
        "--model", model,
        "--output-format", "stream-json", "--verbose",
        "--allowedTools", "Read", "Glob", "Agent",
    ]
    if mode == "delegated":
        cmd += ["--plugin-dir", str(ROOT)]
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    elapsed = time.time() - t0

    stem = f"{image.stem}.{mode}{tag}"
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{stem}.jsonl").write_text(proc.stdout, encoding="utf-8")

    main_calls: list[dict] = []  # usage of each main-thread API call, in order
    seen_ids: set[str] = set()
    result: dict = {}
    for line in proc.stdout.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "assistant" and ev.get("parent_tool_use_id") is None:
            msg = ev["message"]
            # one API response can arrive as several events (one per content block)
            if msg.get("id") in seen_ids:
                continue
            seen_ids.add(msg.get("id"))
            u = msg.get("usage", {})
            main_calls.append(u)
        elif ev.get("type") == "result":
            result = ev

    def ctx(u: dict) -> int:
        return (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                + u.get("cache_creation_input_tokens", 0))

    per_model = {
        m: {
            "input_total": v.get("inputTokens", 0) + v.get("cacheReadInputTokens", 0)
            + v.get("cacheCreationInputTokens", 0),
            "output": v.get("outputTokens", 0),
            "cost_usd": round(v.get("costUSD", 0.0), 5),
        }
        for m, v in (result.get("modelUsage") or {}).items()
    }
    return {
        "image": image.name,
        "mode": mode,
        "seconds": round(elapsed, 1),
        "main_calls": len(main_calls),
        "main_ctx_first": ctx(main_calls[0]) if main_calls else None,
        "main_ctx_final": ctx(main_calls[-1]) if main_calls else None,
        "per_model": per_model,
        "total_cost_usd": round(result.get("total_cost_usd", 0.0), 5),
        "answer": result.get("result", ""),
        "exit": proc.returncode,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+", type=Path)
    ap.add_argument("--model", default="opus")
    ap.add_argument("--modes", default="direct,delegated")
    ap.add_argument("--batch", action="store_true", help="one session, all images, narrow question")
    ap.add_argument("--tag", default="", help="suffix for result files")
    args = ap.parse_args()

    rows = []
    if args.batch:
        prompt = BATCH_PROMPT.format(n=len(args.images),
                                     paths="\n".join(str(i.resolve()) for i in args.images))
        for mode in args.modes.split(","):
            r = run(Path("batch"), mode, args.model, args.tag, prompt)
            rows.append(r)
            print(json.dumps({k: v for k, v in r.items() if k != "answer"}), flush=True)
        (RESULTS / f"summary{args.tag}.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
        return 0
    for img in args.images:
        for mode in args.modes.split(","):
            r = run(img.resolve(), mode, args.model, args.tag)
            rows.append(r)
            print(json.dumps({k: v for k, v in r.items() if k != "answer"}), flush=True)

    (RESULTS / f"summary{args.tag}.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
