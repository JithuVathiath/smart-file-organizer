from __future__ import annotations

from pathlib import Path

import pytest

from smart_file_organizer.models import FileRecord
from smart_file_organizer.rules import Rule, RuleSet, load_rules
from smart_file_organizer.safety import SafetyError


def record(name: str, extension: str, *, modified_ns: int = 0) -> FileRecord:
    return FileRecord(name, 1, modified_ns, "digest", extension)


@pytest.mark.parametrize(
    ("name", "extension", "expected"),
    [
        ("bank_statement_2025.pdf", ".pdf", "Finance/Records/2025"),
        ("conference_paper_2024.pdf", ".pdf", "Research/Papers/2024"),
        ("slides.pptx", ".pptx", "Documents/Presentations/1970"),
        ("photo.jpg", ".jpg", "Media/Images/1970"),
        ("model.py", ".py", "Code/Snippets/py"),
        ("unknown.xyz", ".xyz", "Other/xyz"),
        ("LICENSE", "", "Other/no-extension"),
    ],
)
def test_builtin_classification(name: str, extension: str, expected: str) -> None:
    assert load_rules().classify(record(name, extension)).destination_directory == expected


def test_rule_match_with_regex() -> None:
    rule = Rule("test", "Folder", 1, "reason", name_regex=r"report_\d+")
    assert rule.matches(record("report_12.txt", ".txt"))
    assert not rule.matches(record("notes.txt", ".txt"))


def test_custom_rules_override_builtins(tmp_path: Path) -> None:
    config = tmp_path / "rules.toml"
    config.write_text(
        """[[rules]]
id = "resumes"
destination = "Career/{year}"
priority = 500
extensions = ["pdf"]
name_contains = ["resume"]
explanation = "resume keyword"
""",
        encoding="utf-8",
    )
    result = load_rules(config).classify(record("my_resume_2026.pdf", ".pdf"))
    assert result.rule_id == "resumes"
    assert result.destination_directory == "Career/2026"


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("[settings]\nvalue=1", "Unknown configuration sections"),
        ("rules = 'bad'", "array of tables"),
        ("[[rules]]\nid='Bad Id'\ndestination='Folder'", "Invalid rule id"),
        ("[[rules]]\nid='okay'", "Missing rule fields"),
        ("[[rules]]\nid='okay'\ndestination='../escape'", "Unsafe relative path"),
        ("[[rules]]\nid='okay'\ndestination='Folder'\nconfidence='certain'", "confidence"),
        ("[[rules]]\nid='okay'\ndestination='Folder'\nunknown=1", "Unknown rule fields"),
        ("[[rules]]\nid='same'\ndestination='A'\n[[rules]]\nid='same'\ndestination='B'", "unique"),
    ],
)
def test_invalid_configurations(tmp_path: Path, content: str, message: str) -> None:
    config = tmp_path / "rules.toml"
    config.write_text(content, encoding="utf-8")
    with pytest.raises((SafetyError, ValueError), match=message):
        load_rules(config)


def test_invalid_template_key_is_rejected(tmp_path: Path) -> None:
    config = tmp_path / "rules.toml"
    config.write_text("[[rules]]\nid='okay'\ndestination='Folder/{missing}'", encoding="utf-8")
    with pytest.raises(KeyError):
        load_rules(config)


def test_rule_set_requires_fallback() -> None:
    with pytest.raises(RuntimeError, match="fallback"):
        RuleSet([]).classify(record("file.txt", ".txt"))
