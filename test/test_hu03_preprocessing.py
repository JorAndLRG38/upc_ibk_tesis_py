"""Pruebas HU03 - Limpieza, imputación y codificación (CP006 a CP009, CP012, CP013)."""
import hashlib

import numpy as np
import pandas as pd
import pytest

from training.preprocessing import (DataQualityError, clean, persist_artifacts, prepare,
                                    validate_prepared)
from training.security import verify_manifest


@pytest.mark.cp("CP006")
def test_cp006_imputacion_numerica(prepared, contract):
    num_cols = [c for c in prepared.X_train.columns if c.startswith("num__")]
    assert prepared.X_train[num_cols].isna().sum().sum() == 0
    assert "num__missingindicator_ingreso_mensual" in prepared.X_train.columns
    imp = prepared.preprocessor.named_transformers_["num"].named_steps["imp"]
    assert np.all(np.isfinite(imp.statistics_))                 # medianas aprendidas en train


@pytest.mark.cp("CP007")
def test_cp007_imputacion_categorica_desconocido(prepared):
    ohe_cols = [c for c in prepared.X_train.columns if c.startswith("ohe__")]
    assert prepared.X_train[ohe_cols].isna().sum().sum() == 0
    assert any(c.endswith("_Desconocido") for c in ohe_cols)    # categoría explícita


@pytest.mark.cp("CP008")
def test_cp008_onehot_y_target_encoding(prepared):
    g = prepared.report["grupos"]
    assert "departamento" in g["target_enc"] and "actividad_economica" in g["target_enc"]
    assert "tipo_vivienda" in g["onehot"]
    ohe = prepared.X_train.filter(like="ohe__tipo_vivienda")
    assert set(np.unique(ohe.values)) <= {0.0, 1.0} and (ohe.sum(axis=1) == 1).all()
    te = prepared.X_train["te__departamento"]
    assert te.between(0, 1).all() and te.nunique() > 1


@pytest.mark.cp("CP009")
def test_cp009_validacion_final(prepared, contract):
    v = prepared.report["validacion"]
    assert v["max_pct_nulos_criticos"] < contract.prep["umbral_nulos_criticos"] * 100
    assert all(pd.api.types.is_numeric_dtype(t) for t in prepared.X_train.dtypes)
    with pytest.raises(DataQualityError):
        bad = prepared.X_train.copy(); bad.iloc[:2000, 0] = np.nan
        validate_prepared(bad, [bad.columns[0].split("__")[1]], 0.01)


@pytest.mark.cp("CP012")
def test_cp012_sin_fuga_de_informacion(prepared, ingested, contract):
    # 1) estratificación conserva la tasa de incumplimiento
    assert abs(prepared.y_train.mean() - prepared.y_test.mean()) < 0.01
    # 2) mediana aprendida == mediana SOLO del train (no del dataset completo)
    imp = prepared.preprocessor.named_transformers_["num"].named_steps["imp"]
    cleaned, _ = clean(ingested.df, contract)
    tr_idx = prepared.X_train.index
    num = prepared.report["grupos"]["numericas"]
    i = num.index("ingreso_mensual")
    X = cleaned.drop(columns=[contract.target])
    from sklearn.model_selection import train_test_split
    Xtr, _, _, _ = train_test_split(X, cleaned[contract.target], test_size=0.2,
                                    stratify=cleaned[contract.target], random_state=contract.prep["semilla"])
    assert imp.statistics_[i] == pytest.approx(Xtr["ingreso_mensual"].astype(float).median())
    assert len(tr_idx) == len(Xtr)


def test_cp012b_categoria_no_vista_en_test(prepared, ingested, contract):
    row = ingested.df.drop(columns=[contract.target]).head(1).copy()
    row["actividad_economica"] = "Actividad nunca vista"
    row["tipo_vivienda"] = "Flotante"
    out = prepared.preprocessor.transform(row)
    assert out.notna().all().all()


@pytest.mark.cp("CP013")
def test_cp013_reproducibilidad(ingested, contract):
    h = lambda p: hashlib.sha256(pd.util.hash_pandas_object(p.X_train, index=True).values).hexdigest()  # noqa: E731
    assert h(prepare(ingested.df, contract)) == h(prepare(ingested.df, contract))


def test_limpieza_duplicados_y_rangos(ingested, contract):
    cleaned, rep = clean(ingested.df, contract)
    assert rep["duplicados_eliminados"] == int(ingested.df.duplicated().sum())
    assert cleaned["edad"].dropna().between(18, 85).all()
    assert (cleaned["monto_solicitado"].dropna() >= 100).all()


def test_persistencia_y_diccionario(prepared, contract, tmp_path):
    paths = persist_artifacts(prepared, contract, tmp_path)
    for k in ("train", "test", "preprocessor"):
        assert verify_manifest(paths[k])
    dd = (tmp_path / "data_dictionary.md").read_text()
    assert "Target encoding" in dd and "One-hot" in dd and "default_12m" in dd
