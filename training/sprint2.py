"""HU04-HU06: seleccion y balanceo de una particion de entrenamiento.

Acepta variables numericas sin transformar, nunca el artefacto ajustado del
Sprint 1. El llamador separa desarrollo/prueba y vuelve a ajustar esta clase
en cada fold externo. RFECV usa sus propios folds internos por cliente.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from boruta import BorutaPy
from imblearn.combine import SMOTEENN
from imblearn.over_sampling import SMOTE
from imblearn.under_sampling import EditedNearestNeighbours
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import NotFittedError
from sklearn.feature_selection import RFECV
from sklearn.impute import SimpleImputer
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

DEFAULT_CONFIG = Path(__file__).parent / 'config' / 'sprint2.yaml'


class Sprint2Error(ValueError):
    """Entrada o resultado insuficiente; nunca se inventa un subconjunto valido."""


@dataclass(frozen=True)
class Sprint2Config:
    seed: int = 42
    holdout_folds: int = 5
    outer_folds: int = 3
    inner_folds: int = 3
    forest_trees: int = 64
    forest_max_depth: int = 5
    boruta_iterations: int = 50
    boruta_percentile: int = 100
    boruta_alpha: float = .05
    rfecv_step: int = 1
    smote_neighbors: int = 5
    enn_neighbors: int = 3
    features: list[str] = field(default_factory=list)

    def __post_init__(self):
        for name in ('holdout_folds', 'outer_folds', 'inner_folds', 'forest_trees',
                     'forest_max_depth', 'boruta_iterations', 'rfecv_step',
                     'smote_neighbors', 'enn_neighbors', 'seed', 'boruta_percentile'):
            value = getattr(self, name)
            minimum = 0 if name == 'seed' else 1
            if type(value) is not int or value < minimum:
                raise Sprint2Error(f'Configuracion invalida: {name}.')
        if min(self.holdout_folds, self.outer_folds, self.inner_folds) < 2:
            raise Sprint2Error('Cada validacion cruzada necesita al menos dos folds.')
        if self.boruta_iterations < 10 or self.boruta_percentile > 100:
            raise Sprint2Error('Boruta necesita max_iter >= 10 y percentil entre 1 y 100.')
        if isinstance(self.boruta_alpha, bool) or not 0 < self.boruta_alpha < 1:
            raise Sprint2Error('boruta_alpha debe estar entre 0 y 1.')
        if (not isinstance(self.features, list)
                or any(not isinstance(c, str) or not c.strip() for c in self.features)
                or len(set(self.features)) != len(self.features)):
            raise Sprint2Error('features debe ser una lista de nombres distintos.')

    @classmethod
    def load(cls, path: str | Path = DEFAULT_CONFIG) -> 'Sprint2Config':
        with Path(path).open(encoding='utf-8') as handle:
            raw = yaml.safe_load(handle)
        if not isinstance(raw, dict):
            raise Sprint2Error('La configuracion YAML debe ser un objeto.')
        try:
            return cls(**raw)
        except TypeError as exc:
            raise Sprint2Error('Campos desconocidos o tipos invalidos en la configuracion.') from exc


def class_counts(y) -> dict[str, int]:
    counts = pd.Series(np.asarray(y)).value_counts()
    return {str(k): int(counts.get(k, 0)) for k in (0, 1)}


def numeric_frame(X: pd.DataFrame, *, training: bool) -> pd.DataFrame:
    if not isinstance(X, pd.DataFrame) or X.empty or not X.index.is_unique:
        raise Sprint2Error('Se requiere un DataFrame no vacio con indice unico.')
    if not X.columns.is_unique or not all(isinstance(c, str) for c in X.columns):
        raise Sprint2Error('Los nombres de variables deben ser cadenas distintas.')
    if any(not pd.api.types.is_numeric_dtype(t) or pd.api.types.is_bool_dtype(t) for t in X.dtypes):
        raise Sprint2Error('Esta base acepta solo variables numericas; no categorias ni booleanos.')
    result = X.astype('float64')
    if np.isinf(result.to_numpy()).any():
        raise Sprint2Error('Hay valores infinitos en las variables.')
    if training and result.isna().all().any():
        raise Sprint2Error('Hay variables completamente vacias en entrenamiento.')
    return result


def validate_labels(y: pd.Series, groups: pd.Series) -> None:
    if not isinstance(y, pd.Series) or not isinstance(groups, pd.Series):
        raise Sprint2Error('Las etiquetas y grupos deben ser Series alineadas.')
    if not y.index.equals(groups.index) or y.isna().any() or groups.isna().any():
        raise Sprint2Error('Etiquetas/grupos ausentes o desalineados.')
    if set(y.unique()) != {0, 1}:
        raise Sprint2Error('Se requieren ambas clases binarias 0 y 1.')


def grouped_splits(y: pd.Series, groups: pd.Series, folds: int, seed: int):
    """Rechaza folds sin ambas clases y mantiene clientes separados."""
    validate_labels(y, groups)
    if y.value_counts().min() < folds or groups.nunique() < folds:
        raise Sprint2Error('Muestras o clientes insuficientes para los folds solicitados.')
    splitter = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed)
    splits = list(splitter.split(np.zeros((len(y), 1)), y, groups))
    for train, valid in splits:
        if set(y.iloc[train]) != {0, 1} or set(y.iloc[valid]) != {0, 1}:
            raise Sprint2Error('Un fold no contiene ambas clases; revise datos o numero de folds.')
        if set(groups.iloc[train]) & set(groups.iloc[valid]):
            raise Sprint2Error('Un cliente aparece en entrenamiento y validacion.')
    return splits


class Sprint2Preparation:
    """Ajustar solo con train; transform aplica el mismo esquema sin remuestrear.

    No es un clasificador de clientes. Los bosques internos son estimadores
    auxiliares de seleccion; el modelo XGBoost corresponde a HU07.
    """

    def __init__(self, config: Sprint2Config | None = None):
        self.config = config

    def _forest(self):
        cfg = self.config or Sprint2Config()
        return RandomForestClassifier(n_estimators=cfg.forest_trees,
                                      max_depth=cfg.forest_max_depth,
                                      class_weight='balanced', random_state=cfg.seed, n_jobs=1)

    def fit_resample(self, X: pd.DataFrame, y: pd.Series, groups: pd.Series):
        """HU04 -> HU05 -> HU06; solo esta llamada recibe etiquetas de train."""
        self.__dict__.pop('is_fitted_', None)
        cfg = self.config or Sprint2Config()
        X = numeric_frame(X, training=True)
        validate_labels(y, groups)
        if not X.index.equals(y.index):
            raise Sprint2Error('Variables y etiquetas desalineadas.')
        if y.value_counts().min() <= cfg.smote_neighbors:
            raise Sprint2Error('HU06: la clase minoritaria necesita mas filas que smote_neighbors.')
        inner = grouped_splits(y, groups, cfg.inner_folds, cfg.seed)
        self.feature_names_in_ = np.asarray(X.columns, dtype=object)
        self.n_features_in_ = X.shape[1]

        # HU04: no se incorporan tentativas como si fueran confirmadas.
        self.boruta_imputer_ = SimpleImputer(strategy='median', keep_empty_features=True)
        boruta_input = self.boruta_imputer_.fit_transform(X)
        self.boruta_ = BorutaPy(self._forest(), n_estimators=cfg.forest_trees,
                               max_iter=cfg.boruta_iterations, perc=cfg.boruta_percentile,
                               alpha=cfg.boruta_alpha, random_state=cfg.seed, verbose=0)
        self.boruta_.fit(boruta_input, y.to_numpy(dtype=int))
        self.boruta_features_ = X.columns[self.boruta_.support_].tolist()
        if not self.boruta_features_:
            raise Sprint2Error('HU04: Boruta no confirmo variables. Revise datos/iteraciones; '
                               'las variables tentativas no se aceptan automaticamente.')
        self.boruta_report_ = [
            {'variable': name, 'estado': ('confirmada' if self.boruta_.support_[i]
                                         else 'tentativa' if self.boruta_.support_weak_[i] else 'rechazada'),
             'ranking': int(self.boruta_.ranking_[i])}
            for i, name in enumerate(X.columns)
        ]

        # HU05: RFECV ve numericas crudas. La mediana se ajusta por fold interno.
        # Sus scores sirven para elegir el subconjunto, no para medir generalizacion.
        X_boruta = X[self.boruta_features_]
        self.rfecv_ = None
        if X_boruta.shape[1] == 1:
            self.selected_features_ = self.boruta_features_.copy()
            rfecv_status = 'NO_APLICA_UNA_VARIABLE'
            self.rfecv_curve_ = []
            self.rfecv_ranking_ = [{'variable': self.selected_features_[0], 'seleccionada': True, 'ranking': 1}]
        else:
            estimator = Pipeline([('imputer', SimpleImputer(strategy='median', keep_empty_features=True)),
                                  ('model', self._forest())])
            self.rfecv_ = RFECV(estimator=estimator, step=cfg.rfecv_step, min_features_to_select=1,
                                cv=inner, scoring='average_precision', n_jobs=1,
                                importance_getter='named_steps.model.feature_importances_')
            self.rfecv_.fit(X_boruta, y)
            self.selected_features_ = X_boruta.columns[self.rfecv_.support_].tolist()
            results = self.rfecv_.cv_results_
            self.rfecv_curve_ = [
                {'n_variables': int(n), 'ap_media_seleccion_interna': float(m), 'ap_desv': float(s)}
                for n, m, s in zip(results['n_features'], results['mean_test_score'], results['std_test_score'])
            ]
            self.rfecv_ranking_ = [
                {'variable': name, 'seleccionada': bool(self.rfecv_.support_[i]),
                 'ranking': int(self.rfecv_.ranking_[i])}
                for i, name in enumerate(self.boruta_features_)
            ]
            rfecv_status = 'EJECUTADO'

        # HU06: escala aprendida SOLO con train para distancias comparables.
        self.transformer_ = Pipeline([('imputer', SimpleImputer(strategy='median', keep_empty_features=True)),
                                      ('scale', StandardScaler())])
        selected = self.transformer_.fit_transform(X[self.selected_features_])
        self.sampler_ = SMOTEENN(
            random_state=cfg.seed,
            smote=SMOTE(random_state=cfg.seed, k_neighbors=cfg.smote_neighbors),
            enn=EditedNearestNeighbours(n_neighbors=cfg.enn_neighbors, sampling_strategy='all', n_jobs=1),
            n_jobs=1)
        xr, yr = self.sampler_.fit_resample(selected, y.to_numpy(dtype=int))
        if set(np.unique(yr)) != {0, 1} or not np.isfinite(xr).all():
            raise Sprint2Error('HU06: ENN elimino una clase o produjo una salida invalida.')
        generated = sum(int(n) for n in self.sampler_.smote_.sampling_strategy_.values())
        self.report_ = {
            'hu04': {'estado': 'EJECUTADO', 'confirmadas': self.boruta_features_,
                     'variables': self.boruta_report_},
            'hu05': {'estado': rfecv_status, 'seleccionadas': self.selected_features_,
                     'ranking': self.rfecv_ranking_, 'curva': self.rfecv_curve_,
                     'metrica_interna': 'average_precision',
                     'nota': 'Criterio interno condicionado por Boruta; no es desempeno independiente.'},
            'hu06': {'estado': 'EJECUTADO', 'antes': class_counts(y), 'despues': class_counts(yr),
                     'generadas_smote': generated, 'eliminadas_enn': len(y) + generated - len(yr),
                     'espacio': 'numerico, mediana y StandardScaler ajustados solo con train'},
            'train_filas': len(X), 'train_clientes': int(groups.nunique()),
            'configuracion': asdict(cfg),
        }
        self.is_fitted_ = True
        return (pd.DataFrame(xr, columns=self.selected_features_),
                pd.Series(yr, name=y.name, dtype='int64'))

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Sin etiquetas, ajuste ni SMOTE: conserva filas e indice de validacion/test."""
        if not getattr(self, 'is_fitted_', False):
            raise NotFittedError('Ejecute fit_resample solo con entrenamiento antes de transform.')
        X = numeric_frame(X, training=False)
        if list(X.columns) != self.feature_names_in_.tolist():
            raise Sprint2Error('El esquema/orden de variables difiere del entrenamiento.')
        values = self.transformer_.transform(X[self.selected_features_])
        return pd.DataFrame(values, columns=self.selected_features_, index=X.index)
