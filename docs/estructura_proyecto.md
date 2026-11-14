# Estructura del proyecto

Este documento describe el contenido versionado del repositorio después de la
limpieza. Los directorios de datos, resultados y entregables generados no se
conservan en el árbol de desarrollo: se crean localmente al ejecutar los
scripts y están excluidos por `.gitignore`.

## Vista general

| Carpeta | Propósito |
|---|---|
| `colab/` | Exportación autónoma de la demostración para Google Colab. |
| `config/` | Configuración externa de la conexión a SQL Server. |
| `database/` | Adaptador de conexión y manejo seguro de errores de SQL Server. |
| `docs/` | Guías operativas, límites conocidos y documentación del proyecto. |
| `notebooks/` | Notebooks reproducibles para EDA y demostración de Sprint 2, sin salidas guardadas. |
| `quality/` | Benchmark reproducible de rendimiento del flujo de Sprint 1. |
| `scripts/` | Puntos de entrada auxiliares: datos sintéticos, demo, exportación Colab y conexión. |
| `test/` | Pruebas automatizadas y fixtures; se conservan como evidencia técnica. |
| `training/` | Pipeline principal de ingesta, EDA, preparación, seguridad y Sprint 2. |

Los directorios locales `.venv/`, `.idea/` y `.vscode/` son herramientas del
entorno de desarrollo. No forman parte del código fuente ni de la publicación.

## Archivos de raíz

| Archivo | Contenido y uso |
|---|---|
| `.env.example` | Plantilla de variables de conexión y seguridad; no contiene secretos reales. |
| `.gitignore` | Excluye secretos, datos, resultados, caches, artefactos y archivos temporales generados. |
| `README.md` | Presenta el objetivo, estado, instalación, ejecución, demo Colab, pruebas y documentación. |
| `README_SPRINT1.md` | Trazabilidad del Sprint 1, historias, comandos de ejecución y criterios de calidad. |
| `PLAN_ESTRATEGICO_DESARROLLO.md` | Ruta de fases pendientes; las fases 0 y 1 ya están documentadas como completadas. |
| `BITACORA_DESARROLLO.md` | Historial breve de solicitudes, fechas, resultados y archivos modificados. |
| `pytest.ini` | Configuración mínima de descubrimiento y ejecución de pytest. |
| `requirements-training.txt` | Dependencias del pipeline de ingesta, EDA y preparación. |
| `requirements-sprint2.txt` | Extiende las dependencias de entrenamiento con Boruta, imbalanced-learn y componentes del Sprint 2. |
| `requirements-database.txt` | Dependencias del adaptador SQL Server y configuración tipada. |
| `requirements-colab.txt` | Dependencias mínimas para ejecutar la demo autónoma en Colab. |

## `colab/`

| Archivo | Contenido y uso |
|---|---|
| `demo_sprint2_colab.py` | Exportación autónoma comprimida y verificada con SHA-256; ejecuta la demo sin depender del repositorio original. Se regenera con `scripts/build_colab_demo.py`. |

## `config/`

| Archivo | Contenido y uso |
|---|---|
| `settings.py` | Define `DatabaseSettings` y `load_settings()` para cargar y validar la configuración externa de SQL Server sin exponer contraseñas. |

## `database/`

| Archivo | Contenido y uso |
|---|---|
| `connection.py` | Implementa `DatabaseConnection`, conexión/pool, consulta de salud `SELECT 1` y sanitización de errores. |

## `docs/`

| Archivo | Contenido y uso |
|---|---|
| `conexion_bd.md` | Configuración, ejecución y diagnóstico de la conexión a SQL Server. |
| `decisiones_metodologicas.md` | Definiciones de la tesis, distinciones metodológicas y cuestiones abiertas. |
| `demo_colab.md` | Alcance, ejecución, regeneración y limitaciones de la demo Colab. |
| `estructura_proyecto.md` | Este inventario de carpetas y archivos. |
| `guia_run_sprint1.md` | Explicación detallada del flujo de Sprint 1, entradas, salidas y errores frecuentes. |
| `LINEA_BASE_FASE1.md` | Evidencia de las pruebas y ejecuciones sintéticas de la línea base. |
| `matriz_trazabilidad.md` | Relación de objetivos, historias y capítulos de tesis con evidencia y brechas del repositorio. |
| `sprint2_hu04_hu06.md` | Diseño, ejecución, evidencias y límites de HU04 (Boruta), HU05 (RFECV) y HU06 (SMOTE-ENN). |

