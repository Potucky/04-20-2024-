import json
import os
import subprocess
import sys

import pytest
from tests.conftest import ROOT

from clinic_dq.cli import main


def test_cli_clean_exits_zero_and_writes_reports(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["run", "--dataset", "clean", "--report-dir", str(tmp_path)])
    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "failed: 0" in output
    assert (tmp_path / "dq-summary.html").is_file()
    assert (tmp_path / "dq-summary.json").is_file()
    assert (tmp_path / "dq-summary.txt").is_file()


def test_cli_defects_exit_one_without_the_expectation_flag(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main(["run", "--dataset", "defects", "--report-dir", str(tmp_path)])
    assert exc.value.code == 1


def test_cli_expect_failures_matches_the_seed(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "run",
                "--dataset",
                "defects",
                "--expect-failures",
                "--report-dir",
                str(tmp_path),
            ]
        )
    assert exc.value.code == 0
    assert "Seed expectation matched (15 failing checks)." in capsys.readouterr().out


def test_cli_one_mutation_expectation(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "run",
                "--dataset",
                "defects",
                "--mutations",
                "orphan_visit",
                "--expect-failures",
                "--report-dir",
                str(tmp_path),
            ]
        )
    assert exc.value.code == 0
    payload = json.loads((tmp_path / "dq-summary.json").read_text(encoding="utf-8"))
    failed = [item["check_id"] for item in payload["checks"] if not item["passed"]]
    assert failed == ["fk.visits.patient_id"]


def test_cli_unknown_dataset_exits_two(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["run", "--dataset", "snowflake", "--report-dir", str(tmp_path)])
    assert exc.value.code == 2
    assert "error:" in capsys.readouterr().err


def test_cli_uses_dataset_and_report_dir_from_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("DQ_DATASET", "clean")
    monkeypatch.setenv("DQ_REPORT_DIR", str(tmp_path))
    monkeypatch.delenv("DQ_AS_OF_DATE", raising=False)
    with pytest.raises(SystemExit) as exc:
        main(["run", "--config", str(ROOT / "config" / "checks.yaml")])
    assert exc.value.code == 0
    assert (tmp_path / "dq-summary.json").is_file()


def test_module_entrypoint_runs_the_clean_dataset(tmp_path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env.pop("DQ_AS_OF_DATE", None)
    env.pop("DQ_DATASET", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "clinic_dq",
            "run",
            "--dataset",
            "clean",
            "--report-dir",
            str(tmp_path),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "failed: 0" in completed.stdout
