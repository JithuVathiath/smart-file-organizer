from __future__ import annotations

from pathlib import Path

from smart_file_organizer.journal import Journal
from smart_file_organizer.models import PlanOperation


def test_journal_lifecycle(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "journal.sqlite3")
    operation = PlanOperation("a", "b", "hash", 1, "rule", "reason", "high")
    journal.begin("tx", "plan", "/root", [operation])
    journal.operation_status("tx", 0, "moved")
    journal.finish("tx", "completed")
    entry, operations = journal.transaction("tx")
    assert entry.status == "completed"
    assert operations[0]["status"] == "moved"
    assert journal.history() == [entry]
