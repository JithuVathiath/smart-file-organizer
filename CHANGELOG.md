# Changelog

All notable changes follow semantic versioning.

## 1.0.1 — 2026-09-11

- Hardened cross-platform validation for POSIX-rooted, Windows drive, UNC, and
  backslash-based paths after the Windows CI matrix exposed a platform semantic difference.
- Updated GitHub Actions to current Node.js 24-based action runtimes.

## 1.0.0 — 2026-09-11

- Added read-only scanning with project, hidden-file, and symbolic-link protection.
- Added deterministic built-in and configurable TOML rules with explanations.
- Added immutable plans, conflict policies, stale-plan detection, and HTML previews.
- Added transaction-safe apply, SQLite history, rollback, and one-command undo.
- Added a dependency-free CLI, synthetic demo, benchmark, cross-platform CI, and safety documentation.
