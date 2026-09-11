# Architecture

Smart File Organizer separates recommendation from execution. A scan is read-only, a plan is an immutable JSON artifact, and execution requires a separate explicit command.

```text
Filesystem
    │ read-only
    ▼
Scanner ──► File records + SHA-256 fingerprints
    │
    ▼
Rule engine ──► destination + rule + reason + confidence
    │
    ▼
Planner ──► conflict-safe immutable plan + HTML preview
    │ explicit --yes
    ▼
Preflight ──► scope, source integrity, duplicate destination checks
    │
    ▼
Executor ──► verified copy + fsync + hash check + source removal
    │
    ├──► SQLite transaction journal
    └──► reverse-ordered undo
```

## Modules

| Module | Responsibility | Filesystem access |
| --- | --- | --- |
| `scanner` | Discovers regular files and records cryptographic fingerprints | Read-only |
| `rules` | Applies deterministic built-in and custom TOML rules | None, except configuration read |
| `planner` | Resolves destinations and conflicts, then creates a stable plan ID | Read-only |
| `reports` | Produces a standalone escaped HTML preview | Writes only the requested report |
| `executor` | Preflights and applies explicitly approved moves | Controlled writes inside the root |
| `journal` | Persists operations and transaction state | `.sfo/journal.sqlite3` inside the root |

## Plan identity

The plan identifier is derived from the selected root plus each source, destination, content hash, and planned status. Re-scanning unchanged content and rules therefore gives the same identifier. Creation time is recorded separately and does not affect identity.

## Move protocol

Each file is copied to a destination opened in exclusive-creation mode. The destination is flushed to durable storage, metadata is copied, and SHA-256 is verified before the source is removed. Existing destinations are never opened for writing. A failed multi-file transaction reverses completed moves in reverse order.

## Portability

The runtime uses only the Python 3.11+ standard library. Paths stored in plans are POSIX-style relative paths, then validated and converted for the host operating system. CI exercises Linux, macOS, and Windows.
