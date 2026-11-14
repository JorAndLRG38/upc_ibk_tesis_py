"""Evidencia HU04-HU06 con algoritmos reales y controles de fuga de informacion."""
import json

import joblib
import numpy as np
import pandas as pd
import pytest
from boruta import BorutaPy
from imblearn.combine import SMOTEENN
from sklearn.feature_selection import RFECV

from training.run_sprint2 import main, persist_result, run_demo, run_experiment
from training.security import verify_manifest
from training.sprint2 import (Sprint2Config, Sprint2Error, Sprint2Preparation,
                              class_counts, grouped_splits)


@pytest.fixture(scope='module')
def numeric_data():
    rng = np.random.default_rng(17)
    y = np.r_[np.zeros(280, dtype=int), np.ones(80, dtype=int)]
    rng.shuffle(y)
    X = pd.DataFrame({'signal': 3*y+rng.normal(0, .6, len(y)),
                      'signal2': 2*y+rng.normal(0, .8, len(y)),
                      'noise': rng.normal(size=len(y)), 'noise2': rng.normal(size=len(y))})
    X.loc[::17, 'signal'] = np.nan
    return X, pd.Series(y, name='target'), pd.Series(np.arange(len(y))//2, name='cliente')


@pytest.fixture(scope='module')
def small_config():
    return Sprint2Config(seed=9, holdout_folds=3, outer_folds=2, inner_folds=2,
                         forest_trees=24, forest_max_depth=4, boruta_iterations=20,
                         smote_neighbors=3)


@pytest.fixture(scope='module')
def fitted(numeric_data, small_config):
    X, y, groups = numeric_data
    p = Sprint2Preparation(small_config)
    xr, yr = p.fit_resample(X.iloc[:300], y.iloc[:300], groups.iloc[:300])
    return p, xr, yr


def test_hu04_boruta_real_confirma_senales_y_reporta_todas(fitted):
    p, _, _ = fitted
    assert isinstance(p.boruta_, BorutaPy)
    assert {'signal', 'signal2'} <= set(p.boruta_features_)
    assert len(p.boruta_report_) == 4
    assert all(r['estado'] in {'confirmada', 'tentativa', 'rechazada'} for r in p.boruta_report_)
    assert all(r['estado'] == 'confirmada' for r in p.boruta_report_ if r['variable'] in p.boruta_features_)


def test_hu05_rfecv_real_refina_solo_confirmadas(fitted):
    p, _, _ = fitted
    assert isinstance(p.rfecv_, RFECV)
    assert set(p.selected_features_) <= set(p.boruta_features_)
    assert len(p.rfecv_curve_) >= 2
    assert 0 <= max(r['ap_media_seleccion_interna'] for r in p.rfecv_curve_) <= 1


def test_hu06_smoteenn_real_y_cambio_de_balance(fitted, numeric_data):
    p, xr, yr = fitted
    _, y, _ = numeric_data
    assert isinstance(p.sampler_, SMOTEENN)
    report = p.report_['hu06']
    assert report['antes'] == class_counts(y.iloc[:300])
    assert report['despues'] == class_counts(yr)
    assert report['generadas_smote'] > 0
    before, after = list(report['antes'].values()), list(report['despues'].values())
    assert min(after)/max(after) > min(before)/max(before)
    assert np.isfinite(xr).all().all()
    assert len(xr) == len(yr)


def test_holdout_transform_no_ajusta_ni_remuestrea(fitted, numeric_data, monkeypatch):
    p, _, _ = fitted
    X, _, _ = numeric_data
    def forbidden(*args, **kwargs):
        raise AssertionError('No debe ajustarse ningun estimador con test')
    monkeypatch.setattr(p.sampler_, 'fit_resample', forbidden)
    monkeypatch.setattr(p.boruta_, 'fit', forbidden)
    monkeypatch.setattr(p.rfecv_, 'fit', forbidden)
    monkeypatch.setattr(p.transformer_, 'fit', forbidden)
    test = X.iloc[300:].copy()
    test.loc[:, 'signal'] = 1000000.0
    before = p.transformer_.named_steps['imputer'].statistics_.copy()
    result = p.transform(test)
    assert result.index.equals(test.index)
    assert len(result) == len(test)
    np.testing.assert_array_equal(before, p.transformer_.named_steps['imputer'].statistics_)


def test_mediana_usa_solo_train(fitted, numeric_data):
    p, _, _ = fitted
    X, _, _ = numeric_data
    expected = X.iloc[:300][p.selected_features_].median().to_numpy()
    np.testing.assert_allclose(p.transformer_.named_steps['imputer'].statistics_, expected)


def test_rfecv_imputa_dentro_de_cada_fold(numeric_data, small_config, monkeypatch):
    from sklearn.impute import SimpleImputer
    X, y, groups = numeric_data
    fits = []
    original = SimpleImputer.fit
    def record(self, data, *args, **kwargs):
        fits.append(len(data))
        return original(self, data, *args, **kwargs)
    monkeypatch.setattr(SimpleImputer, 'fit', record)
    p = Sprint2Preparation(small_config)
    p.fit_resample(X, y, groups)
    inner_sizes = {len(train) for train, _ in grouped_splits(y, groups, small_config.inner_folds, small_config.seed)}
    assert inner_sizes <= set(fits)
    assert len(X) in fits


def test_separacion_por_cliente_y_clases(numeric_data):
    _, y, groups = numeric_data
    for train, valid in grouped_splits(y, groups, 3, 42):
        assert not set(groups.iloc[train]) & set(groups.iloc[valid])
        assert set(y.iloc[train]) == set(y.iloc[valid]) == {0, 1}


def test_recorrido_por_fold_excluye_test_y_persiste(numeric_data, small_config, monkeypatch, tmp_path):
    X, y, groups = numeric_data
    fits = []
    original = Sprint2Preparation.fit_resample
    def record(self, x, labels, clients):
        fits.append(set(x.index))
        return original(self, x, labels, clients)
    monkeypatch.setattr(Sprint2Preparation, 'fit_resample', record)
    result = run_experiment(X, y, groups, small_config)
    dev, test = grouped_splits(y, groups, small_config.holdout_folds, small_config.seed)[0]
    assert len(fits) == small_config.outer_folds+1
    assert all(not rows & set(X.iloc[test].index) for rows in fits)
    assert fits[-1] == set(X.iloc[dev].index)
    assert all(rows < fits[-1] for rows in fits[:-1])
    assert result.test.index.equals(X.iloc[test].index)
    pd.testing.assert_series_equal(result.test.target, y.iloc[test])
    paths = persist_result(result, tmp_path)
    assert verify_manifest(paths['preparador'])
    assert verify_manifest(paths['train_smoteenn'])
    loaded = joblib.load(paths['preparador'])
    pd.testing.assert_frame_equal(loaded.transform(X.iloc[test]), result.processor.transform(X.iloc[test]))
    report = json.loads((tmp_path/'reporte_sprint2.json').read_text(encoding='utf-8'))
    assert report['predictor_entrenado'] is False
    assert len(report['folds_externos']) == small_config.outer_folds


def test_reproducibilidad(fitted, numeric_data, small_config):
    p, xr, yr = fitted
    X, y, groups = numeric_data
    other = Sprint2Preparation(small_config)
    xx, yy = other.fit_resample(X.iloc[:300], y.iloc[:300], groups.iloc[:300])
    assert p.selected_features_ == other.selected_features_
    pd.testing.assert_frame_equal(xr, xx)
    pd.testing.assert_series_equal(yr, yy)


@pytest.mark.parametrize('problem', ['categorical', 'infinite', 'empty_column', 'one_class', 'alignment', 'few_minority'])
def test_entradas_invalidas_rechazadas(problem, numeric_data, small_config):
    X, y, groups = [a.copy() for a in numeric_data]
    if problem == 'categorical': X['cat'] = 'A'
    if problem == 'infinite': X.loc[0, 'signal'] = np.inf
    if problem == 'empty_column': X['signal'] = np.nan
    if problem == 'one_class': y[:] = 0
    if problem == 'alignment': y.index = y.index+1
    if problem == 'few_minority': y[:] = 0; y.iloc[:2] = 1
    with pytest.raises(Sprint2Error):
        Sprint2Preparation(small_config).fit_resample(X, y, groups)


def test_no_promueve_tentativas_si_boruta_no_confirma(numeric_data, small_config, monkeypatch):
    def unconfirmed(self, X, y):
        self.support_ = np.zeros(X.shape[1], dtype=bool)
        self.support_weak_ = np.ones(X.shape[1], dtype=bool)
        return self
    monkeypatch.setattr(BorutaPy, 'fit', unconfirmed)
    with pytest.raises(Sprint2Error, match='no confirmo'):
        Sprint2Preparation(small_config).fit_resample(*numeric_data)


def test_una_variable_no_finge_ejecucion_rfecv(numeric_data, small_config, monkeypatch):
    def single(self, X, y):
        self.support_ = np.array([True]+[False]*(X.shape[1]-1))
        self.support_weak_ = np.zeros(X.shape[1], dtype=bool)
        self.ranking_ = np.arange(1, X.shape[1]+1)
        return self
    monkeypatch.setattr(BorutaPy, 'fit', single)
    prep = Sprint2Preparation(small_config)
    prep.fit_resample(*numeric_data)
    assert prep.report_['hu05']['estado'] == 'NO_APLICA_UNA_VARIABLE'
    assert prep.rfecv_ is None


def test_enn_no_puede_eliminar_toda_una_clase(numeric_data, small_config, monkeypatch):
    monkeypatch.setattr(SMOTEENN, 'fit_resample', lambda self, X, y: (X[y==0], y[y==0]))
    with pytest.raises(Sprint2Error, match='elimino una clase'):
        Sprint2Preparation(small_config).fit_resample(*numeric_data)


def test_esquema_de_transformacion_obligatorio(fitted, numeric_data):
    p, _, _ = fitted
    X, _, _ = numeric_data
    with pytest.raises(Sprint2Error, match='esquema'):
        p.transform(X.iloc[:10, ::-1])


def test_cli_exige_demo_y_no_acepta_target_como_feature(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main(['--source', 'no_existe.csv'])
    assert exc.value.code == 2
    with pytest.raises(Sprint2Error, match='features numericas'):
        run_demo('no_existe.csv', Sprint2Config(features=['default_12m']), tmp_path)


@pytest.mark.parametrize('kwargs', [{'inner_folds': 1}, {'seed': -1}, {'forest_trees': True},
                                   {'boruta_percentile': 101}, {'features': ['x','x']}])
def test_configuracion_rechaza_parametros_invalidos(kwargs):
    with pytest.raises(Sprint2Error):
        Sprint2Config(**kwargs)
