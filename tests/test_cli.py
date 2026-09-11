from __future__ import annotations

from pathlib import Path

import pytest

import smart_file_organizer.cli as cli


def test_scan_plan_apply_history_and_undo_commands(
    workspace: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["scan", str(workspace)]) == 0
    assert "Regular files: 3" in capsys.readouterr().out

    plan_path = tmp_path / "plan.json"
    report_path = tmp_path / "report.html"
    assert (
        cli.main(
            [
                "plan",
                str(workspace),
                "--output",
                str(plan_path),
                "--report",
                str(report_path),
                "--redact-root",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "No files were changed" in output
    assert plan_path.exists() and report_path.exists()
    assert "[redacted local folder]" in report_path.read_text(encoding="utf-8")

    assert cli.main(["apply", str(plan_path)]) == 2
    assert "Preview only" in capsys.readouterr().out
    assert cli.main(["apply", str(plan_path), "--yes"]) == 0
    apply_output = capsys.readouterr().out
    transaction_id = apply_output.split("transaction ", 1)[1].splitlines()[0]

    assert cli.main(["history", str(workspace)]) == 0
    assert transaction_id in capsys.readouterr().out
    assert cli.main(["undo", transaction_id, str(workspace)]) == 0
    assert "Preview only" in capsys.readouterr().out
    assert cli.main(["undo", transaction_id, str(workspace), "--yes"]) == 0
    assert "successfully undone" in capsys.readouterr().out


def test_explain_and_empty_history(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    file = tmp_path / "research_paper_2026.pdf"
    file.write_text("paper", encoding="utf-8")
    assert cli.main(["explain", str(file)]) == 0
    output = capsys.readouterr().out
    assert "Rule: research-papers" in output
    assert "Research/Papers/2026" in output

    empty = tmp_path / "empty"
    empty.mkdir()
    assert cli.main(["history", str(empty)]) == 0
    assert "No transactions" in capsys.readouterr().out


def test_demo_preview_and_apply(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    preview = tmp_path / "preview-demo"
    assert cli.main(["demo", str(preview)]) == 0
    output = capsys.readouterr().out
    assert "Synthetic demo created" in output
    assert "No files were changed" in output
    assert (tmp_path / "preview-demo-report.html").exists()

    applied = tmp_path / "applied-demo"
    assert cli.main(["demo", str(applied), "--apply"]) == 0
    assert "Demo applied as transaction" in capsys.readouterr().out
    assert (applied / "Finance/Records/2025/bank_statement_2025.pdf").exists()


def test_cli_reports_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "missing"
    assert cli.main(["scan", str(missing)]) == 1
    assert "Error:" in capsys.readouterr().err

    occupied = tmp_path / "demo"
    occupied.mkdir()
    (occupied / "existing").touch()
    assert cli.main(["demo", str(occupied)]) == 1
    assert "must be empty" in capsys.readouterr().err


def test_scan_options_and_custom_config(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]", encoding="utf-8")
    (project / "resume_2026.pdf").write_text("resume", encoding="utf-8")
    hidden = tmp_path / ".visible-with-flag.txt"
    hidden.write_text("hidden", encoding="utf-8")
    config = tmp_path / "rules.toml"
    config.write_text(
        "[[rules]]\nid='resume'\ndestination='Career/{year}'\n"
        "priority=500\nextensions=['pdf']\nname_contains=['resume']\n",
        encoding="utf-8",
    )
    plan = tmp_path / "plan.json"
    assert (
        cli.main(
            [
                "plan",
                str(tmp_path),
                "--allow-project-files",
                "--include-hidden",
                "--config",
                str(config),
                "--conflict",
                "review",
                "--output",
                str(plan),
            ]
        )
        == 0
    )
    assert "Career/2026/resume_2026.pdf" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("value", "expected"),
    [(10, "10 B"), (2048, "2.0 KB"), (2 * 1024**2, "2.0 MB"), (1024**3, "1.0 GB")],
)
def test_cli_byte_format(value: int, expected: str) -> None:
    assert cli._bytes(value) == expected


def test_entrypoint_raises_system_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "main", lambda: 7)
    with pytest.raises(SystemExit) as error:
        cli.entrypoint()
    assert error.value.code == 7
