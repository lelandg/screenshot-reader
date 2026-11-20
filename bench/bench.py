"""Measure what a screenshot costs the main model, with and without delegation.

For each image this runs two fresh headless Claude Code sessions with the same
prompt and the same main model:

  direct     - plugin disabled; the main model Reads the image itself.
  delegated  - plugin loaded; the main model hands the image to the Haiku
               screenshot-reader subagent and only sees its text report.

Each run checks the route it actually took (main-thread image Read vs. a
screenshot-reader dispatch) and fails if it does not match the mode, so an
installed copy of the plugin cannot silently turn a "direct" run into a
delegated one.

The headline number is the growth of the main model's context between its
first and last API call: what the session carries into every later turn.
Raw transcripts go to bench/results/ (gitignored: they contain screenshot
text).

Safety: runs are restricted to the Read, Glob, Agent and Skill tools and load
no MCP servers, so instructions hidden in a screenshot cannot reach a shell.

Usage:
  python bench/bench.py --model opus IMAGE [IMAGE ...]
  python bench/bench.py --model opus --batch IMAGE [IMAGE ...]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "bench" / "results"
PLUGIN_ID = "screenshot-reader@screenshot-reader"
IMAGE_EXT = re.compile(r"\.(png|jpe?g|gif|webp|bmp|tiff?|heic)$", re.I)

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


class RunFailed(RuntimeError):
    pass


def ctx(u: dict) -> int:
    return (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
            + u.get("cache_creation_input_tokens", 0))


def run(label: str, prompt: str, mode: str, model: str, stem: str) -> dict:
    cmd = [
        "claude", "-p", prompt,
        "--model", model,
        "--output-format", "stream-json", "--verbose",
        "--tools", "Read,Glob,Agent,Skill",
        "--allowedTools", "Read", "Glob", "Agent", "Skill",
        "--strict-mcp-config",
    ]
    if mode == "delegated":
        cmd += ["--plugin-dir", str(ROOT)]
    else:
        cmd += ["--settings", json.dumps({"enabledPlugins": {PLUGIN_ID: False}})]

    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    elapsed = time.time() - t0

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{stem}.jsonl").write_text(proc.stdout, encoding="utf-8")
    if proc.stderr.strip():
        (RESULTS / f"{stem}.stderr.txt").write_text(proc.stderr, encoding="utf-8")

    main_calls: list[dict] = []  # usage of each main-thread API call, in order
    seen_ids: set[str] = set()
    result: dict = {}
    direct_reads = 0
    dispatches = 0
    for line in proc.stdout.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "assistant" and ev.get("parent_tool_use_id") is None:
            msg = ev["message"]
            for block in msg.get("content", []):
                if block.get("type") != "tool_use":
                    continue
                inp = block.get("input", {})
                if block.get("name") == "Read" and IMAGE_EXT.search(inp.get("file_path", "")):
                    direct_reads += 1
                if block.get("name") == "Agent" and "screenshot-reader" in inp.get("subagent_type", ""):
                    dispatches += 1
            # one API response arrives as several events (one per content block)
            if msg.get("id") not in seen_ids:
                seen_ids.add(msg.get("id"))
                main_calls.append(msg.get("usage", {}))
        elif ev.get("type") == "result":
            result = ev  # keep the last one

    problems = []
    if proc.returncode != 0:
        problems.append(f"claude exited {proc.returncode}")
    if not result or result.get("is_error") or result.get("subtype") != "success":
        problems.append(f"no successful result event (subtype={result.get('subtype')})")
    if not main_calls:
        problems.append("no main-thread API calls")
    if mode == "direct" and (direct_reads == 0 or dispatches):
        problems.append(f"route mismatch: {direct_reads} direct reads, {dispatches} dispatches")
    if mode == "delegated" and (dispatches == 0 or direct_reads):
        problems.append(f"route mismatch: {direct_reads} direct reads, {dispatches} dispatches")
    if problems:
        raise RunFailed(f"{label} [{mode}]: " + "; ".join(problems)
                        + f" (see {RESULTS / stem}.*)")

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
        "image": label,
        "mode": mode,
        "seconds": round(elapsed, 1),
        "main_calls": len(main_calls),
        "main_ctx_first": ctx(main_calls[0]),
        "main_ctx_final": ctx(main_calls[-1]),
        "main_ctx_added": ctx(main_calls[-1]) - ctx(main_calls[0]),
        "direct_image_reads": direct_reads,
        "reader_dispatches": dispatches,
        "per_model": per_model,
        "total_cost_usd": round(result.get("total_cost_usd", 0.0), 5),
        "answer": result.get("result", ""),
    }


def unique_stem(path: Path, mode: str, tag: str) -> str:
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:8]
    return f"{path.stem}-{path.suffix.lstrip('.')}-{digest}.{mode}{tag}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+", type=Path)
    ap.add_argument("--model", default="opus")
    ap.add_argument("--modes", default="direct,delegated")
    ap.add_argument("--batch", action="store_true", help="one session, all images, narrow question")
    ap.add_argument("--tag", default="", help="suffix for result files")
    args = ap.parse_args()

    images = [i.resolve() for i in args.images]
    missing = [str(i) for i in images if not i.is_file()]
    if missing:
        print("missing image(s): " + ", ".join(missing), file=sys.stderr)
        return 2

    tag = args.tag or time.strftime(".%Y%m%d-%H%M%S")
    jobs = []
    if args.batch:
        prompt = BATCH_PROMPT.format(n=len(images), paths="\n".join(map(str, images)))
        digest = hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:8]
        jobs = [(f"batch of {len(images)}", prompt, f"batch-{digest}")]
    else:
        jobs = [(i.name, PROMPT.format(path=i), None, i) for i in images]

    rows, failures = [], 0
    for job in jobs:
        for mode in args.modes.split(","):
            if args.batch:
                label, prompt, base = job
                stem = f"{base}.{mode}{tag}"
            else:
                label, prompt, _, img = job
                stem = unique_stem(img, mode, tag)
            try:
                r = run(label, prompt, mode, args.model, stem)
            except RunFailed as e:
                failures += 1
                print(f"FAILED: {e}", file=sys.stderr, flush=True)
                continue
            rows.append(r)
            print(json.dumps({k: v for k, v in r.items() if k != "answer"}), flush=True)

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"summary{tag}.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
