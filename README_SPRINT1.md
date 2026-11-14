# Sprint 1: Preparación del dataset analítico (EP01)

La base experimental de **HU04 (Boruta), HU05 (RFECV) y HU06 (SMOTE-ENN)**
se ejecuta por separado con `python -m training.run_sprint2 --demo --source
data/source/solicitudes_demo.csv`. Consultar [la guía del Sprint 2](docs/sprint2_hu04_hu06.md)
y `requirements-sprint2.txt`. Usa variables numéricas del CSV sintético; la
integración SQL, el objetivo de 90 días y el entrenamiento XGBoost siguen pendientes.

Incremento del Sprint 1 del proyecto *Modelo predictivo basado en XGBoost para la identificación
temprana del riesgo de incumplimiento en créditos otorgados a microempresas unipersonales*.
Diseñado para copiarse dentro del repositorio `app-upc-risk-validator-service` (carpetas `training/`,
`test/`, `notebooks/`, `scripts/`, `quality/`).

## Instalación

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-training.txt
export RISK_PSEUDO_SALT="<sal-secreta-del-equipo>"     # Windows: $env:RISK_PSEUDO_SALT="..."
```

> La sal de seudonimización NO se versiona en Git (ISO/IEC 27001:2022, control 8.24).

## Ejecución

```bash
# Solo para pruebas: dataset sintético con defectos de calidad controlados
python scripts/generate_synthetic_dataset.py --n 100000 --out data/source/solicitudes.csv

python -m training.ingestion --source data/source/solicitudes.csv        # HU01
jupyter nbconvert --to html --execute notebooks/eda_report.ipynb          # HU02
python -m training.preprocessing --input data/raw/dataset_base_<fecha>.parquet   # HU03

python -m training.run_sprint1 --source data/source/solicitudes.csv      # HU01 + HU02 + HU03
python -m pytest --cov=training --cov-report=term-missing                # pruebas
python quality/benchmark.py                                               # MC2 y MC3
```

## Adaptar al dataset real (Plan A) o al dataset de Jorge (Plan B)

1. Editar `training/config/data_contract.yaml`: nombres de columnas, tipos, rangos, columnas PII.
2. Verificar la definición de la variable objetivo (`default_12m`, atraso >= 30 días a 12 meses).
3. Ejecutar `pytest`: las pruebas usan el generador sintético y no dependen del dataset real.

## Trazabilidad ticket a código

| HU | Ticket | Implementación |
|---|---|---|
| HU01 | TK-01.1 Configurar conexión a la fuente | `config/data_contract.yaml`, `ingestion._read_source` |
| HU01 | TK-01.2 Script de ingesta | `ingestion.ingest`, CLI `python -m training.ingestion` |
| HU01 | TK-01.3 Validar filas, columnas y tipos | `ingestion.validate_schema` |
| HU01 | TK-01.4 Log de ingesta y versionado | `logs/ingestion_log.jsonl`, `security.write_manifest` |
| HU02 | TK-02.1 Estadísticas descriptivas | `eda.descriptive_stats` |
| HU02 | TK-02.2 Variable objetivo | `eda.target_distribution`, `eda.temporal_default_rate` |
| HU02 | TK-02.3 Atípicos y faltantes | `eda.missing_report`, `eda.outlier_report`, `eda.consistency_report` |
| HU02 | TK-02.4 Correlaciones y visualizaciones | `eda.correlation_matrix`, `eda.plot_*` |
| HU02 | TK-02.5 Reporte EDA en notebook | `notebooks/eda_report.ipynb` |
| HU03 | TK-03.1 Estrategia de imputación | `preprocessing.IMPUTATION_STRATEGY` |
| HU03 | TK-03.2 Imputación | `preprocessing.build_preprocessor` (mediana + indicador, "Desconocido") |
| HU03 | TK-03.3 Codificación one-hot y target | `preprocessing.build_preprocessor` (`OneHotEncoder`, `TargetEncoder`) |
| HU03 | TK-03.4 Validar nulos en columnas críticas | `preprocessing.validate_prepared` |
| HU03 | TK-03.5 Versionar y documentar | `preprocessing.persist_artifacts`, `data_dictionary.md` |

## Casos de prueba automatizados

| CP | Prueba |
|---|---|
| CP001 | `test_cp001_ingesta_exitosa` |
| CP002 | `test_cp002_fuente_no_disponible`, `test_cp002b_archivo_vacio` |
| CP003 | `test_cp003_estadisticas_descriptivas` |
| CP004 | `test_cp004_variable_objetivo` (+ revisión visual manual del gráfico) |
| CP005 | `test_cp005_valores_faltantes` |
| CP006 | `test_cp006_imputacion_numerica` |
| CP007 | `test_cp007_imputacion_categorica_desconocido` |
| CP008 | `test_cp008_onehot_y_target_encoding` |
| CP009 | `test_cp009_validacion_final` |
| CP010 | `test_cp010_*` (contrato de datos) |
| CP011 | `test_cp011_pii_eliminada_y_seudonimizada` |
| CP012 | `test_cp012_sin_fuga_de_informacion`, `test_cp012b_categoria_no_vista_en_test` |
| CP013 | `test_cp013_reproducibilidad` |
| CP014 | `test_cp014_integridad_manifest` |
| CP015 | `test_cp015_desempeno_pipeline_100k` |

## Decisiones técnicas

- La partición estratificada 80/20 ocurre **antes** de ajustar imputadores y codificadores para evitar
  fuga de información; SMOTE-ENN (Sprint 2) se aplicará solo al entrenamiento.
- `TargetEncoder` de scikit-learn usa validación cruzada interna (cv=5) para no filtrar la variable objetivo.
- Los datos (`data/`), logs y artefactos no se versionan en Git (ver `.gitignore`); se versionan
  mediante manifiestos SHA-256. Si se requiere versionado de datos, se recomienda DVC.
