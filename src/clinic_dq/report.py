"""Text, JSON, and HTML summaries of a check run."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from html import escape
from pathlib import Path

from clinic_dq.catalog import CATEGORY_ORDER
from clinic_dq.models import CheckResult, RunReport

_CATEGORY_LABELS = {
    "row_count": "Row count",
    "not_null": "Required fields",
    "uniqueness": "Uniqueness",
    "referential": "Referential integrity",
    "accepted_values": "Accepted values",
    "range": "Ranges",
    "date_logic": "Date logic",
    "consistency": "Consistency",
}


def build_report(
    *,
    dataset: str,
    as_of_date: str,
    applied_mutations: tuple[str, ...],
    results: list[CheckResult],
    note: str = "",
) -> RunReport:
    ordered = _display_order(results)
    return RunReport(
        dataset=dataset,
        as_of_date=as_of_date,
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        applied_mutations=applied_mutations,
        note=note,
        results=tuple(ordered),
    )


def render_text(report: RunReport) -> str:
    lines = [
        "Harbor Veterinary Clinic — data-quality summary",
        f"dataset: {report.dataset}",
        f"as_of_date: {report.as_of_date}",
        f"generated_at: {report.generated_at}",
        (
            f"checks: {report.total}  passed: {report.passed_count}  "
            f"failed: {len(report.failed_results)}  "
            f"errors: {report.error_count}  warnings: {report.warning_count}"
        ),
    ]
    if report.applied_mutations:
        lines.append("mutations: " + ", ".join(report.applied_mutations))
    if report.note:
        lines.append(report.note)
    lines.append("")
    for result in report.results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(
            f"{status}  {result.check_id}  [{result.severity}]  "
            f"observed={result.observed}  expected={result.expected}"
        )
        if result.passed:
            continue
        lines.append(f"      {result.description}")
        for row in result.sample:
            lines.append(f"      {row.entity_key}  {row.detail}")
        hidden = result.failed_count - len(result.sample)
        if hidden > 0:
            lines.append(f"      ... {hidden} more")
    lines.append("")
    return "\n".join(lines)


def render_json(report: RunReport) -> str:
    payload = {
        "dataset": report.dataset,
        "as_of_date": report.as_of_date,
        "generated_at": report.generated_at,
        "applied_mutations": list(report.applied_mutations),
        "note": report.note,
        "summary": {
            "total": report.total,
            "passed": report.passed_count,
            "failed": len(report.failed_results),
            "errors": report.error_count,
            "warnings": report.warning_count,
        },
        "checks": [asdict(result) for result in report.results],
    }
    return json.dumps(payload, indent=2) + "\n"


def render_html(report: RunReport) -> str:
    failed_section = _failure_section(report)
    note = f"<p class='note'>{escape(report.note)}</p>" if report.note else ""
    mutations = ""
    if report.applied_mutations:
        mutation_text = ", ".join(escape(item) for item in report.applied_mutations)
        mutations = f"<p class='meta'>Seeded mutations: {mutation_text}</p>"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Harbor Veterinary Clinic data-quality summary</title>
  <style>
    :root {{
      --bg: #f4f6f8;
      --card: #ffffff;
      --ink: #1c2430;
      --muted: #5c6b7a;
      --line: #e2e8ee;
      --pass: #0f7b4c;
      --pass-bg: #e7f6ee;
      --fail: #b42318;
      --fail-bg: #fdecea;
      --warn: #9a6700;
      --warn-bg: #fff6db;
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 15px/1.5 "Segoe UI", system-ui, sans-serif;
    }}
    .wrap {{ max-width: 1080px; margin: 0 auto; padding: 32px 20px 64px; }}
    h1 {{ font-size: 1.6rem; margin: 0 0 4px; }}
    h2 {{ font-size: 1.05rem; margin: 28px 0 8px; }}
    .meta, .note {{ color: var(--muted); margin: 4px 0; }}
    .note {{ color: var(--ink); }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
      margin: 24px 0;
    }}
    .stat {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 14px 16px;
    }}
    .stat .n {{ font-size: 1.6rem; font-weight: 650; font-variant-numeric: tabular-nums; }}
    .stat .l {{ color: var(--muted); font-size: 0.85rem; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 10px;
    }}
    th, td {{
      text-align: left;
      padding: 8px 10px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }}
    th {{
      font-size: 0.75rem;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    tr.fail td {{ background: var(--fail-bg); }}
    tr.warn td {{ background: var(--warn-bg); }}
    .pill {{
      display: inline-block;
      border-radius: 999px;
      padding: 1px 8px;
      font-size: 0.75rem;
      font-weight: 650;
    }}
    .pill.pass {{ background: var(--pass-bg); color: var(--pass); }}
    .pill.fail {{ background: var(--fail-bg); color: var(--fail); }}
    .pill.warn {{ background: var(--warn-bg); color: var(--warn); }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.86em; }}
    footer {{ color: var(--muted); font-size: 0.85rem; margin-top: 28px; }}
    @media (max-width: 720px) {{
      .stats {{ grid-template-columns: repeat(2, 1fr); }}
    }}
  </style>
</head>
<body>
  <main class="wrap">
    <header>
      <h1>Harbor Veterinary Clinic</h1>
      <p class="meta">Data-quality summary for the {escape(report.dataset)} dataset,
      as of {escape(report.as_of_date)}. Generated {escape(report.generated_at)}.</p>
      {mutations}
      {note}
    </header>
    <section class="stats">
      {_stat("Checks", str(report.total))}
      {_stat("Passed", str(report.passed_count))}
      {_stat("Errors", str(report.error_count))}
      {_stat("Warnings", str(report.warning_count))}
    </section>
    <h2>Failures</h2>
    {failed_section}
    <h2>Checks</h2>
    <table>
      <thead>
        <tr>
          <th>Result</th>
          <th>Check</th>
          <th>Category</th>
          <th>Observed</th>
          <th>Expected</th>
        </tr>
      </thead>
      <tbody>
        {"".join(_result_row(result) for result in report.results)}
      </tbody>
    </table>
    <footer>
      Portfolio demo. Fictional Harbor Veterinary Clinic data. Generated by clinic_dq.
      Error-severity failures block a run. Warnings are reported and do not block it.
    </footer>
  </main>
</body>
</html>
"""


