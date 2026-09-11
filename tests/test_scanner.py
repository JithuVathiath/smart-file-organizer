from __future__ import annotations

from pathlib import Path

import pytest

from smart_file_organizer.safety import SafetyError
from smart_file_organizer.scanner import scan_directory


def test_scanner_finds_regular_files_in_stable_order(workspace: Path) -> None:
    result = scan_directory(workspace)
    paths = [item.relative_path for item in result.files]
    assert paths == sorted(paths, key=str.casefold)
    assert len(paths) == 3
    assert result.total_bytes == sum(item.size for item in result.files)


def test_scanner_skips_hidden_files_by_default(tmp_path: Path) -> None:
    (tmp_path / ".hidden.txt").write_text("secret", encoding="utf-8")
    (tmp_path / "visible.txt").write_text("public", encoding="utf-8")
    assert [item.name for item in scan_directory(tmp_path).files] == ["visible.txt"]
    included = scan_directory(tmp_path, include_hidden=True)
    assert {item.name for item in included.files} == {".hidden.txt", "visible.txt"}


def test_scanner_protects_software_projects(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]", encoding="utf-8")
    (project / "main.py").write_text("pass", encoding="utf-8")
    protected = scan_directory(tmp_path)
    assert protected.files == []
    assert protected.protected_directories == ["project"]
    unprotected = scan_directory(tmp_path, protect_projects=False)
    assert len(unprotected.files) == 2


def test_scanner_refuses_project_as_selected_root(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
    with pytest.raises(SafetyError, match="appears to be a software project"):
        scan_directory(tmp_path)
    assert len(scan_directory(tmp_path, protect_projects=False).files) == 1


def test_scanner_skips_symbolic_links(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("data", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symbolic links are unavailable on this runner")
    result = scan_directory(tmp_path)
    assert [item.name for item in result.files] == ["target.txt"]
    assert result.warnings[0].reason == "symbolic link skipped"
