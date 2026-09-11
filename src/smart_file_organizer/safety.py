"""Path validation and file-integrity primitives."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

CHUNK_SIZE = 1024 * 1024


class SafetyError(RuntimeError):
    """Raised when an operation would violate a safety invariant."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def resolved_root(path: Path) -> Path:
    root = path.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise SafetyError(f"Selected root is not a directory: {root}")
    return root


def safe_relative_path(value: str) -> Path:
    path = Path(value)
    if (
        path.is_absolute()
        or value in {"", ".", ".."}
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise SafetyError(f"Unsafe relative path: {value!r}")
    return path


def path_within(root: Path, relative: str) -> Path:
    rel = safe_relative_path(relative)
    candidate = (root / rel).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise SafetyError(f"Path escapes the selected root: {relative!r}") from exc
    return candidate


def verify_file(path: Path, expected_size: int, expected_hash: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise SafetyError(f"Expected a regular file: {path}")
    stat = path.stat()
    if stat.st_size != expected_size:
        raise SafetyError(f"File size changed after planning: {path}")
    if sha256_file(path) != expected_hash:
        raise SafetyError(f"File content changed after planning: {path}")


def safe_move(source: Path, destination: Path, expected_hash: str) -> None:
    """Move a file without overwriting, verifying the copied bytes before deletion."""

    if source.is_symlink() or not source.is_file():
        raise SafetyError(f"Source is not a regular file: {source}")
    if destination.exists() or destination.is_symlink():
        raise SafetyError(f"Destination already exists: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with source.open("rb") as input_stream, destination.open("xb") as output_stream:
            shutil.copyfileobj(input_stream, output_stream, length=CHUNK_SIZE)
            output_stream.flush()
            os.fsync(output_stream.fileno())
        shutil.copystat(source, destination, follow_symlinks=False)
        if sha256_file(destination) != expected_hash:
            raise SafetyError(f"Integrity check failed after copying to {destination}")
        source.unlink()
    except Exception:
        if destination.exists() and source.exists():
            destination.unlink(missing_ok=True)
        raise
