from __future__ import annotations

from pathlib import Path

import pytest

from smart_file_organizer.models import ConflictPolicy
from smart_file_organizer.planner import create_plan
from smart_file_organizer.rules import load_rules
from smart_file_organizer.scanner import scan_directory


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    inbox = root / "Inbox"
    inbox.mkdir(parents=True)
    (inbox / "bank_statement_2025.pdf").write_text("statement", encoding="utf-8")
    (inbox / "photo_2023.jpg").write_bytes(b"image")
    (inbox / "notes.txt").write_text("notes", encoding="utf-8")
    return root


@pytest.fixture
def plan(workspace: Path):
    return create_plan(
        scan_directory(workspace), load_rules(), conflict_policy=ConflictPolicy.RENAME
    )
