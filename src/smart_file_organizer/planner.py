"""Create immutable, reviewable organization plans."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from .models import (
    ConflictPolicy,
    OperationStatus,
    OrganizationPlan,
    PlanOperation,
    ScanResult,
)
from .rules import RuleSet
from .safety import path_within, safe_relative_path, sha256_file


def _versioned_path(destination: Path, reserved: set[str]) -> Path:
    candidate = destination
    number = 1
    while candidate.as_posix().casefold() in reserved:
        candidate = destination.with_name(f"{destination.stem} ({number}){destination.suffix}")
        number += 1
    return candidate


def _plan_identifier(root: str, operations: list[PlanOperation]) -> str:
    payload = {
        "root": root,
        "operations": [
            {
                "source": item.source,
                "destination": item.destination,
                "sha256": item.sha256,
                "status": item.status.value,
            }
            for item in operations
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:12]


def create_plan(
    scan: ScanResult,
    rules: RuleSet,
    *,
    conflict_policy: ConflictPolicy = ConflictPolicy.RENAME,
) -> OrganizationPlan:
    root = Path(scan.root)
    existing: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            relative = path.relative_to(root)
            existing[relative.as_posix().casefold()] = path
    reserved = set(existing)
    operations: list[PlanOperation] = []

    for record in scan.files:
        classification = rules.classify(record)
        source_relative = safe_relative_path(record.relative_path)
        destination_relative = safe_relative_path(
            f"{classification.destination_directory}/{source_relative.name}"
        )
        path_within(root, destination_relative.as_posix())

        base_operation = PlanOperation(
            source=source_relative.as_posix(),
            destination=destination_relative.as_posix(),
            sha256=record.sha256,
            size=record.size,
            rule_id=classification.rule_id,
            explanation=classification.explanation,
            confidence=classification.confidence,
        )

        if source_relative.as_posix().casefold() == destination_relative.as_posix().casefold():
            operations.append(
                replace(
                    base_operation,
                    status=OperationStatus.SKIP,
                    conflict="already in the recommended location",
                )
            )
            continue

        key = destination_relative.as_posix().casefold()
        if key in reserved:
            existing_path = existing.get(key)
            is_same_file = existing_path is not None and (
                existing_path.stat().st_size == record.size
                and sha256_file(existing_path) == record.sha256
            )
            if is_same_file:
                operations.append(
                    replace(
                        base_operation,
                        status=OperationStatus.SKIP,
                        conflict="identical destination already exists",
                    )
                )
                continue
            if conflict_policy is ConflictPolicy.SKIP:
                operations.append(
                    replace(
                        base_operation,
                        status=OperationStatus.SKIP,
                        conflict="destination already exists",
                    )
                )
                continue
            if conflict_policy is ConflictPolicy.REVIEW:
                operations.append(
                    replace(
                        base_operation,
                        status=OperationStatus.REVIEW,
                        conflict="destination requires manual review",
                    )
                )
                continue
            destination_relative = _versioned_path(destination_relative, reserved)
            base_operation = replace(
                base_operation,
                destination=destination_relative.as_posix(),
                conflict="renamed to avoid overwriting an existing file",
            )

        reserved.add(destination_relative.as_posix().casefold())
        operations.append(base_operation)

    operations.sort(key=lambda item: item.source.casefold())
    return OrganizationPlan(
        schema_version=1,
        plan_id=_plan_identifier(scan.root, operations),
        created_at=datetime.now(UTC).isoformat(),
        root=scan.root,
        conflict_policy=conflict_policy,
        operations=operations,
        warnings=scan.warnings,
    )


def save_plan(plan: OrganizationPlan, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan.to_dict(), indent=2) + "\n", encoding="utf-8")


def load_plan(path: Path) -> OrganizationPlan:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    return OrganizationPlan.from_dict(value)
