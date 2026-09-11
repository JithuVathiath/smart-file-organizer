"""Serializable domain models used throughout the application."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class ConflictPolicy(StrEnum):
    """Supported behavior when a planned destination already exists."""

    RENAME = "rename"
    SKIP = "skip"
    REVIEW = "review"


class OperationStatus(StrEnum):
    MOVE = "move"
    SKIP = "skip"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class FileRecord:
    relative_path: str
    size: int
    modified_ns: int
    sha256: str
    extension: str

    @property
    def name(self) -> str:
        return Path(self.relative_path).name

    @property
    def stem(self) -> str:
        return Path(self.relative_path).stem


@dataclass(frozen=True, slots=True)
class Classification:
    destination_directory: str
    rule_id: str
    explanation: str
    confidence: str


@dataclass(frozen=True, slots=True)
class PlanOperation:
    source: str
    destination: str
    sha256: str
    size: int
    rule_id: str
    explanation: str
    confidence: str
    status: OperationStatus = OperationStatus.MOVE
    conflict: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> PlanOperation:
        return cls(
            source=value["source"],
            destination=value["destination"],
            sha256=value["sha256"],
            size=int(value["size"]),
            rule_id=value["rule_id"],
            explanation=value["explanation"],
            confidence=value["confidence"],
            status=OperationStatus(value.get("status", "move")),
            conflict=value.get("conflict"),
        )


@dataclass(frozen=True, slots=True)
class ScanWarning:
    path: str
    reason: str


@dataclass(slots=True)
class ScanResult:
    root: str
    files: list[FileRecord] = field(default_factory=list)
    warnings: list[ScanWarning] = field(default_factory=list)
    protected_directories: list[str] = field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        return sum(item.size for item in self.files)


@dataclass(slots=True)
class OrganizationPlan:
    schema_version: int
    plan_id: str
    created_at: str
    root: str
    conflict_policy: ConflictPolicy
    operations: list[PlanOperation]
    warnings: list[ScanWarning] = field(default_factory=list)

    @property
    def movable(self) -> list[PlanOperation]:
        return [item for item in self.operations if item.status is OperationStatus.MOVE]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "created_at": self.created_at,
            "root": self.root,
            "conflict_policy": self.conflict_policy.value,
            "operations": [
                {**asdict(item), "status": item.status.value} for item in self.operations
            ],
            "warnings": [asdict(item) for item in self.warnings],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> OrganizationPlan:
        if int(value.get("schema_version", 0)) != 1:
            raise ValueError("Unsupported plan schema version")
        return cls(
            schema_version=1,
            plan_id=value["plan_id"],
            created_at=value["created_at"],
            root=value["root"],
            conflict_policy=ConflictPolicy(value["conflict_policy"]),
            operations=[PlanOperation.from_dict(item) for item in value["operations"]],
            warnings=[ScanWarning(**item) for item in value.get("warnings", [])],
        )
