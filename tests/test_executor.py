from __future__ import annotations

from pathlib import Path

import pytest

import smart_file_organizer.executor as executor
from smart_file_organizer.executor import (
    apply_plan,
    default_journal_path,
    preview_undo,
    undo_transaction,
    workspace_lock,
)
from smart_file_organizer.journal import Journal
from smart_file_organizer.models import OrganizationPlan
from smart_file_organizer.safety import SafetyError


def test_apply_and_undo_round_trip(workspace: Path, plan: OrganizationPlan) -> None:
    before = {
        path.relative_to(workspace).as_posix(): path.read_bytes()
        for path in workspace.rglob("*")
        if path.is_file()
    }
    transaction_id = apply_plan(plan, confirmed=True)
    assert not (workspace / "Inbox/bank_statement_2025.pdf").exists()
    assert (workspace / "Finance/Records/2025/bank_statement_2025.pdf").exists()
    assert len(preview_undo(transaction_id, workspace)) == 3

    undo_transaction(transaction_id, workspace, confirmed=True)
    after = {
        path.relative_to(workspace).as_posix(): path.read_bytes()
        for path in workspace.rglob("*")
        if path.is_file() and ".sfo" not in path.parts
    }
    assert after == before
    assert Journal(default_journal_path(workspace)).history()[0].status == "undone"


def test_apply_requires_confirmation(plan: OrganizationPlan) -> None:
    with pytest.raises(SafetyError, match="confirmation"):
        apply_plan(plan)


def test_undo_requires_confirmation(workspace: Path, plan: OrganizationPlan) -> None:
    transaction_id = apply_plan(plan, confirmed=True)
    with pytest.raises(SafetyError, match="confirmation"):
        undo_transaction(transaction_id, workspace)


def test_stale_plan_is_rejected(workspace: Path, plan: OrganizationPlan) -> None:
    (workspace / "Inbox/notes.txt").write_text("changed", encoding="utf-8")
    with pytest.raises(SafetyError, match="changed after planning"):
        apply_plan(plan, confirmed=True)


def test_new_destination_is_never_overwritten(workspace: Path, plan: OrganizationPlan) -> None:
    destination = workspace / "Documents/Text/2026/notes.txt"
    destination.parent.mkdir(parents=True)
    destination.write_text("do not overwrite", encoding="utf-8")
    with pytest.raises(SafetyError, match="appeared after planning"):
        apply_plan(plan, confirmed=True)
    assert destination.read_text(encoding="utf-8") == "do not overwrite"


def test_workspace_lock_rejects_concurrent_operation(tmp_path: Path) -> None:
    with (
        workspace_lock(tmp_path),
        pytest.raises(SafetyError, match="lock exists"),
        workspace_lock(tmp_path),
    ):
        pass
    assert not (tmp_path / ".sfo.lock").exists()


def test_mid_transaction_failure_rolls_back(
    workspace: Path, plan: OrganizationPlan, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = executor.safe_move
    calls = 0

    def unreliable_move(source: Path, destination: Path, expected_hash: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("synthetic failure")
        original(source, destination, expected_hash)

    monkeypatch.setattr(executor, "safe_move", unreliable_move)
    with pytest.raises(SafetyError, match="rollback was attempted"):
        apply_plan(plan, confirmed=True)
    assert (workspace / "Inbox/bank_statement_2025.pdf").exists()
    assert (workspace / "Inbox/photo_2023.jpg").exists()
    entry = Journal(default_journal_path(workspace)).history()[0]
    assert entry.status == "failed"
    assert "synthetic failure" in (entry.error or "")


def test_undo_stops_if_original_path_is_occupied(workspace: Path, plan: OrganizationPlan) -> None:
    transaction_id = apply_plan(plan, confirmed=True)
    original = workspace / "Inbox/notes.txt"
    original.parent.mkdir(exist_ok=True)
    original.write_text("new occupant", encoding="utf-8")
    with pytest.raises(SafetyError, match="occupied"):
        undo_transaction(transaction_id, workspace, confirmed=True)


def test_unknown_and_repeated_undo_are_rejected(workspace: Path, plan: OrganizationPlan) -> None:
    with pytest.raises(KeyError, match="Unknown transaction"):
        preview_undo("missing", workspace)
    transaction_id = apply_plan(plan, confirmed=True)
    undo_transaction(transaction_id, workspace, confirmed=True)
    with pytest.raises(SafetyError, match="Only completed"):
        preview_undo(transaction_id, workspace)


def test_transaction_cannot_be_used_for_different_root(
    workspace: Path, plan: OrganizationPlan, tmp_path: Path
) -> None:
    transaction_id = apply_plan(plan, confirmed=True)
    other = tmp_path / "other"
    other.mkdir()
    # Copying the database simulates an incorrectly supplied root.
    other_db = default_journal_path(other)
    other_db.parent.mkdir()
    other_db.write_bytes(default_journal_path(workspace).read_bytes())
    with pytest.raises(SafetyError, match="different root"):
        preview_undo(transaction_id, other)
