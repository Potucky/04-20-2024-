import copy
from datetime import date

import pytest
import yaml
from tests.conftest import ROOT
from tests.support import open_dataset

from clinic_dq.config import load_config, validate_species_coverage
from clinic_dq.errors import DQError
from clinic_dq.loader import load_dataset


def test_as_of_date_override_moves_the_extract_gate(config):
    overridden = load_config(config.config_path, environ={"DQ_AS_OF_DATE": "2020-01-01"})
    assert overridden.as_of_date == date(2020, 1, 1)
    with open_dataset(overridden) as loaded:
        from clinic_dq.engine import run_checks

        results = run_checks(loaded.connection, overridden)
    failed = {result.check_id for result in results if not result.passed}
    assert "date.visits.not_after_as_of" in failed
    assert "date.patients.dob_not_after_as_of" in failed
    assert "row_count.patients.min" not in failed


def test_bad_as_of_date_is_rejected(config):
    with pytest.raises(DQError, match="DQ_AS_OF_DATE"):
        load_config(config.config_path, environ={"DQ_AS_OF_DATE": "June"})


def test_duplicate_check_id_is_rejected(tmp_path):
    (tmp_path / "data").symlink_to(ROOT / "data")
    (tmp_path / "sql").symlink_to(ROOT / "sql")
    source = yaml.safe_load((ROOT / "config" / "checks.yaml").read_text(encoding="utf-8"))
    source["checks"]["row_counts"].append(copy.deepcopy(source["checks"]["row_counts"][0]))
    path = tmp_path / "config" / "checks.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(source), encoding="utf-8")
    with pytest.raises(DQError, match="Duplicate check id"):
        load_config(path, environ={})


def test_unknown_dataset_is_rejected(config):
    with pytest.raises(DQError, match="dataset"):
        load_dataset(config, dataset="snowflake")


def test_unknown_mutation_is_rejected(config):
    with pytest.raises(DQError, match="Unknown mutation"):
        load_dataset(config, dataset="defects", mutations={"not_a_real_defect"})


def test_missing_extract_is_rejected(config, tmp_path):
    from dataclasses import replace

    broken = replace(
        config, clean_files={**config.clean_files, "patients": tmp_path / "missing.csv"}
    )
    with pytest.raises(DQError, match="patients"):
        load_dataset(broken, dataset="clean")


def test_species_bounds_must_cover_the_accepted_list():
    with pytest.raises(DQError, match="missing weight bounds"):
        validate_species_coverage({"dog", "cat"}, {"dog"}, {"dog"})
    with pytest.raises(DQError, match="outside the accepted list"):
        validate_species_coverage({"dog"}, {"dog", "dragon"}, {"dog"})


def test_committed_extracts_match_the_builder(repo_root):
    import subprocess
    import sys

    completed = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "build_sample_data.py"), "--check"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
