"""Pruebas HU02 - EDA (CP003, CP004, CP005)."""
import json

import numpy as np
import pandas as pd
import pytest

from training.eda import (consistency_report, descriptive_stats, missing_report, outlier_report,
                          run_eda, target_distribution, temporal_default_rate)


@pytest.mark.cp("CP003")
def test_cp003_estadisticas_descriptivas(ingested, contract):
    num = contract.cols_of("int", "float")
    st = descriptive_stats(ingested.df, num)
    assert {"media", "mediana", "desv_est", "q1", "q3"} <= set(st.columns)
    assert set(st.index) == set(num)
    s = ingested.df["plazo_meses"].astype(float)
    assert st.loc["plazo_meses", "media"] == pytest.approx(s.mean(), rel=1e-3)
    assert st.loc["plazo_meses", "mediana"] == pytest.approx(s.median())


@pytest.mark.cp("CP004")
def test_cp004_variable_objetivo(ingested, contract, tmp_path):
    d = target_distribution(ingested.df, contract.target)
    assert d["n_cumplidos"] + d["n_incumplidos"] == d["n_total"]
    assert 0 < d["tasa_incumplimiento"] < 0.5 and d["ratio_desbalance"] > 1
    out = run_eda(ingested.df, contract, tmp_path / "eda")
    assert (tmp_path / "eda" / "fig_target_distribucion.png").stat().st_size > 5000
    assert json.loads((tmp_path / "eda" / "eda_summary.json").read_text())["objetivo"] == d
    assert len(out["temporal"]) >= 12          # análisis temporal solicitado por el PO


@pytest.mark.cp("CP005")
def test_cp005_valores_faltantes(ingested):
    rep = missing_report(ingested.df)
    assert rep.loc["ventas_mensuales", "pct_faltantes"] == pytest.approx(
        ingested.df["ventas_mensuales"].isna().mean() * 100, abs=0.01)
    assert (rep.pct_faltantes.between(0, 100)).all()
    assert rep.pct_faltantes.is_monotonic_decreasing


def test_atipicos_iqr():
    df = pd.DataFrame({"x": list(np.ones(99)) + [1000.0]})
    rep = outlier_report(df, ["x"])
    assert rep.loc[0, "n_atipicos"] == 1


def test_consistencia_detecta_rangos_y_duplicados(ingested, contract):
    rep = consistency_report(ingested.df, contract).set_index("variable")
    assert rep.loc["edad", "n_inconsistentes"] > 0            # edad = 999 sembrada
    assert rep.loc["*", "n_inconsistentes"] >= 0


def test_temporal_por_mes(ingested, contract):
    t = temporal_default_rate(ingested.df, contract.target, "fecha_solicitud")
    assert t.tasa.between(0, 1).all() and t.n.sum() == ingested.df.fecha_solicitud.notna().sum()
