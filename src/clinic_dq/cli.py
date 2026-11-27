"""Command line entry point for a clinic data-quality run."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from clinic_dq.config import load_config
from clinic_dq.engine import run_checks
from clinic_dq.errors import DQError
from clinic_dq.loader import load_dataset
from clinic_dq.models import has_blocking_failure
from clinic_dq.report import build_report, render_text, write_reports


def main(argv: list[str] | None = None) -> None:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        code = _run(args)
    except DQError as exc:
        print(f"error: {exc}", file=sys.stderr)
        code = 2
    raise SystemExit(code)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clinic_dq",
        description="Run SQL data-quality checks for the Harbor Veterinary Clinic extract.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Load a dataset, run the catalog, and write a summary.")
    run.add_argument(
        "--dataset", choices=("clean", "defects"), help="Defaults to DQ_DATASET or clean."
    )
    run.add_argument(
        "--config",
        help="Path to config/checks.yaml. Defaults to DQ_CONFIG or ./config/checks.yaml.",
    )
    run.add_argument(
        "--report-dir",
        help="Directory for dq-summary.html, json, and txt. Defaults to DQ_REPORT_DIR or reports.",
    )
    run.add_argument(
        "--mutations",
        help="Comma-separated defect ids to apply. Defaults to every seeded defect.",
    )
    run.add_argument(
        "--expect-failures",
        action="store_true",
        help="Exit 0 when the failing checks match the seed manifest for the applied mutations.",
    )
    return parser


def _run(args: argparse.Namespace) -> int:
    dataset = args.dataset or os.environ.get("DQ_DATASET", "clean")
    report_dir = Path(args.report_dir or os.environ.get("DQ_REPORT_DIR", "reports"))
    mutations = _mutation_filter(args.mutations)
    config = load_config(args.config)
    loaded = load_dataset(config, dataset=dataset, mutations=mutations)
    try:
        results = run_checks(loaded.connection, config)
    finally:
        loaded.connection.close()

    note = ""
    exit_code = 1 if has_blocking_failure(results) else 0
    if args.expect_failures:
        actual = {result.check_id for result in results if not result.passed}
        expected = set(loaded.expected_failures)
        if actual == expected:
            note = f"Seed expectation matched ({len(expected)} failing checks)."
            exit_code = 0
        else:
            note = _mismatch(actual, expected)
            exit_code = 1

    report = build_report(
        dataset=loaded.dataset,
        as_of_date=config.as_of_date.isoformat(),
        applied_mutations=loaded.applied_mutations,
        results=results,
        note=note,
    )
    write_reports(report, report_dir)
    print(render_text(report), end="")
    return exit_code


def _mutation_filter(raw: str | None) -> set[str] | None:
    if raw is None:
        return None
    selected = {part.strip() for part in raw.split(",") if part.strip()}
    if not selected:
        raise DQError("--mutations did not include any ids.")
    return selected


def _mismatch(actual: set[str], expected: set[str]) -> str:
    lines = ["Seed expectation did not match the failing checks."]
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing:
        lines.append("Expected to fail but passed: " + ", ".join(missing))
    if unexpected:
        lines.append("Failed but not listed in the seed: " + ", ".join(unexpected))
    return " ".join(lines)
