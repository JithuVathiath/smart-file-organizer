"""Preflighted plan execution and reversible transaction handling."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

from .journal import Journal
from .models import OrganizationPlan
from .safety import SafetyError, path_within, safe_move, verify_file


@contextmanager
def workspace_lock(root: Path) -> Iterator[None]:
    lock_path = root / ".sfo.lock"
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise SafetyError(f"Another operation may be active; lock exists: {lock_path}") from exc
    try:
        os.write(descriptor, str(os.getpid()).encode())
        os.close(descriptor)
        yield
    finally:
        with suppress(OSError):
            os.close(descriptor)
        lock_path.unlink(missing_ok=True)


def default_journal_path(root: Path) -> Path:
    return root / ".sfo" / "journal.sqlite3"


def _preflight(plan: OrganizationPlan) -> tuple[Path, list[tuple[Path, Path, object]]]:
    root = Path(plan.root).resolve(strict=True)
    planned: list[tuple[Path, Path, object]] = []
    destinations: set[str] = set()
    for operation in plan.movable:
        source = path_within(root, operation.source)
        destination = path_within(root, operation.destination)
        verify_file(source, operation.size, operation.sha256)
        key = str(destination).casefold()
        if key in destinations:
            raise SafetyError(f"Plan contains duplicate destination: {destination}")
        destinations.add(key)
        if destination.exists() or destination.is_symlink():
            raise SafetyError(f"Destination appeared after planning: {destination}")
        planned.append((source, destination, operation))
    return root, planned


def apply_plan(plan: OrganizationPlan, *, confirmed: bool = False) -> str:
    if not confirmed:
        raise SafetyError("Explicit confirmation is required to apply a plan")
    root, planned = _preflight(plan)
    journal = Journal(default_journal_path(root))
    transaction_id = uuid.uuid4().hex[:12]

    with workspace_lock(root):
        # Re-run preflight under the lock to close the normal stale-plan window.
        _, planned = _preflight(plan)
        operations = [item[2] for item in planned]
        journal.begin(transaction_id, plan.plan_id, str(root), operations)  # type: ignore[arg-type]
        moved: list[tuple[int, Path, Path, object]] = []
        try:
            for sequence, (source, destination, operation) in enumerate(planned):
                safe_move(source, destination, operation.sha256)  # type: ignore[attr-defined]
                journal.operation_status(transaction_id, sequence, "moved")
                moved.append((sequence, source, destination, operation))
        except Exception as exc:
            rollback_errors: list[str] = []
            for sequence, source, destination, operation in reversed(moved):
                try:
                    safe_move(destination, source, operation.sha256)  # type: ignore[attr-defined]
                    journal.operation_status(transaction_id, sequence, "rolled_back")
                except (
                    Exception
                ) as rollback_exc:  # pragma: no cover - catastrophic filesystem failure
                    rollback_errors.append(str(rollback_exc))
            detail = str(exc)
            if rollback_errors:
                detail += f"; rollback errors: {'; '.join(rollback_errors)}"
            journal.finish(transaction_id, "failed", detail)
            raise SafetyError(f"Transaction failed and rollback was attempted: {detail}") from exc
        journal.finish(transaction_id, "completed")
    return transaction_id


def preview_undo(transaction_id: str, root_path: Path) -> list[tuple[str, str]]:
    root = root_path.resolve(strict=True)
    journal = Journal(default_journal_path(root))
    transaction, operations = journal.transaction(transaction_id)
    if Path(transaction.root) != root:
        raise SafetyError("Transaction belongs to a different root")
    if transaction.status != "completed":
        raise SafetyError(f"Only completed transactions can be undone; status={transaction.status}")
    return [
        (str(item["destination"]), str(item["source"]))
        for item in reversed(operations)
        if item["status"] == "moved"
    ]


def undo_transaction(transaction_id: str, root_path: Path, *, confirmed: bool = False) -> None:
    if not confirmed:
        raise SafetyError("Explicit confirmation is required to undo a transaction")
    root = root_path.resolve(strict=True)
    journal = Journal(default_journal_path(root))
    transaction, operations = journal.transaction(transaction_id)
    if Path(transaction.root) != root:
        raise SafetyError("Transaction belongs to a different root")
    if transaction.status != "completed":
        raise SafetyError(f"Only completed transactions can be undone; status={transaction.status}")

    candidates: list[tuple[int, Path, Path, str, int]] = []
    for item in reversed(operations):
        if item["status"] != "moved":
            continue
        source = path_within(root, str(item["destination"]))
        destination = path_within(root, str(item["source"]))
        verify_file(source, int(item["size"]), str(item["sha256"]))
        if destination.exists() or destination.is_symlink():
            raise SafetyError(f"Original path is occupied; undo stopped: {destination}")
        candidates.append(
            (int(item["sequence"]), source, destination, str(item["sha256"]), int(item["size"]))
        )

    with workspace_lock(root):
        undone: list[tuple[int, Path, Path, str]] = []
        try:
            for sequence, source, destination, expected_hash, _ in candidates:
                safe_move(source, destination, expected_hash)
                journal.operation_status(transaction_id, sequence, "undone")
                undone.append((sequence, source, destination, expected_hash))
        except Exception as exc:
            for sequence, original_source, restored_path, expected_hash in reversed(undone):
                try:
                    safe_move(restored_path, original_source, expected_hash)
                    journal.operation_status(transaction_id, sequence, "moved")
                except Exception:  # pragma: no cover - catastrophic filesystem failure
                    pass
            raise SafetyError(f"Undo failed and restoration was attempted: {exc}") from exc
        journal.finish(transaction_id, "undone")
