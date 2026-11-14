"""Ejecutor HU04-HU06 de laboratorio. No consulta SQL ni entrena XGBoost."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import sys
import uuid

import joblib
import pandas as pd

from training.common import get_logger, load_contract, utc_now
from training.ingestion import DataSourceUnavailableError, SchemaValidationError, ingest
from training.preprocessing import clean
from training.security import write_manifest
from training.sprint2 import (DEFAULT_CONFIG, Sprint2Config, Sprint2Error,
                              Sprint2Preparation, class_counts, grouped_splits, numeric_frame)

log = get_logger('sprint2')


@dataclass
class Sprint2Result:
    processor: Sprint2Preparation
    train_original: pd.DataFrame
    train_resampled: pd.DataFrame
    test: pd.DataFrame
    report: dict


def run_experiment(X: pd.DataFrame, y: pd.Series, groups: pd.Series,
                   config: Sprint2Config) -> Sprint2Result:
    """Recibe variables crudas. El test nunca participa en ajustes ni remuestreo.

    Los folds externos demuestran el recorrido completo por particion; no
    generan metricas predictivas porque HU07 no forma parte de este incremento.
    """
    X = numeric_frame(X, training=True)
    if not isinstance(y, pd.Series) or not isinstance(y.name, str) or not y.name:
        raise Sprint2Error('La etiqueta debe ser una Series con nombre de columna.')
    if not X.index.equals(y.index) or y.name in X.columns:
        raise Sprint2Error('Variables desalineadas o variable objetivo incluida en X.')
    dev, test = grouped_splits(y, groups, config.holdout_folds, config.seed)[0]
    X_dev, y_dev, g_dev = X.iloc[dev], y.iloc[dev], groups.iloc[dev]
    fold_reports = []
    for number, (train, valid) in enumerate(
            grouped_splits(y_dev, g_dev, config.outer_folds, config.seed), 1):
        log.info('Fold externo %s/%s: Boruta -> RFECV -> SMOTE-ENN', number, config.outer_folds)
        prep = Sprint2Preparation(config)
        prep.fit_resample(X_dev.iloc[train], y_dev.iloc[train], g_dev.iloc[train])
        validation = prep.transform(X_dev.iloc[valid])
        fold_reports.append({
            'fold': number, **prep.report_, 'validacion_filas': len(validation),
            'validacion_clientes': int(g_dev.iloc[valid].nunique()),
            'validacion_clases_sin_remuestreo': class_counts(y_dev.iloc[valid]),
            'clientes_compartidos': 0,
        })
    log.info('Ajuste final solo sobre desarrollo; test reservado sin remuestreo')
    final = Sprint2Preparation(config)
    xr, yr = final.fit_resample(X_dev, y_dev, g_dev)
    train_output = final.transform(X_dev).assign(**{y.name: y_dev.to_numpy()})
    test_output = final.transform(X.iloc[test]).assign(**{y.name: y.iloc[test].to_numpy()})
    report = {
        'estado': 'BASE_EXPERIMENTAL_HU04_HU06', 'fecha_utc': utc_now(),
        'objetivo_columna': y.name, 'predictor_entrenado': False,
        'particion': {'metodo': 'StratifiedGroupKFold por cliente; no es validacion temporal',
                      'semilla': config.seed, 'filas_desarrollo': len(dev), 'filas_test': len(test),
                      'clientes_compartidos': 0, 'clases_test_sin_remuestreo': class_counts(y.iloc[test])},
        'folds_externos': fold_reports, 'ajuste_final': final.report_,
        'limitaciones': [
            'Esta etapa selecciona y remuestrea: no genera probabilidades de atraso.',
            'Solo variables numericas; categorias/booleanos excluidos de esta base.',
            'SMOTE interpola el espacio numerico; no crea clientes ni pagos reales.',
            'La curva RFECV es un criterio interno de seleccion, no una metrica de generalizacion.',
            'Falta entrenamiento HU07, baseline sin remuestreo, calibracion y prueba temporal.',
        ],
        'versiones': {p: version(p) for p in ['Boruta', 'imbalanced-learn', 'scikit-learn', 'numpy', 'pandas']},
    }
    return Sprint2Result(final, train_output, xr.assign(**{y.name: yr.to_numpy()}), test_output, report)


def persist_result(result: Sprint2Result, destination: Path) -> dict[str, str]:
    paths = {}
    for name, frame in [('train_sin_remuestreo', result.train_original),
                        ('train_smoteenn', result.train_resampled), ('test_sin_remuestreo', result.test)]:
        path = destination / f'{name}.parquet'
        frame.to_parquet(path, index=False)
        write_manifest(path, {'filas': len(frame), 'columnas': len(frame.columns), 'fecha_utc': utc_now()})
        paths[name] = str(path)
    processor = destination / 'preparacion_sprint2.joblib'
    joblib.dump(result.processor, processor)
    write_manifest(processor, {'tipo': 'preparacion_HU04_HU06_no_clasificador', 'fecha_utc': utc_now()})
    pd.DataFrame(result.processor.boruta_report_).to_csv(destination / 'boruta_variables.csv', index=False)
    pd.DataFrame(result.processor.rfecv_ranking_).to_csv(destination / 'rfecv_variables.csv', index=False)
    pd.DataFrame(result.processor.rfecv_curve_, columns=[
        'n_variables', 'ap_media_seleccion_interna', 'ap_desv']).to_csv(destination / 'rfecv_curva.csv', index=False)
    balance = result.report['ajuste_final']['hu06']
    pd.DataFrame([{'clase': k, 'antes': balance['antes'][k], 'despues': balance['despues'][k]}
                  for k in ('0', '1')]).to_csv(destination / 'balance_clases.csv', index=False)
    paths['preparador'] = str(processor)
    paths['reporte'] = str(destination / 'reporte_sprint2.json')
    result.report['archivos'] = paths
    (destination / 'reporte_sprint2.json').write_text(
        json.dumps(result.report, indent=2, ensure_ascii=False), encoding='utf-8')
    selected = ', '.join(result.processor.selected_features_)
    md = f'''# HU04-HU06: resultado de laboratorio

**Base experimental. No es validacion del atraso en 90 dias.**

Origen declarado: {result.report.get('origen', 'entrada numerica de prueba')}.
Objetivo: {result.report['objetivo_columna']}.
Definicion: {result.report.get('objetivo_descripcion', 'ver contrato del llamador')}.

- Boruta: {len(result.processor.boruta_features_)} variables confirmadas.
- RFECV: {result.report['ajuste_final']['hu05']['estado']}; {len(result.processor.selected_features_)} variables finales.
- Subconjunto: {selected}.
- SMOTE-ENN: antes {balance['antes']}; despues {balance['despues']}.
- Test reservado: {len(result.test)} filas, sin remuestrear.
- Folds externos ejecutados: {len(result.report['folds_externos'])}.

La curva RFECV usa Average Precision para seleccionar; no representa la calidad
predictiva final de un modelo. ENN puede dejar clases de distinto tamano.
Cada fold externo vuelve a ajustar Boruta, RFECV, imputacion, escala y remuestreo.
No se reutiliza el preprocesador del Sprint 1 para la validacion interna.

El archivo preparacion_sprint2.joblib es un preparador, no un predictor de clientes.
La conexion SQL, el dataset con snapshots y etiqueta de 90 dias, el entrenamiento
XGBoost y la validacion temporal permanecen fuera de esta ejecucion.
'''
    (destination / 'LEER_RESULTADOS.md').write_text(md, encoding='utf-8')
    return paths


def run_demo(source: str | Path, config: Sprint2Config, output_root: str | Path) -> dict:
    contract = load_contract()
    allowed = set(contract.cols_of('int', 'float'))
    if not config.features or not set(config.features) <= allowed:
        raise Sprint2Error('Configure solo features numericas del contrato, sin target ni identificadores.')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8]
    destination = Path(output_root).resolve() / run_id
    destination.mkdir(parents=True, exist_ok=False)
    try:
        ingested = ingest(source, contract, persist=False, log_path=destination / 'ingesta.jsonl')
        data, cleaning = clean(ingested.df, contract)
        if data.cliente_id.isna().any():
            raise Sprint2Error('Faltan identificadores para separar clientes.')
        result = run_experiment(data[config.features], data[contract.target].astype(int),
                                data.cliente_id, config)
        result.report.update(
            origen='CSV_SINTETICO_DE_LABORATORIO_DECLARADO_CON_DEMO',
            objetivo_descripcion=contract.raw['objetivo']['descripcion'],
            objetivo_tesis_90_dias_validado=False,
            fuente_sha256=ingested.report['sha256_fuente'],
            contrato_version=contract.raw['dataset']['version_contrato'], limpieza=cleaning,
            configuracion_sha256=hashlib.sha256(json.dumps(asdict(config), sort_keys=True).encode()).hexdigest(),
            variables_excluidas=[c for c in contract.columns if c not in config.features],
        )
        persist_result(result, destination)
    except Exception as exc:
        # No deja un reporte de exito si alguna etapa falla.
        (destination / 'ERROR.json').write_text(json.dumps(
            {'estado': 'ERROR', 'tipo': type(exc).__name__, 'fecha_utc': utc_now()}), encoding='utf-8')
        raise
    return {'estado': result.report['estado'], 'directorio': str(destination),
            'boruta_confirmadas': result.processor.boruta_features_,
            'rfecv_seleccionadas': result.processor.selected_features_,
            'clases_entrenamiento': result.processor.report_['hu06'],
            'filas_test_sin_remuestreo': len(result.test),
            'objetivo_tesis_90_dias_validado': False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Base experimental HU04-HU06; no entrena XGBoost')
    parser.add_argument('--source', required=True, type=Path, help='CSV sintetico de laboratorio del Sprint 1')
    parser.add_argument('--demo', action='store_true', required=True,
                        help='Declara que la fuente es sintetica; no usar con registros bancarios reales')
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--output-root', type=Path, default=Path('artifacts/sprint2'))
    args = parser.parse_args(argv)
    try:
        summary = run_demo(args.source, Sprint2Config.load(args.config), args.output_root)
    except (Sprint2Error, SchemaValidationError, DataSourceUnavailableError, OSError) as exc:
        print(f'ERROR Sprint 2: {exc}', file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
