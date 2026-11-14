"""Pruebas transversales: seguridad (MC4) y desempeño (MC2)."""
import time

import pandas as pd
import pytest

from generate_synthetic_dataset import generate
from training.security import SecurityError, assert_no_pii, pseudonymize_series, scan_pii


def test_scan_detecta_patrones_pii():
    df = pd.DataFrame({"doc": ["12345678"] * 10, "mail": ["a@b.pe"] * 10, "ok": ["Lima"] * 10})
    hits = scan_pii(df)
    assert "doc" in hits and "mail" in hits and "ok" not in hits
    with pytest.raises(SecurityError):
        assert_no_pii(df, [])


def test_seudonimo_depende_de_la_sal(monkeypatch):
    s = pd.Series(["CLI0000001"])
    monkeypatch.setenv("RISK_PSEUDO_SALT", "sal-A"); a = pseudonymize_series(s)[0]
    monkeypatch.setenv("RISK_PSEUDO_SALT", "sal-B"); b = pseudonymize_series(s)[0]
    assert a != b and len(a) == 16


@pytest.mark.performance
@pytest.mark.cp("CP015")
def test_cp015_desempeno_pipeline_100k(tmp_path, monkeypatch):
    from training.run_sprint1 import run
    src = tmp_path / "s.csv"; generate(100_000, seed=1).to_csv(src, index=False)
    monkeypatch.chdir(tmp_path)
    t0 = time.perf_counter(); summary = run(str(src), persist=True, eda=False)
    elapsed = time.perf_counter() - t0
    assert elapsed <= 60, f"Pipeline Sprint 1 tardó {elapsed:.1f} s (umbral 60 s)"
    assert summary["filas_entrada"] >= 100_000
