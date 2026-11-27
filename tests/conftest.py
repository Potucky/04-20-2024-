from pathlib import Path

import pytest

from clinic_dq.config import Config, load_config

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def repo_root() -> Path:
    return ROOT


@pytest.fixture
def config() -> Config:
    # Ignore ambient DQ_* variables so the suite stays tied to the committed catalog.
    return load_config(ROOT / "config" / "checks.yaml", environ={})
