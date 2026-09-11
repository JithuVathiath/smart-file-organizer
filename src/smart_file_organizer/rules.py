"""Deterministic and explainable file-classification rules."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import Classification, FileRecord
from .safety import SafetyError, safe_relative_path

YEAR_PATTERN = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    destination: str
    priority: int
    explanation: str
    confidence: str = "high"
    extensions: tuple[str, ...] = ()
    name_contains: tuple[str, ...] = ()
    name_regex: str | None = None

    def matches(self, record: FileRecord) -> bool:
        name = record.name.casefold()
        extension_match = not self.extensions or record.extension in self.extensions
        contains_match = not self.name_contains or any(
            token.casefold() in name for token in self.name_contains
        )
        regex_match = (
            self.name_regex is None
            or re.search(self.name_regex, record.name, flags=re.IGNORECASE) is not None
        )
        return extension_match and contains_match and regex_match


@dataclass(slots=True)
class RuleSet:
    rules: list[Rule] = field(default_factory=list)

    def classify(self, record: FileRecord) -> Classification:
        for rule in sorted(self.rules, key=lambda item: (-item.priority, item.id)):
            if rule.matches(record):
                destination = _render_destination(rule.destination, record)
                return Classification(
                    destination_directory=destination,
                    rule_id=rule.id,
                    explanation=rule.explanation,
                    confidence=rule.confidence,
                )
        raise RuntimeError("The fallback rule is missing")


def _year(record: FileRecord) -> str:
    match = YEAR_PATTERN.search(record.name)
    if match:
        return match.group(1)
    return str(datetime.fromtimestamp(record.modified_ns / 1_000_000_000).year)


def _render_destination(template: str, record: FileRecord) -> str:
    values = {
        "year": _year(record),
        "extension": record.extension.removeprefix(".") or "no-extension",
        "stem": record.stem,
    }
    try:
        rendered = template.format_map(values)
    except (KeyError, ValueError) as exc:
        raise SafetyError(f"Invalid destination template {template!r}: {exc}") from exc
    return safe_relative_path(rendered).as_posix()


def _normalise_extensions(values: list[str]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                value.casefold() if value.startswith(".") else f".{value.casefold()}"
                for value in values
            }
        )
    )


def _custom_rule(value: dict[str, Any]) -> Rule:
    allowed = {
        "id",
        "destination",
        "priority",
        "explanation",
        "confidence",
        "extensions",
        "name_contains",
        "name_regex",
    }
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"Unknown rule fields: {', '.join(sorted(unknown))}")
    required = {"id", "destination"}
    missing = required - set(value)
    if missing:
        raise ValueError(f"Missing rule fields: {', '.join(sorted(missing))}")
    rule_id = str(value["id"]).strip()
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", rule_id):
        raise ValueError(f"Invalid rule id: {rule_id!r}")
    destination = str(value["destination"])
    # Validate path syntax and template keys with representative values.
    rendered = destination.format_map({"year": "2026", "extension": "pdf", "stem": "example"})
    safe_relative_path(rendered)
    name_regex = value.get("name_regex")
    if name_regex is not None:
        re.compile(str(name_regex))
    confidence = str(value.get("confidence", "high")).casefold()
    if confidence not in {"high", "medium", "low"}:
        raise ValueError("Rule confidence must be high, medium, or low")
    return Rule(
        id=rule_id,
        destination=destination,
        priority=int(value.get("priority", 100)),
        explanation=str(value.get("explanation", f"Matched custom rule {rule_id}")),
        confidence=confidence,
        extensions=_normalise_extensions(list(value.get("extensions", []))),
        name_contains=tuple(str(item) for item in value.get("name_contains", [])),
        name_regex=str(name_regex) if name_regex is not None else None,
    )


def load_rules(config_path: Path | None = None) -> RuleSet:
    custom: list[Rule] = []
    if config_path is not None:
        with config_path.open("rb") as stream:
            document = tomllib.load(stream)
        top_level_unknown = set(document) - {"rules"}
        if top_level_unknown:
            raise ValueError(f"Unknown configuration sections: {', '.join(top_level_unknown)}")
        raw_rules = document.get("rules", [])
        if not isinstance(raw_rules, list):
            raise ValueError("The 'rules' value must be an array of tables")
        custom = [_custom_rule(value) for value in raw_rules]
        ids = [rule.id for rule in custom]
        if len(ids) != len(set(ids)):
            raise ValueError("Custom rule ids must be unique")
    return RuleSet(custom + builtin_rules())


def builtin_rules() -> list[Rule]:
    categories = [
        ("pdf", "Documents/PDF/{year}", [".pdf"], "PDF document"),
        (
            "spreadsheets",
            "Documents/Spreadsheets/{year}",
            [".csv", ".ods", ".xls", ".xlsm", ".xlsx"],
            "spreadsheet or tabular document",
        ),
        (
            "presentations",
            "Documents/Presentations/{year}",
            [".key", ".odp", ".ppt", ".pptx"],
            "presentation document",
        ),
        (
            "word-processing",
            "Documents/Word Processing/{year}",
            [".doc", ".docx", ".odt", ".rtf"],
            "word-processing document",
        ),
        (
            "images",
            "Media/Images/{year}",
            [
                ".avif",
                ".bmp",
                ".gif",
                ".heic",
                ".jpeg",
                ".jpg",
                ".png",
                ".svg",
                ".tif",
                ".tiff",
                ".webp",
            ],
            "image file",
        ),
        (
            "audio",
            "Media/Audio/{year}",
            [".aac", ".flac", ".m4a", ".mp3", ".ogg", ".wav"],
            "audio file",
        ),
        (
            "video",
            "Media/Video/{year}",
            [".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm"],
            "video file",
        ),
        (
            "archives",
            "Archives/{year}",
            [".7z", ".bz2", ".gz", ".rar", ".tar", ".tgz", ".zip"],
            "compressed archive",
        ),
        (
            "data",
            "Data/{year}",
            [".feather", ".json", ".jsonl", ".parquet", ".sql", ".tsv", ".xml"],
            "structured data file",
        ),
        (
            "code",
            "Code/Snippets/{extension}",
            [
                ".c",
                ".cpp",
                ".css",
                ".go",
                ".h",
                ".html",
                ".java",
                ".js",
                ".jsx",
                ".kt",
                ".php",
                ".py",
                ".rb",
                ".rs",
                ".sh",
                ".swift",
                ".ts",
                ".tsx",
            ],
            "source-code file",
        ),
        ("ebooks", "Documents/Ebooks/{year}", [".azw", ".epub", ".mobi"], "ebook file"),
        ("text", "Documents/Text/{year}", [".log", ".md", ".tex", ".txt"], "plain-text document"),
    ]
    rules = [
        Rule(
            id="financial-records",
            destination="Finance/Records/{year}",
            priority=300,
            explanation="financial-document keyword and supported document format",
            extensions=(".csv", ".doc", ".docx", ".pdf", ".xls", ".xlsx"),
            name_contains=("bank", "budget", "invoice", "receipt", "statement", "tax"),
        ),
        Rule(
            id="research-papers",
            destination="Research/Papers/{year}",
            priority=250,
            explanation="research-paper keyword and document format",
            extensions=(".docx", ".pdf", ".tex"),
            name_contains=("article", "conference", "journal", "paper", "research"),
        ),
    ]
    rules.extend(
        Rule(
            id=rule_id,
            destination=destination,
            priority=100,
            explanation=explanation,
            extensions=tuple(extensions),
        )
        for rule_id, destination, extensions, explanation in categories
    )
    rules.append(
        Rule(
            id="fallback",
            destination="Other/{extension}",
            priority=-1,
            explanation="no more specific rule matched; grouped by extension",
            confidence="low",
        )
    )
    return rules
