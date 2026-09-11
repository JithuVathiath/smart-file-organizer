# Rule language

Custom rules use TOML and are evaluated before built-in rules. The highest priority wins; ties are resolved by rule identifier for deterministic behavior.

```toml
[[rules]]
id = "cv-and-resume"
destination = "Career/CV/{year}"
priority = 500
explanation = "CV or resume keyword in a supported document"
confidence = "high"
extensions = ["pdf", "doc", "docx"]
name_contains = ["cv", "resume"]
```

## Fields

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | Yes | Stable lowercase identifier using letters, numbers, `_`, or `-` |
| `destination` | Yes | Relative destination directory template |
| `priority` | No | Integer; default `100` |
| `explanation` | No | Human-readable reason shown in plans |
| `confidence` | No | `high`, `medium`, or `low` |
| `extensions` | No | Extensions with or without a leading dot |
| `name_contains` | No | Case-insensitive filename tokens; any token may match |
| `name_regex` | No | Case-insensitive Python regular expression |

All supplied match conditions must pass. Supported destination placeholders are `{year}`, `{extension}`, and `{stem}`. Absolute paths, `..`, unknown fields, duplicate identifiers, unknown placeholders, and invalid regular expressions are rejected.
