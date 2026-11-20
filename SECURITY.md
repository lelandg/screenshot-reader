# Security policy

## Reporting a vulnerability

Please report security problems privately, not in a public issue.

Use the **Report a vulnerability** button on this repository's **Security** tab. It opens a private advisory that only the maintainers can see. We aim to reply within a few working days, and we'll keep you posted while we fix it.

Please include what you found, how to reproduce it, and what an attacker could do with it. If you'd like credit in the advisory, say so.

## Supported versions

Only the latest release is supported. Fixes are not backported.

## What we already do

This repository scans for secrets before every commit and in CI, scans dependencies and GitHub Actions for known vulnerabilities on every change and weekly, and keeps dependencies current with Dependabot. The setup is described in [docs/security-setup.md](docs/security-setup.md).

