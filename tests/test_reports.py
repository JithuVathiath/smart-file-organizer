from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from smart_file_organizer.models import OrganizationPlan
from smart_file_organizer.reports import _human_bytes, render_html, save_html


def test_html_report_contains_plan_and_escapes_content(
    tmp_path: Path, plan: OrganizationPlan
) -> None:
    plan.operations[0] = replace(plan.operations[0], explanation="<script>alert(1)</script>")
    html = render_html(plan)
    assert plan.plan_id in html
    assert "dry-run only" in html
    assert "<table>" in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    output = tmp_path / "report.html"
    save_html(plan, output)
    assert output.read_text(encoding="utf-8") == html

    save_html(plan, output, display_root="[redacted]")
    assert "Root: [redacted]" in output.read_text(encoding="utf-8")


def test_report_escapes_user_paths(plan: OrganizationPlan) -> None:
    plan.root = "/tmp/<script>"
    html = render_html(plan)
    assert "/tmp/&lt;script&gt;" in html
    assert "/tmp/<script>" not in html


def test_human_bytes() -> None:
    assert _human_bytes(12) == "12 B"
    assert _human_bytes(2048) == "2.0 KB"
    assert _human_bytes(1024**2) == "1.0 MB"
    assert _human_bytes(1024**3) == "1.0 GB"
    assert _human_bytes(1024**4) == "1.0 TB"
