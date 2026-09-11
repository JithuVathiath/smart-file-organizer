"""Command-line interface for Smart File Organizer."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from . import __version__
from .executor import (
    apply_plan,
    default_journal_path,
    preview_undo,
    undo_transaction,
)
from .journal import Journal
from .models import ConflictPolicy, FileRecord
from .planner import create_plan, load_plan, save_plan
from .reports import save_html
from .rules import load_rules
from .safety import SafetyError, sha256_file
from .scanner import scan_directory


def _bytes(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1024 or unit == "TB":
            return f"{int(amount)} B" if unit == "B" else f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{amount:.1f} TB"  # pragma: no cover


def _print_plan(plan: object) -> None:
    operations = plan.operations  # type: ignore[attr-defined]
    counts = Counter(item.status.value for item in operations)
    print(f"Plan {plan.plan_id}")  # type: ignore[attr-defined]
    print(f"Root: {plan.root}")  # type: ignore[attr-defined]
    print(f"Actions: {counts['move']} move, {counts['skip']} skip, {counts['review']} review")
    for item in operations:
        marker = {"move": "MOVE", "skip": "SKIP", "review": "REVIEW"}[item.status.value]
        print(f"[{marker:6}] {item.source} -> {item.destination}")
        print(f"         {item.explanation} ({item.confidence} confidence)")
        if item.conflict:
            print(f"         Conflict: {item.conflict}")


def _write_demo_workspace(target: Path) -> None:
    if target.exists() and any(target.iterdir()):
        raise SafetyError(f"Demo destination must be empty: {target}")
    target.mkdir(parents=True, exist_ok=True)
    files = {
        "Inbox/bank_statement_2025.pdf": b"synthetic bank statement demonstration\n",
        "Inbox/conference_paper_2024.pdf": b"synthetic research paper demonstration\n",
        "Inbox/customer_data.csv": b"customer_id,segment\n1,A\n2,B\n",
        "Inbox/holiday_photo_2023.jpg": b"synthetic image bytes for demonstration\n",
        "Inbox/meeting_notes.txt": b"Synthetic meeting notes. No personal information.\n",
        "Inbox/model.py": b"def predict(value: float) -> float:\n    return value\n",
        "Inbox/project_export.zip": b"synthetic archive bytes for demonstration\n",
        "Code/sample_project/pyproject.toml": b"[project]\nname = 'protected-demo'\nversion = '0.1.0'\n",
        "Code/sample_project/main.py": b"print('this project directory remains intact')\n",
    }
    for relative, content in files.items():
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def _add_scan_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("root", type=Path, help="folder to inspect")
    parser.add_argument(
        "--include-hidden", action="store_true", help="include hidden files and folders"
    )
    parser.add_argument(
        "--allow-project-files",
        action="store_true",
        help="scan inside detected software projects (off by default)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sfo",
        description="Safe, explainable, and reversible local file organization.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    scan = commands.add_parser("scan", help="inspect a folder without changing it")
    _add_scan_options(scan)

    plan = commands.add_parser("plan", help="create a reviewable organization plan")
    _add_scan_options(plan)
    plan.add_argument("--config", type=Path, help="optional TOML rules file")
    plan.add_argument(
        "--conflict",
        choices=[item.value for item in ConflictPolicy],
        default=ConflictPolicy.RENAME.value,
        help="conflict policy (default: rename)",
    )
    plan.add_argument("--output", type=Path, default=Path("sfo-plan.json"))
    plan.add_argument("--report", type=Path, help="write a standalone HTML preview")
    plan.add_argument(
        "--redact-root",
        action="store_true",
        help="hide the local root path in a shared HTML report",
    )

    apply = commands.add_parser("apply", help="apply a previously reviewed plan")
    apply.add_argument("plan", type=Path)
    apply.add_argument(
        "--yes", action="store_true", help="explicitly confirm that the reviewed plan may run"
    )

    undo = commands.add_parser("undo", help="preview or undo a completed transaction")
    undo.add_argument("transaction_id")
    undo.add_argument("root", type=Path)
    undo.add_argument("--yes", action="store_true", help="explicitly confirm the undo")

    history = commands.add_parser("history", help="show transactions for a folder")
    history.add_argument("root", type=Path)

    explain = commands.add_parser("explain", help="explain one file classification")
    explain.add_argument("file", type=Path)
    explain.add_argument("--config", type=Path, help="optional TOML rules file")

    demo = commands.add_parser("demo", help="create and inspect a synthetic demonstration")
    demo.add_argument("destination", type=Path)
    demo.add_argument("--apply", action="store_true", help="also apply the generated demo plan")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        if arguments.command == "scan":
            scan = scan_directory(
                arguments.root,
                include_hidden=arguments.include_hidden,
                protect_projects=not arguments.allow_project_files,
            )
            print(f"Scanned: {scan.root}")
            print(f"Regular files: {len(scan.files)} ({_bytes(scan.total_bytes)})")
            print(f"Protected projects: {len(scan.protected_directories)}")
            print(f"Warnings: {len(scan.warnings)}")
            return 0

        if arguments.command == "plan":
            scan = scan_directory(
                arguments.root,
                include_hidden=arguments.include_hidden,
                protect_projects=not arguments.allow_project_files,
            )
            rules = load_rules(arguments.config)
            plan = create_plan(scan, rules, conflict_policy=ConflictPolicy(arguments.conflict))
            save_plan(plan, arguments.output)
            if arguments.report:
                save_html(
                    plan,
                    arguments.report,
                    display_root="[redacted local folder]" if arguments.redact_root else None,
                )
            _print_plan(plan)
            print(f"\nPlan saved to {arguments.output}")
            if arguments.report:
                print(f"HTML preview saved to {arguments.report}")
            print("No files were changed.")
            return 0

        if arguments.command == "apply":
            plan = load_plan(arguments.plan)
            if not arguments.yes:
                _print_plan(plan)
                print("\nPreview only. Re-run with --yes after reviewing the plan.")
                return 2
            transaction_id = apply_plan(plan, confirmed=True)
            print(f"Applied plan {plan.plan_id} as transaction {transaction_id}")
            print(f"Undo with: sfo undo {transaction_id} {plan.root} --yes")
            return 0

        if arguments.command == "undo":
            actions = preview_undo(arguments.transaction_id, arguments.root)
            print(f"Undo transaction {arguments.transaction_id}: {len(actions)} move(s)")
            for source, destination in actions:
                print(f"[RESTORE] {source} -> {destination}")
            if not arguments.yes:
                print("\nPreview only. Re-run with --yes to restore these paths.")
                return 0
            undo_transaction(arguments.transaction_id, arguments.root, confirmed=True)
            print("Transaction successfully undone.")
            return 0

        if arguments.command == "history":
            root = arguments.root.resolve(strict=True)
            journal = Journal(default_journal_path(root))
            entries = journal.history()
            if not entries:
                print("No transactions recorded for this folder.")
                return 0
            for entry in entries:
                print(
                    f"{entry.id}  {entry.status:10}  plan={entry.plan_id}  "
                    f"started={entry.started_at}"
                )
            return 0

        if arguments.command == "explain":
            path = arguments.file.resolve(strict=True)
            if path.is_symlink() or not path.is_file():
                raise SafetyError(f"Expected a regular file: {path}")
            stat = path.stat()
            record = FileRecord(
                relative_path=path.name,
                size=stat.st_size,
                modified_ns=stat.st_mtime_ns,
                sha256=sha256_file(path),
                extension=path.suffix.casefold(),
            )
            result = load_rules(arguments.config).classify(record)
            print(f"File: {path}")
            print(f"Destination: {result.destination_directory}/{path.name}")
            print(f"Rule: {result.rule_id}")
            print(f"Reason: {result.explanation}")
            print(f"Confidence: {result.confidence}")
            return 0

        if arguments.command == "demo":
            target = arguments.destination.resolve(strict=False)
            _write_demo_workspace(target)
            scan = scan_directory(target)
            plan = create_plan(scan, load_rules())
            plan_path = target.parent / f"{target.name}-plan.json"
            report_path = target.parent / f"{target.name}-report.html"
            save_plan(plan, plan_path)
            save_html(plan, report_path, display_root="[synthetic demo workspace]")
            _print_plan(plan)
            print(f"\nSynthetic demo created at {target}")
            print(f"HTML preview saved to {report_path}")
            if arguments.apply:
                transaction_id = apply_plan(plan, confirmed=True)
                print(f"Demo applied as transaction {transaction_id}")
            else:
                print("No files were changed after creating the synthetic fixture.")
            return 0

        raise AssertionError(f"Unhandled command: {arguments.command}")  # pragma: no cover
    except (KeyError, OSError, SafetyError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def entrypoint() -> None:
    raise SystemExit(main())
