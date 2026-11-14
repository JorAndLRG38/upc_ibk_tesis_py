# Línea base del proyecto

## Propósito

Este documento registra la ejecución de la Fase 1 del plan estratégico. La línea base permite distinguir el estado comprobado del proyecto antes de iniciar nuevos cambios funcionales.

## Fecha de ejecución

- Fecha local: 14 de noviembre de 2026.
- Zona horaria: America/Lima.
- Ejecución principal de Sprint 1: 2026-11-14 01:34:34.
- Ejecución principal de Sprint 2: 2026-11-14 01:34:47 a 01:35:31 aproximadamente.
- Artefacto Sprint 2: `artifacts/sprint2/20261114T063447Z_e0fd8c67/`.

## Entorno y dependencias

- Entorno: `.venv`.
- Python: 3.12.10.
- Configuración de Sprint 2: [training/config/sprint2.yaml](../training/config/sprint2.yaml).
- Dependencias específicas: [requirements-sprint2.txt](../requirements-sprint2.txt).
- No se utilizaron credenciales de base de datos ni datos bancarios reales.

## Validaciones ejecutadas

### Suite de pruebas

Comando ejecutado:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Resultado: la suite completa terminó correctamente con código de salida 0. Se recolectaron 78 pruebas y todas fueron aprobadas. Se registraron cuatro advertencias de `FutureWarning` relacionadas con `TargetEncoder.shuffle` y `TargetEncoder.random_state` en scikit-learn 1.9.

### Sprint 1

Comando ejecutado:

```powershell
$env:RISK_PSEUDO_SALT = 'solo-prueba-local-datos-sinteticos'
& .\.venv\Scripts\python.exe -m training.run_sprint1 --source .\data\source\solicitudes_demo.csv
```

Resultado observado:

- CSV sintético generado con 5 015 filas y tasa de `default` de 9,39 %.
- Ingesta: 5 015 filas y 22 columnas.
- Preparación: 4 000 filas de desarrollo y 1 000 de prueba.
- Salida preparada: 38 columnas.
- Tiempo total reportado por Sprint 1: 2,814 segundos.

### Sprint 2

Comando ejecutado:

```powershell
$env:RISK_PSEUDO_SALT = 'solo-prueba-local-datos-sinteticos'
& .\.venv\Scripts\python.exe -m training.run_sprint2 --demo --source .\data\source\solicitudes_demo.csv
```

Resultado observado:

- Estado: `BASE_EXPERIMENTAL_HU04_HU06`.
- Folds externos ejecutados: 3.
- Variables confirmadas por Boruta: `antiguedad_negocio_meses`, `n_entidades_sbs`, `deuda_total_sbs` y `max_dias_atraso_12m`.
- Variables finales de RFECV: las mismas cuatro variables.
- RFECV utilizó `average_precision` como criterio interno de selección.
- Clases antes de SMOTE-ENN: clase 0 = 3 623; clase 1 = 377.
- Clases después de SMOTE-ENN: clase 0 = 2 101; clase 1 = 2 380.
- Filas de prueba conservadas sin remuestreo: 1 000.

## Interpretación de la línea base

La ejecución confirma que el flujo técnico de ingesta, preparación, Boruta, RFECV, partición agrupada y SMOTE-ENN funciona con datos sintéticos.

La ejecución no calcula AUC, Recall, F1-score, KS ni Brier Score. RFECV produce una curva de selección interna, pero esa curva no es una métrica de desempeño generalizable de un clasificador.

La ejecución tampoco entrena XGBoost ni genera probabilidades de incumplimiento. El artefacto `preparacion_sprint2.joblib` es un preparador de datos, no un modelo predictor.

La tesis revisada define el objetivo operativo como `default_12m`, atraso de al menos 30 días durante los 12 meses posteriores al desembolso. La salida actual contiene el indicador interno `objetivo_tesis_90_dias_validado: false`, que no coincide con esa definición y debe corregirse en una fase posterior antes de interpretar resultados como parte de la tesis.

## Artefactos principales

- Dataset sintético: `data/source/solicitudes_demo.csv`.
- Salidas de Sprint 1: `data/prepared/` y `reports/eda/`.
- Reporte Sprint 2: `artifacts/sprint2/20261114T063447Z_e0fd8c67/reporte_sprint2.json`.
- Variables Boruta: `artifacts/sprint2/20261114T063447Z_e0fd8c67/boruta_variables.csv`.
- Variables RFECV: `artifacts/sprint2/20261114T063447Z_e0fd8c67/rfecv_variables.csv`.
- Curva RFECV: `artifacts/sprint2/20261114T063447Z_e0fd8c67/rfecv_curva.csv`.
- Balance de clases: `artifacts/sprint2/20261114T063447Z_e0fd8c67/balance_clases.csv`.

## Limitaciones

- La fuente es sintética.
- El objetivo aún requiere alineación definitiva con el contrato de datos y la tesis.
- Solo se procesan variables numéricas en esta base experimental.
- No existe todavía evaluación predictiva con AUC ni validación temporal.
- No se ha confirmado ningún método denominado K2 en la tesis o en el código.

## Estado de la Fase 1

**Completada como línea base técnica y documental.** La fase no demuestra desempeño predictivo ni cumplimiento de los umbrales académicos; deja preparada la evidencia para la siguiente fase.

La alineación documental posterior se registra en la [matriz de trazabilidad](./matriz_trazabilidad.md) y las [decisiones metodológicas](./decisiones_metodologicas.md). Las menciones a 90 días en la salida del ejecutor son hechos observados de la línea base, no la definición vigente de la tesis.

**Aclaración posterior (14/11/2026):** la mención a K2 en las limitaciones anteriores describe la incertidumbre existente durante esta ejecución. El usuario confirmó después que se refería a KS, métrica de evaluación prevista en la tesis.

