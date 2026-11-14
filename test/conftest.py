import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from generate_synthetic_dataset import generate  # noqa: E402
from training.common import load_contract  # noqa: E402


@pytest.fixture(scope="session")
def contract():
    return load_contract()


@pytest.fixture(scope="session")
def raw_df():
    return generate(5000, seed=7)


@pytest.fixture
def source_csv(tmp_path, raw_df):
    p = tmp_path / "solicitudes.csv"
    raw_df.to_csv(p, index=False)
    return p


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture(scope="session")
def ingested(raw_df, contract, tmp_path_factory):
    from training.ingestion import ingest
    d = tmp_path_factory.mktemp("ing")
    p = d / "src.csv"
    raw_df.to_csv(p, index=False)
    return ingest(p, contract, out_dir=d / "raw", log_path=d / "log.jsonl")


@pytest.fixture(scope="session")
def prepared(ingested, contract):
    from training.preprocessing import prepare
    return prepare(ingested.df, contract)


def pytest_configure(config):
    config.addinivalue_line("markers", "cp(id): caso de prueba documentado en el Sprint 1")
    config.addinivalue_line("markers", "performance: prueba de desempeño (MC2)")
