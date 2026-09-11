"""SQLite transaction history for apply and undo operations."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .models import PlanOperation

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    root TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    error TEXT
);
CREATE TABLE IF NOT EXISTS operations (
    transaction_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    source TEXT NOT NULL,
    destination TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size INTEGER NOT NULL,
    status TEXT NOT NULL,
    PRIMARY KEY (transaction_id, sequence),
    FOREIGN KEY (transaction_id) REFERENCES transactions(id)
);
"""


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    id: str
    plan_id: str
    root: str
    started_at: str
    completed_at: str | None
    status: str
    error: str | None


class Journal:
    def __init__(self, database_path: Path):
        self.database_path = database_path
        database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def begin(
        self, transaction_id: str, plan_id: str, root: str, operations: list[PlanOperation]
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO transactions VALUES (?, ?, ?, ?, NULL, 'applying', NULL)",
                (transaction_id, plan_id, root, datetime.now(UTC).isoformat()),
            )
            connection.executemany(
                "INSERT INTO operations VALUES (?, ?, ?, ?, ?, ?, 'pending')",
                [
                    (
                        transaction_id,
                        sequence,
                        item.source,
                        item.destination,
                        item.sha256,
                        item.size,
                    )
                    for sequence, item in enumerate(operations)
                ],
            )

    def operation_status(self, transaction_id: str, sequence: int, status: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE operations SET status = ? WHERE transaction_id = ? AND sequence = ?",
                (status, transaction_id, sequence),
            )

    def finish(self, transaction_id: str, status: str, error: str | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE transactions SET completed_at = ?, status = ?, error = ? WHERE id = ?",
                (datetime.now(UTC).isoformat(), status, error, transaction_id),
            )

    def history(self) -> list[HistoryEntry]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM transactions ORDER BY started_at DESC"
            ).fetchall()
        return [HistoryEntry(**dict(row)) for row in rows]

    def transaction(self, transaction_id: str) -> tuple[HistoryEntry, list[dict[str, object]]]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM transactions WHERE id = ?", (transaction_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown transaction: {transaction_id}")
            operations = connection.execute(
                "SELECT * FROM operations WHERE transaction_id = ? ORDER BY sequence",
                (transaction_id,),
            ).fetchall()
        return HistoryEntry(**dict(row)), [dict(item) for item in operations]
