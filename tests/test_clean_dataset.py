from tests.support import open_dataset

from clinic_dq.engine import run_checks
from clinic_dq.models import has_blocking_failure

CATALOG_SIZE = 48


def test_clean_dataset_passes_every_check(config):
    with open_dataset(config) as loaded:
        results = run_checks(loaded.connection, config)
        counts = {
            table: loaded.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("patients", "visits", "lab_results", "invoices")
        }

    assert [result.check_id for result in results] == list(config.check_ids())
    assert len(results) == CATALOG_SIZE
    assert [result for result in results if not result.passed] == []
    assert not has_blocking_failure(results)
    assert counts == {"patients": 24, "visits": 40, "lab_results": 28, "invoices": 34}
    warnings = [result for result in results if result.severity == "warning"]
    assert [result.check_id for result in warnings] == [
        "consistency.visits.mammal_temperature_recorded"
    ]
    assert {result.category for result in results} == {
        "row_count",
        "not_null",
        "uniqueness",
        "referential",
        "accepted_values",
        "range",
        "date_logic",
        "consistency",
    }


def test_truncated_lab_extract_fails_only_the_volume_gate(config):
    with open_dataset(config) as loaded:
        loaded.connection.execute("DELETE FROM lab_results WHERE result_id = 'LAB-028'")
        results = run_checks(loaded.connection, config)

    failed = {result.check_id for result in results if not result.passed}
    assert failed == {"row_count.lab_results.min"}


def test_missing_mammal_temperature_is_a_warning(config):
    with open_dataset(config) as loaded:
        loaded.connection.execute(
            "UPDATE visits SET temperature_c = NULL WHERE visit_id = 'VIS-001'"
        )
        results = run_checks(loaded.connection, config)

    failed = [result for result in results if not result.passed]
    assert [result.check_id for result in failed] == [
        "consistency.visits.mammal_temperature_recorded"
    ]
    assert failed[0].severity == "warning"
    assert failed[0].sample[0].entity_key == "VIS-001"
    assert not has_blocking_failure(results)


def test_sample_limit_caps_failing_rows(config):
    from dataclasses import replace
    from datetime import date

    narrowed = replace(config, as_of_date=date(2020, 1, 1), sample_limit=1)
    with open_dataset(narrowed) as loaded:
        results = run_checks(loaded.connection, narrowed)

    visit_dates = next(
        result for result in results if result.check_id == "date.visits.not_after_as_of"
    )
    assert visit_dates.failed_count > 1
    assert len(visit_dates.sample) == 1
    row_count = next(result for result in results if result.check_id == "row_count.patients.min")
    assert row_count.passed