## `notebooks/`

| Archivo | Contenido y uso |
|---|---|
| `demo_sprint2_colab.ipynb` | Notebook para ejecutar y visualizar la prueba sintética de HU04–HU06 en Google Colab. Se versiona sin outputs. |
| `eda_report.ipynb` | Notebook reproducible del análisis exploratorio de Sprint 1 (HU02). El HTML generado se considera salida y está ignorado. |

## `quality/`

| Archivo | Contenido y uso |
|---|---|
| `benchmark.py` | Genera datos sintéticos, ejecuta ingesta/prepare y registra tiempo y memoria en un reporte local de calidad. |

## `scripts/`

| Archivo | Contenido y uso |
|---|---|
| `build_colab_demo.py` | Empaqueta la lista explícita de fuentes necesarias, genera el script autónomo y reconstruye el notebook Colab. Añade un `scripts/__init__.py` temporal dentro del bundle para sus imports; no existe como archivo fuente del repositorio. |
| `check_db_connection.py` | CLI para validar configuración y conectividad a SQL Server; devuelve estado y código de salida. |
| `demo_colab.py` | Orquesta la demo sintética, ejecuta Sprint 2 y prepara resultados descargables. |
| `generate_synthetic_dataset.py` | Genera el CSV sintético controlado usado por pruebas, notebooks y demostraciones. |

## `test/`

| Archivo | Contenido y uso |
|---|---|
| `conftest.py` | Fixtures y configuración común: contrato, datos sintéticos y rutas de prueba. |
| `test_colab_demo.py` | Verifica el bundle Colab, sus hashes, fuentes, notebook limpio y comportamiento aislado. |
| `test_database_connection.py` | Prueba configuración, conexión, errores sanitizados, cierre y CLI usando dobles; no requiere SQL Server real. |
| `test_hu01_ingestion.py` | Cubre ingesta, contrato, validación de esquema, PII y manifest de integridad. |
| `test_hu02_eda.py` | Cubre estadísticas, faltantes, atípicos, consistencia y reportes EDA. |
| `test_hu03_preprocessing.py` | Cubre limpieza, imputación, codificación, preparación y reproducibilidad. |
| `test_security_performance.py` | Cubre controles de seguridad y el umbral de rendimiento del pipeline. |
| `test_sprint2.py` | Cubre Boruta, RFECV, SMOTE-ENN, particiones por cliente, persistencia y fallos del Sprint 2. |

## `training/`

| Archivo | Contenido y uso |
|---|---|
| `common.py` | Contratos de datos, logging, timestamps, lectura de YAML y utilidades compartidas. |
| `eda.py` | Cálculo y persistencia de estadísticas, faltantes, atípicos, correlaciones y gráficos EDA. |
| `ingestion.py` | Lectura del CSV, validación contra contrato, detección de PII, seudonimización y registro de ingesta. |
| `preprocessing.py` | Limpieza, imputación, codificación, escalado, particionado y persistencia del preparador. |
| `run_sprint1.py` | CLI que encadena ingesta, EDA y preparación del Sprint 1. |
| `run_sprint2.py` | Orquesta la demo/experimento de Sprint 2 y persiste reportes, particiones y manifestes. |
| `security.py` | Detección de PII, seudonimización, hashes y manifestes de integridad. |
| `sprint2.py` | Implementa selección Boruta/RFECV y remuestreo SMOTE-ENN dentro de validación agrupada. |
| `config/data_contract.yaml` | Contrato de columnas, tipos, rangos, objetivo y campos sensibles de entrada. |
| `config/sprint2.yaml` | Parámetros de Boruta, RFECV, SMOTE-ENN, folds y semillas del Sprint 2. |

## Salidas locales no versionadas

Las ejecuciones pueden crear `data/`, `logs/`, `reports/`, `artifacts/`,
`output/`, `tmp/` y `entregables/`. Son resultados o archivos temporales, no
fuentes del proceso; se eliminaron en esta limpieza. Los tests siguen en
`test/` y pueden regenerar sus salidas temporales dentro de sus propios
directorios de prueba.
