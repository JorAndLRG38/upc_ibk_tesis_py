# Identificación temprana del riesgo de atraso — UPC

Proyecto de tesis en desarrollo para estimar, **en la originación de una
solicitud de crédito**, el riesgo de incumplimiento de microempresas
unipersonales (RUC 10). La definición operativa documentada de `default_12m`
es un atraso de al menos 30 días durante los 12 meses posteriores al
desembolso; debe confirmarse con el dataset definitivo. El proyecto busca
apoyar la gestión preventiva del riesgo en un entorno controlado de
investigación.

## Estado del desarrollo

| Componente | Estado actual |
|---|---|
| Sprint 1 | Ingesta de CSV, validación, seudonimización, análisis exploratorio y preprocesamiento. |
| Conexión SQL Server | Configuración externa, clase de conexión y comprobación de lectura con `SELECT 1`. |
| HU04: Boruta | Selección inicial implementada con `BorutaPy` y Random Forest. |
| HU05: RFECV | Refinamiento del subconjunto con validación agrupada por cliente. |
| HU06: SMOTE-ENN | Remuestreo aplicado únicamente al entrenamiento; validación y test conservan sus filas. |

El Sprint 2 es una **base experimental con variables numéricas de datos
sintéticos**. El contrato usa `default_12m`, pero el generador sintético no
demuestra que la etiqueta corresponda a pagos observados durante los 12 meses
posteriores al desembolso. Quedan pendientes la extracción desde SQL Server
hacia el pipeline, la validación temporal de la etiqueta y de las variables
disponibles en originación, el entrenamiento y evaluación de XGBoost y el
servicio de inferencia. No se dispone todavía de un modelo validado para
evaluar solicitudes reales. La tesis contempla AUC-ROC, Recall, F1-score, KS
y Brier Score; ninguna de estas métricas finales se calcula en la demo actual.

## Instalación

Entorno de referencia: **Windows y Python 3.12**. El adaptador SQL Server
requiere .NET Framework 4.7.2 o posterior y utiliza `System.Data.SqlClient`
mediante `pythonnet`. La demostración con CSV y las pruebas no necesitan
conexión a la base de datos.

Desde PowerShell:

```powershell
git clone https://github.com/JorAndLRG38/upc_ibk_tesis_py.git
cd upc_ibk_tesis_py
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements-sprint2.txt -r requirements-database.txt
Copy-Item .env.example .env
```

Configura `.env` con los valores de tu entorno según la
[guía de conexión](docs/conexion_bd.md). Este archivo es local y está excluido
de Git; `.env.example` contiene únicamente valores de referencia.

## Comprobar la conexión a SQL Server

```powershell
& .\.venv\Scripts\python.exe -m scripts.check_db_connection --json
```

Con una configuración válida y un servidor accesible, el resultado esperado
es `{"status":"OK","database":"connected"}`. Esta comprobación ejecuta
`SELECT 1`: no extrae tablas para entrenamiento ni modifica la base de datos.

## Ejecutar la demostración

Genera un CSV sintético local y establece la clave de seudonimización para
esa sesión. El valor del ejemplo es exclusivamente para datos sintéticos;
la clave utilizada con información autorizada debe mantenerse privada y
estable para conservar los mismos seudónimos.

```powershell
& .\.venv\Scripts\python.exe scripts/generate_synthetic_dataset.py --n 5000 --seed 42 --out data/source/solicitudes_demo.csv
$env:RISK_PSEUDO_SALT = 'solo-prueba-local-datos-sinteticos'

# Sprint 1: ingesta, análisis exploratorio y preparación.
& .\.venv\Scripts\python.exe -m training.run_sprint1 --source .\data\source\solicitudes_demo.csv

# Sprint 2: Boruta, RFECV y SMOTE-ENN con particiones propias.
& .\.venv\Scripts\python.exe -m training.run_sprint2 --demo --source .\data\source\solicitudes_demo.csv
```

El Sprint 1 genera datos preparados y reportes en `data/` y `reports/`.
El Sprint 2 crea una carpeta por ejecución en `artifacts/sprint2/`, con
selección de variables, conteos de clases, particiones transformadas,
preparador serializado y manifiestos de integridad. Ese preparador **no es
un clasificador XGBoost**. Los datos, logs y artefactos generados se mantienen
fuera de Git.

## Pruebas

Para presentar una prueba inicial en Google Colab, sube
[`notebooks/demo_sprint2_colab.ipynb`](notebooks/demo_sprint2_colab.ipynb).
Incluye el código necesario y genera datos sintéticos sin depender de GitHub
ni SQL Server. También está disponible el
[script autónomo](colab/demo_sprint2_colab.py) y la
[guía de ejecución](docs/demo_colab.md).

```powershell
& .\.venv\Scripts\python.exe -m pytest
```

Las pruebas usan datos sintéticos y dobles de conexión; no requieren
credenciales de una base bancaria. Incluyen validación de datos,
seudonimización, configuración de conexión, selección de variables y
controles para que el remuestreo no altere validación ni test.

## Documentación

- [Plan estratégico y fases pendientes](PLAN_ESTRATEGICO_DESARROLLO.md).
- [Matriz de trazabilidad entre tesis y repositorio](docs/matriz_trazabilidad.md).
- [Decisiones metodológicas y cuestiones abiertas](docs/decisiones_metodologicas.md).
- [Línea base verificada de la Fase 1](docs/LINEA_BASE_FASE1.md).
- [Bitácora de desarrollo](BITACORA_DESARROLLO.md).
- [Sprint 1 y trazabilidad de historias](README_SPRINT1.md).
- [Guía de ejecución del Sprint 1](docs/guia_run_sprint1.md).
- [Configuración y comprobación de SQL Server](docs/conexion_bd.md).
- [Sprint 2: implementación, evidencias y límites de HU04–HU06](docs/sprint2_hu04_hu06.md).

Los PDF de exposición, exportaciones del notebook y entregables de datos
permanecen como archivos locales; no forman parte de esta publicación del
código. El notebook se versiona sin sus salidas de ejecución.
