# AGENTS.md: screenshot-reader

The canonical guide for AI coding agents in this repo. `CLAUDE.md` imports it.

## What this is

A Claude Code plugin. A subagent (`agents/screenshot-reader.md`) reads images
for the main model and returns exact text. It runs on Haiku by default; the
skill (`skills/read-screenshot/SKILL.md`) tells the main model to delegate and
to override the model to Sonnet for visual-judgment questions (rendering,
color, layout). A `PreToolUse` hook (`hooks/guard-image-read.js`) blocks main-thread image
reads. `bench/bench.py` measures the token effect.

## Gates before a commit

```bash
node --test tests/guard-image-read.test.js
python -m py_compile bench/bench.py
claude plugin validate .
```

CI (`.github/workflows/ci.yml`) runs the first two on Ubuntu and Windows,
along with a manifest check and an LF check. `security.yml` and
`githooks.yml` come from
[secure-repo-template](https://github.com/Chameleon-Labs-LLC/secure-repo-template)
(adopted at `180c76a`). They run gitleaks, osv-scanner, zizmor, npm audit
(which skips, since there is no lockfile), the git-hook tests and shellcheck.

## Security rules

(From secure-repo-template. Keep them.)

- How the setup works, and why: `docs/security-setup.md`. Read it before changing `Scripts/githooks/`, `.github/`, `.npmrc`, `.coderabbit.yaml` or `.greptile/config.json`.
- Repository settings, when a PR may merge, and how to handle each kind of finding: `docs/agent-guide.md`.
- Never commit secrets. Keep them in a gitignored `.env` file and commit an `.env.example` with placeholders.
- Never use `git commit --no-verify`. Never set `GITLEAKS_DEGRADED_OK=1` without telling the human why (it passes one degraded scan, never a finding).
- Never add a suppression (`.gitleaksignore` entry, `gitleaks:allow` comment, osv-scanner ignore, `.snyk` ignore) to make a check pass. Report the finding instead.
- Never use the `pull_request_target` trigger. Pin every action to a full commit SHA.
- When a vulnerability with a fixed version is reported, apply the lowest version that fixes it, even if that version is newer than the 7-day package-age floor.
- Git-hook changes: `sh Scripts/githooks/test-pre-commit.sh`, then `shellcheck -s sh -x --severity=warning` on the changed scripts. The hooks must stay POSIX `sh`.
- **Solo maintainer:** the default-branch ruleset (created right after the template-adoption PR, lelandg/screenshot-reader#3) requires a PR, green checks, and code-owner review for the paths in `.github/CODEOWNERS`. Before the ruleset exists, nothing enforces owner review. An agent never uses an admin bypass (`docs/agent-guide.md` section 8). A PR that touches a code-owned path therefore waits for the owner, who merges it himself through his admin bypass; tell him so in the PR. Every other PR merges on the gates. Because the owner's bypass skips the checks as gates, the local fail-closed gitleaks hook is what stops a secret before it is pushed, and every machine that commits here must have it installed.
- AI reviewers: CodeRabbit (free on this public repo) and Greptile (`effort: base`). Wait for them as `docs/agent-guide.md` section 8 says: CodeRabbit gates, while Greptile does not. If Greptile hasn't reported after 15 minutes, or is out of credits, say so in the PR and carry on.

## Rules

- **Every change reaches `main` through a PR**, so CodeRabbit reviews it,
  docs included: the ruleset blocks direct pushes, and agents don't bypass it.
- `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` carry the
  same `version`. CI fails if they differ. The version is bumped when a PR
  lands, never by hand in a PR.
- The hook must never block on its own errors (bad input means exit 0). A
  subagent is identified by `agent_id`, never `agent_type` alone.
- Never commit benchmark output (`bench/results/` is gitignored). It contains
  the text of real screenshots.
- Keep the reader's report terse. Measured: a verbose report costs the main
  model more context than the image it replaces.
