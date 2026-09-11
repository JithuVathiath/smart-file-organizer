"""Reproducible end-to-end benchmark using synthetic, non-sensitive files."""

from __future__ import annotations

import argparse
import json
import platform
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from smart_file_organizer.planner import create_plan
from smart_file_organizer.rules import load_rules
from smart_file_organizer.scanner import scan_directory

EXTENSIONS = (".pdf", ".jpg", ".csv", ".txt", ".py", ".zip", ".json")


def create_corpus(root: Path, file_count: int) -> None:
    for index in range(file_count):
        bucket = root / "Inbox" / f"batch-{index % 100:03d}"
        bucket.mkdir(parents=True, exist_ok=True)
        extension = EXTENSIONS[index % len(EXTENSIONS)]
        (bucket / f"synthetic_{index:06d}_2025{extension}").write_bytes(
            f"synthetic benchmark record {index}\n".encode()
        )


def run_case(file_count: int) -> dict[str, int | float]:
    with tempfile.TemporaryDirectory(prefix="sfo-benchmark-") as directory:
        root = Path(directory)
        started = time.perf_counter()
        create_corpus(root, file_count)
        creation_seconds = time.perf_counter() - started

        started = time.perf_counter()
        scan = scan_directory(root)
        scan_seconds = time.perf_counter() - started

        started = time.perf_counter()
        plan = create_plan(scan, load_rules())
        planning_seconds = time.perf_counter() - started
        return {
            "files": len(scan.files),
            "bytes": scan.total_bytes,
            "planned_moves": len(plan.movable),
            "creation_seconds": round(creation_seconds, 4),
            "scan_seconds": round(scan_seconds, 4),
            "planning_seconds": round(planning_seconds, 4),
            "scan_files_per_second": round(file_count / scan_seconds),
            "plan_files_per_second": round(file_count / planning_seconds),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--files", type=int, nargs="+", default=[1_000, 10_000, 100_000])
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if any(value < 1 for value in arguments.files):
        parser.error("file counts must be positive")

    document = {
        "generated_at": datetime.now(UTC).isoformat(),
        "system": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "method": "Real temporary files; SHA-256 content hashing enabled; median-free single run.",
        "results": [run_case(value) for value in arguments.files],
    }
    payload = json.dumps(document, indent=2) + "\n"
    print(payload, end="")
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(payload, encoding="utf-8")


if __name__ == "__main__":
    main()
