from __future__ import annotations

import json
from pathlib import Path

import pytest

from smart_file_organizer.models import ConflictPolicy, OperationStatus, OrganizationPlan
from smart_file_organizer.planner import create_plan, load_plan, save_plan
from smart_file_organizer.rules import load_rules
from smart_file_organizer.scanner import scan_directory


def test_plan_is_deterministic_except_creation_time(workspace: Path) -> None:
    first = create_plan(scan_directory(workspace), load_rules())
    second = create_plan(scan_directory(workspace), load_rules())
    assert first.plan_id == second.plan_id
    assert first.operations == second.operations
    assert len(first.movable) == 3


def test_plan_round_trip(tmp_path: Path, plan: OrganizationPlan) -> None:
    path = tmp_path / "plan.json"
    save_plan(plan, path)
    loaded = load_plan(path)
    assert loaded.to_dict() == plan.to_dict()
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 1


def test_unsupported_plan_schema(tmp_path: Path) -> None:
    path = tmp_path / "plan.json"
    path.write_text('{"schema_version": 99}', encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported"):
        load_plan(path)


@pytest.mark.parametrize(
    ("policy", "expected_status", "expected_name"),
    [
        (ConflictPolicy.RENAME, OperationStatus.MOVE, "report (1).pdf"),
        (ConflictPolicy.SKIP, OperationStatus.SKIP, "report.pdf"),
        (ConflictPolicy.REVIEW, OperationStatus.REVIEW, "report.pdf"),
    ],
)
def test_conflict_policies(
    tmp_path: Path,
    policy: ConflictPolicy,
    expected_status: OperationStatus,
    expected_name: str,
) -> None:
    source = tmp_path / "Inbox/report.pdf"
    destination = tmp_path / "Documents/PDF/2026/report.pdf"
    source.parent.mkdir()
    destination.parent.mkdir(parents=True)
    source.write_text("new", encoding="utf-8")
    destination.write_text("old", encoding="utf-8")
    timestamp = 1_767_225_600  # 2026-01-01
    source.touch()
    destination.touch()
    import os

    os.utime(source, (timestamp, timestamp))
    os.utime(destination, (timestamp, timestamp))
    plan = create_plan(scan_directory(tmp_path), load_rules(), conflict_policy=policy)
    operation = next(item for item in plan.operations if item.source == "Inbox/report.pdf")
    assert operation.status is expected_status
    assert Path(operation.destination).name == expected_name
    assert operation.conflict


def test_identical_destination_is_skipped(tmp_path: Path) -> None:
    source = tmp_path / "Inbox/report_2026.pdf"
    destination = tmp_path / "Documents/PDF/2026/report_2026.pdf"
    source.parent.mkdir()
    destination.parent.mkdir(parents=True)
    source.write_text("same", encoding="utf-8")
    destination.write_text("same", encoding="utf-8")
    plan = create_plan(scan_directory(tmp_path), load_rules())
    operation = next(item for item in plan.operations if item.source.startswith("Inbox"))
    assert operation.status is OperationStatus.SKIP
    assert operation.conflict == "identical destination already exists"


def test_file_already_organized_is_skipped(tmp_path: Path) -> None:
    target = tmp_path / "Data/2026/data_2026.json"
    target.parent.mkdir(parents=True)
    target.write_text("{}", encoding="utf-8")
    plan = create_plan(scan_directory(tmp_path), load_rules())
    assert plan.operations[0].status is OperationStatus.SKIP
    assert plan.operations[0].conflict == "already in the recommended location"


def test_multiple_sources_receive_unique_destinations(tmp_path: Path) -> None:
    first = tmp_path / "A/report_2026.pdf"
    second = tmp_path / "B/report_2026.pdf"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("one", encoding="utf-8")
    second.write_text("two", encoding="utf-8")
    plan = create_plan(scan_directory(tmp_path), load_rules())
    destinations = [item.destination for item in plan.movable]
    assert destinations == [
        "Documents/PDF/2026/report_2026.pdf",
        "Documents/PDF/2026/report_2026 (1).pdf",
    ]
