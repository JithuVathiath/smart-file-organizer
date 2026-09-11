# Safety and privacy model

## Invariants

1. **Explicit scope:** every source and destination must resolve beneath the selected root.
2. **Preview first:** scanning and planning never move or delete files.
3. **No silent overwrite:** destination files are created exclusively; an existing path stops execution.
4. **Content integrity:** SHA-256 and byte size are checked before moving and after copying.
5. **Stale-plan protection:** a changed source invalidates the plan before any move begins.
6. **Reversibility:** completed operations are journalled with enough information for reverse-order undo.
7. **Project protection:** recognized software-project directories are excluded by default.
8. **Local processing:** file paths, metadata, and content never leave the machine.

## Threats addressed

| Threat | Control |
| --- | --- |
| `../` or absolute-path escape | Reject unsafe relative paths and verify resolved containment |
| Symbolic-link traversal | Do not follow or organize symbolic links |
| Existing destination overwritten | Exclusive destination creation and preflight checks |
| Source changed after preview | Size and SHA-256 verification |
| Two organizers running together | Exclusive root-level operation lock |
| Failure after some moves | Reverse-order rollback and durable journal state |
| HTML injection through filenames | Escape all user-controlled values in reports |
| Accidental project breakup | Protect directories containing standard project markers |

## Deliberate limitations

- Version 1 never deletes files.
- It does not monitor directories continuously.
- Classification is deterministic and metadata-based; file contents are hashed but not interpreted.
- Undo requires the organized file to be unchanged and the original location to remain free.
- A catastrophic storage or permission failure can prevent complete rollback. The journal retains the failure details for manual recovery.
- Filesystems can change between checks. An exclusive-create destination and post-copy verification minimize this risk, but this is not a replacement for backups.

## Responsible use

Start with the generated demo or a backed-up test directory. Review the JSON or HTML plan before applying it. Avoid selecting an entire home directory. Important data should always have an independent backup.
