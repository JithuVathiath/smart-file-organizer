"""Read-only filesystem discovery."""

from __future__ import annotations

import os
from pathlib import Path

from .models import FileRecord, ScanResult, ScanWarning
from .safety import SafetyError, resolved_root, sha256_file

DEFAULT_IGNORED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".sfo",
    ".tox",
    ".venv",
    "__pycache__",
    "node_modules",
}
PROJECT_MARKERS = {
    ".git",
    "Cargo.toml",
    "go.mod",
    "package.json",
    "pom.xml",
    "pyproject.toml",
}


def _is_hidden(path: Path) -> bool:
    return path.name.startswith(".")


def _is_protected_project(path: Path) -> bool:
    try:
        names = {child.name for child in path.iterdir()}
    except OSError:
        return False
    return bool(names & PROJECT_MARKERS)


def scan_directory(
    root_path: Path,
    *,
    include_hidden: bool = False,
    protect_projects: bool = True,
) -> ScanResult:
    """Scan regular files under ``root_path`` without following links."""

    root = resolved_root(root_path)
    if protect_projects and _is_protected_project(root):
        raise SafetyError(
            "Selected root appears to be a software project; "
            "use --allow-project-files only after reviewing the risk"
        )
    result = ScanResult(root=str(root))

    def on_error(error: OSError) -> None:
        result.warnings.append(ScanWarning(path=error.filename or "?", reason=str(error)))

    for current, directory_names, file_names in os.walk(
        root, topdown=True, followlinks=False, onerror=on_error
    ):
        current_path = Path(current)
        kept_directories: list[str] = []
        for name in sorted(directory_names):
            candidate = current_path / name
            relative = candidate.relative_to(root).as_posix()
            if candidate.is_symlink():
                result.warnings.append(ScanWarning(relative, "symbolic link skipped"))
            elif (
                name in DEFAULT_IGNORED_DIRECTORIES or not include_hidden and _is_hidden(candidate)
            ):
                continue
            elif protect_projects and candidate != root and _is_protected_project(candidate):
                result.protected_directories.append(relative)
            else:
                kept_directories.append(name)
        directory_names[:] = kept_directories

        for name in sorted(file_names):
            candidate = current_path / name
            relative = candidate.relative_to(root).as_posix()
            if not include_hidden and _is_hidden(candidate):
                continue
            if candidate.is_symlink():
                result.warnings.append(ScanWarning(relative, "symbolic link skipped"))
                continue
            try:
                if not candidate.is_file():
                    result.warnings.append(ScanWarning(relative, "non-regular file skipped"))
                    continue
                stat = candidate.stat()
                result.files.append(
                    FileRecord(
                        relative_path=relative,
                        size=stat.st_size,
                        modified_ns=stat.st_mtime_ns,
                        sha256=sha256_file(candidate),
                        extension=candidate.suffix.lower(),
                    )
                )
            except OSError as exc:
                result.warnings.append(ScanWarning(relative, str(exc)))

    result.files.sort(key=lambda item: item.relative_path.casefold())
    result.protected_directories.sort(key=str.casefold)
    return result