def write_reports(report: RunReport, directory: Path) -> dict[str, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "txt": directory / "dq-summary.txt",
        "json": directory / "dq-summary.json",
        "html": directory / "dq-summary.html",
    }
    paths["txt"].write_text(render_text(report), encoding="utf-8")
    paths["json"].write_text(render_json(report), encoding="utf-8")
    paths["html"].write_text(render_html(report), encoding="utf-8")
    return paths


def _display_order(results: list[CheckResult]) -> list[CheckResult]:
    order = {category: index for index, category in enumerate(CATEGORY_ORDER)}
    indexed = list(enumerate(results))
    indexed.sort(key=lambda pair: (order.get(pair[1].category, len(order)), pair[0]))
    return [result for _, result in indexed]


def _stat(label: str, value: str) -> str:
    return (
        "<div class='stat'><div class='n'>"
        + escape(value)
        + "</div><div class='l'>"
        + escape(label)
        + "</div></div>"
    )


def _result_row(result: CheckResult) -> str:
    if result.passed:
        pill = "<span class='pill pass'>pass</span>"
        row_class = ""
    elif result.severity == "warning":
        pill = "<span class='pill warn'>warn</span>"
        row_class = " class='warn'"
    else:
        pill = "<span class='pill fail'>fail</span>"
        row_class = " class='fail'"
    category = _CATEGORY_LABELS.get(result.category, result.category)
    return (
        f"<tr{row_class}>"
        f"<td>{pill}</td>"
        f"<td><code>{escape(result.check_id)}</code><br>{escape(result.description)}</td>"
        f"<td>{escape(category)}</td>"
        f"<td>{escape(result.observed)}</td>"
        f"<td>{escape(result.expected)}</td>"
        "</tr>"
    )


def _failure_section(report: RunReport) -> str:
    if not report.failed_results:
        return "<p class='meta'>No failing checks.</p>"
    blocks: list[str] = []
    for result in report.failed_results:
        rows = "".join(
            "<tr><td><code>"
            + escape(row.entity_key)
            + "</code></td><td>"
            + escape(row.detail)
            + "</td></tr>"
            for row in result.sample
        )
        hidden = result.failed_count - len(result.sample)
        more = (
            f"<p class='meta'>Showing {len(result.sample)} of {result.failed_count} failing rows.</p>"
            if hidden > 0
            else ""
        )
        blocks.append(
            "<h3><code>"
            + escape(result.check_id)
            + "</code></h3><p>"
            + escape(result.description)
            + "</p><table><thead><tr><th>Key</th><th>Detail</th></tr></thead><tbody>"
            + rows
            + "</tbody></table>"
            + more
        )
    return "".join(blocks)
