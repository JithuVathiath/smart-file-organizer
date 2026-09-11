from __future__ import annotations

import random
import string
from pathlib import Path

import pytest

from smart_file_organizer.safety import (
    SafetyError,
    path_within,
    resolved_root,
    safe_move,
    safe_relative_path,
    sha256_file,
    verify_file,
)


def test_sha256_and_verify(tmp_path: Path) -> None:
    file = tmp_path / "file.txt"
    file.write_text("safe", encoding="utf-8")
    digest = sha256_file(file)
    assert digest == "8b3369944dd2a3fab39e32d1aeb1f763946a458ae3e6368a46432adc8f3a0860"
    verify_file(file, 4, digest)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "../secret",
        "folder/../secret",
        "/absolute",
        ".",
        r"C:\Windows\system.ini",
        r"\\server\share\secret",
        r"folder\..\secret",
    ],
)
def test_rejects_unsafe_relative_paths(value: str) -> None:
    with pytest.raises(SafetyError):
        safe_relative_path(value)


def test_path_within_accepts_nested_path(tmp_path: Path) -> None:
    assert path_within(tmp_path.resolve(), "one/two.txt") == tmp_path / "one/two.txt"


def test_generated_relative_paths_never_escape_root(tmp_path: Path) -> None:
    generator = random.Random(2026)
    alphabet = string.ascii_letters + string.digits + " _-"
    root = tmp_path.resolve()
    for _ in range(250):
        parts = [
            "".join(generator.choice(alphabet) for _ in range(generator.randint(1, 20))).strip()
            or "file"
            for _ in range(generator.randint(1, 5))
        ]
        relative = "/".join(parts)
        assert path_within(root, relative).is_relative_to(root)


def test_resolved_root_validation(tmp_path: Path) -> None:
    assert resolved_root(tmp_path) == tmp_path.resolve()
    file = tmp_path / "file"
    file.touch()
    with pytest.raises(SafetyError, match="not a directory"):
        resolved_root(file)


def test_verify_detects_changed_size_and_hash(tmp_path: Path) -> None:
    file = tmp_path / "file.txt"
    file.write_text("first", encoding="utf-8")
    digest = sha256_file(file)
    with pytest.raises(SafetyError, match="size changed"):
        verify_file(file, 99, digest)
    file.write_text("other", encoding="utf-8")
    with pytest.raises(SafetyError, match="content changed"):
        verify_file(file, 5, digest)


def test_verify_rejects_non_file(tmp_path: Path) -> None:
    with pytest.raises(SafetyError, match="regular file"):
        verify_file(tmp_path, 0, "missing")


def test_safe_move_preserves_content_and_rejects_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    destination = tmp_path / "nested/destination.txt"
    source.write_text("content", encoding="utf-8")
    digest = sha256_file(source)
    safe_move(source, destination, digest)
    assert not source.exists()
    assert destination.read_text(encoding="utf-8") == "content"

    source.write_text("new", encoding="utf-8")
    with pytest.raises(SafetyError, match="already exists"):
        safe_move(source, destination, sha256_file(source))


def test_safe_move_rejects_directory(tmp_path: Path) -> None:
    with pytest.raises(SafetyError, match="regular file"):
        safe_move(tmp_path, tmp_path / "out", "digest")


def test_safe_move_cleans_partial_copy_on_bad_hash(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"
    source.write_text("content", encoding="utf-8")
    with pytest.raises(SafetyError, match="Integrity check"):
        safe_move(source, destination, "wrong")
    assert source.exists()
    assert not destination.exists()
