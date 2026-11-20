# AGENTS.md: screenshot-reader

The canonical guide for AI coding agents in this repo. `CLAUDE.md` imports it.

## What this is

A Claude Code plugin. A subagent (`agents/screenshot-reader.md`) reads images
for the main model and returns exact text. It runs on Haiku by default; the
skill (`skills/read-screenshot/SKILL.md`) tells the main model to delegate and
to override the model to Sonnet for visual-judgment questions (rendering,
color, layout). A
`PreToolUse` hook (`hooks/guard-image-read.js`) blocks main-thread image
reads. `bench/bench.py` measures the token effect.

## Gates before a commit

```bash
node --test tests/guard-image-read.test.js
python -m py_compile bench/bench.py
claude plugin validate .
```

CI (`.github/workflows/ci.yml`) runs the first two on Ubuntu and Windows,
along with a manifest check and an LF check. `security.yml` runs gitleaks,
osv-scanner and zizmor.

## Rules

- **Every change reaches `main` through a PR**, so CodeRabbit reviews it.
  Non-functional edits (README, docs) may go straight to `main`.
- `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` carry the
  same `version`. CI fails if they differ. The version is bumped when a PR
  lands, never by hand in a PR.
- The hook must never block on its own errors (bad input means exit 0). A
  subagent is identified by `agent_id`, never `agent_type` alone.
- Never commit benchmark output (`bench/results/` is gitignored). It contains
  the text of real screenshots.
- Keep the reader's report terse. Measured: a verbose report costs the main
  model more context than the image it replaces.
