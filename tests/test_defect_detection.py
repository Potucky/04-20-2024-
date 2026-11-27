import pytest
from tests.conftest import ROOT
from tests.support import open_dataset

from clinic_dq.config import load_config
from clinic_dq.engine import run_checks
from clinic_dq.loader import load_seed

_CONFIG = load_config(ROOT / "config" / "checks.yaml", environ={})
MUTATIONS = load_seed(_CONFIG.seed_path, known_checks=set(_CONFIG.check_ids()))


def test_seed_manifest_names_real_checks():
    assert len(MUTATIONS) >= 10
    assert len({mutation.id for mutation in MUTATIONS}) == len(MUTATIONS)


@pytest.mark.parametrize("mutation", MUTATIONS, ids=[mutation.id for mutation in MUTATIONS])
def test_seeded_mutation_fails_only_its_expected_checks(config, mutation):
    with open_dataset(config, dataset="defects", mutations={mutation.id}) as loaded:
        results = run_checks(loaded.connection, config)

    failed = [result for result in results if not result.passed]
    assert {result.check_id for result in failed} == set(mutation.expect_failed_checks)
    assert {result.severity for result in failed} == {"error"}
    blob = " ".join(f"{row.entity_key} {row.detail}" for result in failed for row in result.sample)
    for token in mutation.expect_in_sample:
        assert token in blob


def test_all_seeded_defects_fail_exactly_the_manifest(config):
    with open_dataset(config, dataset="defects") as loaded:
        results = run_checks(loaded.connection, config)
        expected = set(loaded.expected_failures)

    failed = {result.check_id for result in results if not result.passed}
    assert failed == expected
    assert len(failed) == 15
    for result in results:
        pairs = [(row.entity_key, row.detail) for row in result.sample]
        assert len(pairs) == len(set(pairs))
