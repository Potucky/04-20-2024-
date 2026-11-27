import json

from tests.support import open_dataset

from clinic_dq.engine import run_checks
from clinic_dq.models import CheckResult, FailedRow
from clinic_dq.report import build_report, render_html, write_reports


def test_clean_report_files_record_a_full_pass(config, tmp_path):
    with open_dataset(config) as loaded:
        results = run_checks(loaded.connection, config)
    report = build_report(
        dataset="clean",
        as_of_date=config.as_of_date.isoformat(),
        applied_mutations=(),
        results=results,
    )
    paths = write_reports(report, tmp_path)
    text = paths["txt"].read_text(encoding="utf-8")
    html = paths["html"].read_text(encoding="utf-8")
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))

    assert "failed: 0" in text
    assert "No failing checks." in html
    assert payload["summary"] == {
        "total": 48,
        "passed": 48,
        "failed": 0,
        "errors": 0,
        "warnings": 0,
    }
    assert payload["checks"][0]["check_id"] == "row_count.patients.min"


def test_defect_report_includes_the_failing_key(config, tmp_path):
    with open_dataset(config, dataset="defects", mutations={"orphan_visit"}) as loaded:
        results = run_checks(loaded.connection, config)
        report = build_report(
            dataset=loaded.dataset,
            as_of_date=config.as_of_date.isoformat(),
            applied_mutations=loaded.applied_mutations,
            results=results,
            note="Seed expectation matched (1 failing checks).",
        )
    html = (write_reports(report, tmp_path))["html"].read_text(encoding="utf-8")
    assert "fk.visits.patient_id" in html
    assert "PAT-404" in html
    assert "Seed expectation matched" in html


def test_html_report_escapes_sample_text(tmp_path):
    result = CheckResult(
        check_id="fk.visits.patient_id",
        category="referential",
        severity="error",
        table="visits",
        description="Every visit points at a patient",
        passed=False,
        observed="1 failing",
        expected="0 failing",
        failed_count=1,
        sample=(FailedRow("VIS-1", "<script>alert(1)</script>"),),
    )
    report = build_report(
        dataset="defects",
        as_of_date="2024-06-15",
        applied_mutations=("orphan_visit",),
        results=[result],
        note="",
    )
    html = render_html(report)
    write_reports(report, tmp_path)
    payload = json.loads((tmp_path / "dq-summary.json").read_text(encoding="utf-8"))

    assert "<script>alert" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert payload["checks"][0]["sample"][0]["detail"] == "<script>alert(1)</script>"
