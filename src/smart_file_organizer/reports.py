"""Standalone HTML previews for organization plans."""

from __future__ import annotations

from collections import Counter
from html import escape
from pathlib import Path

from .models import OrganizationPlan


def _human_bytes(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1024 or unit == "TB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{amount:.1f} TB"  # pragma: no cover


def render_html(plan: OrganizationPlan, *, display_root: str | None = None) -> str:
    counts = Counter(item.status.value for item in plan.operations)
    total_bytes = sum(item.size for item in plan.movable)
    rows = "\n".join(
        "<tr>"
        f"<td><span class='status {escape(item.status.value)}'>{escape(item.status.value)}</span></td>"
        f"<td><code>{escape(item.source)}</code></td>"
        f"<td><code>{escape(item.destination)}</code></td>"
        f"<td>{escape(item.rule_id)}</td>"
        f"<td>{escape(item.explanation)}</td>"
        f"<td>{escape(item.conflict or '—')}</td>"
        "</tr>"
        for item in plan.operations
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smart File Organizer — Plan {escape(plan.plan_id)}</title>
<style>
:root {{--ink:#172033;--muted:#667085;--paper:#f6f8fc;--card:#fff;--blue:#3457d5;--green:#067647;--amber:#b54708;}}
* {{box-sizing:border-box}} body {{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 Inter,ui-sans-serif,system-ui,sans-serif}}
main {{max-width:1180px;margin:auto;padding:52px 24px}} .eyebrow {{color:var(--blue);font-weight:750;letter-spacing:.1em;text-transform:uppercase}}
h1 {{font-size:clamp(2rem,5vw,3.7rem);line-height:1.05;margin:.35rem 0 1rem}} .subtitle {{color:var(--muted);max-width:760px;font-size:1.08rem}}
.cards {{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:34px 0}} .card {{background:var(--card);padding:20px;border-radius:14px;box-shadow:0 8px 30px #1b2b5b0c}}
.label {{color:var(--muted);font-size:.82rem;text-transform:uppercase;letter-spacing:.08em}} .value {{font-size:1.8rem;font-weight:760;margin-top:4px}}
.safety {{border-left:4px solid var(--green);background:#ecfdf3;padding:14px 18px;border-radius:8px;margin:24px 0}}
.table-wrap {{overflow:auto;background:var(--card);border-radius:14px;box-shadow:0 8px 30px #1b2b5b0c}} table {{border-collapse:collapse;width:100%;min-width:920px}}
th,td {{text-align:left;padding:14px;border-bottom:1px solid #eaecf0;vertical-align:top}} th {{font-size:.78rem;text-transform:uppercase;color:var(--muted);letter-spacing:.05em}}
code {{font-size:.84rem}} .status {{padding:4px 9px;border-radius:999px;font-size:.74rem;font-weight:700;text-transform:uppercase}}
.move {{background:#dcfae6;color:var(--green)}} .skip {{background:#f2f4f7;color:#344054}} .review {{background:#fef0c7;color:var(--amber)}}
footer {{color:var(--muted);margin-top:28px;font-size:.88rem}} @media(max-width:760px){{.cards{{grid-template-columns:repeat(2,1fr)}}}}
</style></head>
<body><main>
<div class="eyebrow">Local-first filesystem automation</div>
<h1>Organization plan</h1>
<p class="subtitle">A reviewable record of every recommended action. This report cannot change files; applying the plan requires a separate explicit confirmation.</p>
<section class="cards">
<div class="card"><div class="label">Plan ID</div><div class="value">{escape(plan.plan_id)}</div></div>
<div class="card"><div class="label">Files to move</div><div class="value">{counts["move"]}</div></div>
<div class="card"><div class="label">Skipped / review</div><div class="value">{counts["skip"] + counts["review"]}</div></div>
<div class="card"><div class="label">Planned data</div><div class="value">{_human_bytes(total_bytes)}</div></div>
</section>
<div class="safety"><strong>Safety state:</strong> dry-run only. No files were modified while producing this report.</div>
<div class="table-wrap"><table><thead><tr><th>Status</th><th>Source</th><th>Destination</th><th>Rule</th><th>Why</th><th>Conflict</th></tr></thead><tbody>{rows}</tbody></table></div>
<footer>Generated {escape(plan.created_at)} · Root: {escape(display_root or plan.root)} · Policy: {escape(plan.conflict_policy.value)}</footer>
</main></body></html>"""


def save_html(
    plan: OrganizationPlan, output_path: Path, *, display_root: str | None = None
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_html(plan, display_root=display_root), encoding="utf-8")
