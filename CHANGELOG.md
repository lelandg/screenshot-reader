# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-11-20

- New `visual-inspector` agent (Sonnet) for questions about how a screen looks. Visual questions now reliably go to it instead of the Haiku text reader.

## [0.2.0] - 2026-11-20

- Visual questions about screenshots (rendering bugs, colors, layout) now go to a Sonnet reader. Text questions stay on Haiku.
- The reader no longer claims to read BMP, TIFF or HEIC files.
- The security scans now run on pushes to `main`.
