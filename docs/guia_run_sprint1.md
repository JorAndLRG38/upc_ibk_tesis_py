# Guía de ejecución y explicación de `run_sprint1.py`

Este documento describe el código existente en `training/run_sprint1.py` y los módulos que utiliza. Revisión: 16 de octubre de 2026.

## 1. ¿Qué hace este programa?

Prepara un archivo de datos para un futuro entrenamiento de un modelo. Coordina tres etapas en orden:

```text
Archivo de entrada (CSV, Parquet o Excel)
    → HU01: cargar, proteger identificadores y validar la estructura
    → HU02: analizar los datos y generar tablas y gráficos
    → HU03: limpiar, separar y transformar los datos
    → guardar archivos preparados y registrar un resumen
```

HU significa «historia de usuario»: una funcionalidad del Sprint. El script actúa como coordinador; los detalles están en otros archivos.

**Este Sprint no entrena XGBoost ni calcula predicciones.** Deja preparados los datos y el proceso de transformación que se usarían en una etapa posterior.

## 2. Cómo ejecutarlo en Windows

### Preparar Python y las dependencias

La revisión encontró que PyCharm no tiene un intérprete configurado para este proyecto. El proyecto indica Python 3.12. Si todavía no tienes esa versión instalada, instálala antes de continuar.

Abre una terminal **PowerShell** y ejecuta estos comandos, uno por uno. Continúa al siguiente cuando el anterior termine correctamente:

```powershell
Set-Location 'C:\Users\jorAN\Downloads\codigo'
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements-training.txt
```

El primer comando entra al proyecto. El segundo crea un entorno aislado de Python en `.venv`. El tercero instala las bibliotecas del proyecto. La instalación requiere acceso a Internet o a un repositorio local de paquetes.

Los siguientes comandos utilizan directamente el Python de ese entorno; no necesitas activar `.venv` ni cambiar la política de ejecución de PowerShell. Si `.venv` ya existe y es el entorno que utilizas, omite su creación.

### Hacer una primera ejecución con datos sintéticos

No se encontró una carpeta `data/` ni un archivo de entrada en esta copia del proyecto. El generador incluido permite hacer una prueba técnica con datos inventados; no representa registros bancarios reales ni una validación de la tesis.

```powershell
# Valor público exclusivamente para la prueba con datos sintéticos.
$env:RISK_PSEUDO_SALT = 'solo-prueba-local-datos-sinteticos'

# Crear una muestra de prueba; el generador añade algunos duplicados.
& .\.venv\Scripts\python.exe scripts/generate_synthetic_dataset.py --n 5000 --out data/source/solicitudes_demo.csv

# Ejecutar las tres etapas.
& .\.venv\Scripts\python.exe -m training.run_sprint1 --source data/source/solicitudes_demo.csv
```

`RISK_PSEUDO_SALT` es la clave que usa el programa para reemplazar los identificadores de clientes por códigos. El valor de ejemplo es solo para datos sintéticos. Con datos reales se necesita una clave privada estable, gestionada fuera del código y del repositorio. El programa actual lee esta variable del entorno y **no carga automáticamente un archivo `.env`**.

Usa `-m training.run_sprint1` desde la raíz del proyecto: así Python puede resolver las importaciones de `training`. El único argumento propio de esta línea de comandos es `--source`, que es obligatorio.

### Ejecutarlo con un archivo que ya tengas

Después de preparar el entorno y la variable anterior, sustituye la ruta por la de tu archivo compatible:

```powershell
& .\.venv\Scripts\python.exe -m training.run_sprint1 --source 'C:\ruta\a\tu\archivo.csv'
```

La entrada debe cumplir `training/config/data_contract.yaml`: al menos 1000 filas, las columnas esperadas y un objetivo válido de 0 o 1. El CSV se lee con comas y codificación UTF-8. Para Excel `.xlsx`, la lista actual de dependencias no incluye `openpyxl`; si vas a usar ese formato, instálalo en el mismo entorno:

```powershell
& .\.venv\Scripts\python.exe -m pip install openpyxl
```

### Ejecutarlo desde PyCharm

Una vez creado el entorno y generado el archivo de prueba, configura una ejecución de Python con estos valores:

| Campo | Valor |
|---|---|
| Intérprete | `C:\Users\jorAN\Downloads\codigo\.venv\Scripts\python.exe` |
| Tipo de ejecución | Módulo / Module name |
| Nombre del módulo | `training.run_sprint1` |
| Parámetros | `--source data/source/solicitudes_demo.csv` |
| Directorio de trabajo | `C:\Users\jorAN\Downloads\codigo` |
| Variable de entorno, solo para la prueba sintética | `RISK_PSEUDO_SALT=solo-prueba-local-datos-sinteticos` |

Después pulsa **Run**. La variable definida en una terminal PowerShell no se incorpora necesariamente a una configuración de ejecución de PyCharm; introdúcela también en esa configuración.

## 3. Explicación técnica en lenguaje sencillo

### El contrato: las reglas que debe cumplir el archivo

`load_contract()` lee `training/config/data_contract.yaml`. Este archivo define los nombres de columnas, sus tipos, los rangos admitidos, qué campos eliminar y cómo preparar los datos.

Por ejemplo, `ingreso_mensual` se trata como número, `estado_civil` como categoría y `fecha_solicitud` como fecha. La columna objetivo actual es `default_12m` y debe venir calculada en el archivo: el pipeline no la construye a partir de pagos.

### HU01: cargar, proteger y validar

`ingest()` está en `training/ingestion.py` y realiza lo siguiente:

1. Lee el archivo indicado en `--source`.
2. Elimina las columnas personales configuradas, como `ruc` y `nombre_cliente`, de la copia procesada. El archivo fuente no se modifica.
3. Sustituye `cliente_id` por un código calculado con HMAC-SHA256. Con la misma clave y el mismo identificador se obtiene el mismo código.
4. Comprueba las columnas requeridas y el mínimo de filas, convierte tipos y rechaza objetivos inválidos. Las columnas adicionales se descartan.
5. Guarda una copia base en Parquet y un registro de la ingesta.

Parquet es un formato de archivo para tablas. Un «manifiesto» es un archivo JSON que acompaña a un resultado con sus metadatos y una huella SHA-256 para comprobar si su contenido ha cambiado.

La validación de estructura no implica que todos los valores sean correctos: algunos errores de conversión pasan a ser datos faltantes; los rangos numéricos se tratan después.

### HU02: conocer el estado de los datos

`run_eda()` está en `training/eda.py`. EDA significa análisis exploratorio de datos: resume qué contiene la tabla antes de limpiarla.

Produce estadísticas, proporciones de las clases 0 y 1, porcentajes de faltantes, detección de valores atípicos, duplicados, valores fuera de rango y relaciones entre variables. También calcula la tasa del objetivo por mes de solicitud y genera gráficos PNG.

Esta etapa describe problemas, pero no los corrige. Se ejecuta sobre todos los datos recibidos, antes de separar entrenamiento y prueba. El script genera tablas y gráficos; no ejecuta el notebook ni produce automáticamente un informe HTML.

### HU03: dejar los datos en formato numérico

`prepare()` está en `training/preprocessing.py`:

1. Elimina filas exactamente duplicadas y convierte valores fuera de los rangos configurados en faltantes.
2. Separa la tabla en aproximadamente 80 % para entrenamiento y 20 % para prueba, conservando la proporción de las clases. Usa la semilla 42 para repetir la partición con los mismos datos y configuración.
3. Aprende las reglas de transformación solo con entrenamiento y las aplica a prueba.
4. Comprueba que los resultados sean numéricos y no contengan valores faltantes ni infinitos.

| Tipo de dato | Tratamiento |
|---|---|
| Numérico | Reemplaza faltantes por la mediana del entrenamiento y añade indicadores de ausencia cuando corresponde. |
| Booleano, como `tiene_garantia` | Reemplaza faltantes por el valor más frecuente. |
| Categoría ordenada, como `calificacion_sbs` | Completa con el valor más frecuente y asigna números según el orden del contrato. |
| Categoría con hasta 10 valores distintos en entrenamiento | Usa `Desconocido` para faltantes y crea columnas indicadoras de cada categoría, técnica llamada one-hot. |
| Categoría con más de 10 valores distintos en entrenamiento | Usa `Desconocido` y una codificación basada en el objetivo, con cinco particiones internas para reducir la fuga de información. |

La «fuga de información» ocurre cuando la preparación o el entrenamiento utiliza información que no debería conocer al evaluarse. Ajustar las transformaciones solo con entrenamiento evita una fuente de esa fuga; no garantiza por sí solo una validación temporal correcta.

`X_train` y `X_test` contienen las variables transformadas. `y_train` y `y_test` contienen la respuesta conocida, 0 o 1. El identificador y la fecha no entran en las matrices finales; se conservan en el dataset base.

`persist_artifacts()` guarda ambas particiones, el transformador aprendido, un reporte de preparación y un diccionario de variables. `preprocessor.joblib` contiene el transformador, no un modelo predictivo entrenado.

### Medición de tiempos y resumen

En `run_sprint1.py`, `time.perf_counter()` mide cuánto tarda cada etapa. Los resultados se redondean a tres decimales y se suman en `total_s`. Ese total corresponde a las etapas medidas; no incluye todo el arranque de Python ni la carga inicial del contrato.

Al terminar, el script imprime un JSON con `evento`, `fecha_utc`, `tiempos`, `filas_entrada`, `columnas_finales` y `artefactos`. También añade ese resumen a `logs/pipeline_log.jsonl`. JSONL almacena un registro JSON por línea.

Si una etapa falla, el error interrumpe el flujo. Pueden quedar archivos de etapas anteriores; el proceso no deshace automáticamente lo que ya guardó.

## 4. Dónde quedan los resultados

Las rutas se resuelven respecto al directorio desde el que ejecutas el programa. Con los comandos anteriores, estarán dentro de `codigo/`.

| Ubicación | Contenido |
|---|---|
| `data/raw/dataset_base_<fecha>.parquet` | Datos cargados, con identificadores protegidos y tipos convertidos. |
| `reports/eda/` | Tablas CSV, cinco gráficos PNG y `eda_summary.json`. |
| `data/prepared/dataset_preparado_train.parquet` | Variables de entrenamiento y columna objetivo. |
| `data/prepared/dataset_preparado_test.parquet` | Variables de prueba y columna objetivo. |
| `data/prepared/preprocessor.joblib` | Reglas de transformación aprendidas. |
| `data/prepared/preparation_report.json` | Detalles de limpieza, grupos de variables y validación. |
| `data/prepared/data_dictionary.md` | Descripción de las variables y sus tratamientos. |
| `*.manifest.json` junto a los Parquet y al transformador | Huellas de integridad y metadatos. |
| `logs/ingestion_log.jsonl` y `logs/pipeline_log.jsonl` | Registros de ingesta y resumen del flujo completado. |

Los archivos preparados y los reportes EDA usan nombres fijos: una nueva ejecución los sobrescribe. Los logs añaden registros. El dataset base incorpora fecha y hora en el nombre.

## 5. Opciones al llamarlo desde otro código Python

La función principal tiene esta firma:

```python
run(source: str, persist: bool = True, eda: bool = True) -> dict
```

`source` es la ruta de entrada; `persist` controla si se guardan el dataset base y los artefactos preparados; `eda` controla si se genera el análisis exploratorio.

Estos dos últimos controles solo están disponibles al importar la función: no existen argumentos de terminal `--persist` o `--eda`. Además, `persist=False` no significa «no escribir nada»: los logs siguen escribiéndose y el EDA guarda reportes si está habilitado.

## 6. Problemas frecuentes

| Mensaje o situación | Qué revisar |
|---|---|
| `py` no se reconoce o no encuentra Python 3.12 | Comprueba la instalación de Python 3.12 y de su lanzador para Windows. |
| `ModuleNotFoundError` de una biblioteca | Instala `requirements-training.txt` con el mismo Python que ejecuta el script. |
| `No module named training` | Ejecuta desde la raíz `codigo` y usa `-m training.run_sprint1`. |
| `--source` es obligatorio | Añade `--source` seguido de la ruta al archivo. |
| `fuente de datos no disponible` | Comprueba que el archivo exista, tenga contenido y su ruta sea correcta. |
| `Columnas requeridas ausentes` | Compara los encabezados con el contrato; no basta con tener cualquier CSV. |
| Error de objetivo inválido | `default_12m` debe contener solo 0 y 1, sin faltantes. |
| Error al dividir clases o en la codificación | Revisa que existan ambas clases y suficientes ejemplos de cada una; se usan partición estratificada y cinco particiones internas. |
| Error de valores infinitos o `NaN` | Revisa datos y columnas completamente vacías; la imputación no garantiza resolver todas las entradas posibles. |

## 7. Alcance y brechas frente a la tesis revisada

El comportamiento descrito corresponde a la versión actual. Tras revisar el documento de tesis, la unidad de análisis prevista es la solicitud de crédito en originación y el evento operativo documentado es `default_12m`. Persisten estas brechas antes de usar el flujo como evidencia de desempeño del modelo:

- El contrato actual usa `default_12m`: atraso de al menos 30 días durante los 12 meses posteriores al desembolso, conforme a la definición operativa del documento de tesis. El CSV sintético ya incluye la etiqueta; este flujo no comprueba su construcción a partir del historial de pagos ni su madurez temporal.
- El programa lee archivos locales. Existe una comprobación de conectividad SQL Server separada, pero aún no hay extracción de datos reales integrada al pipeline.
- La partición de Sprint 1 es aleatoria y estratificada, sin agrupación por cliente ni separación temporal. Sprint 2 incorpora agrupación por cliente, pero tampoco constituye validación fuera de tiempo. Debe verificarse la disponibilidad de cada variable en originación. El EDA también utiliza el futuro conjunto de prueba; sus resultados no deberían guiar ajustes de un modelo cuya evaluación se presente como independiente.
- El contrato impone un máximo de edad de 85 años y el generador limita las edades a 80. Estos límites deben justificarse o ajustarse al revisar el dataset definitivo.
- El generador crea solicitudes sintéticas con fechas y etiquetas simuladas. No sustituye la comprobación de la estructura y cobertura temporal del dataset definitivo.

Estas diferencias se documentan sin modificar las reglas del código en esta entrega.

## 8. Qué se verificó en esta revisión

Se revisaron el coordinador, la ingesta, el análisis exploratorio, la preparación, la protección de identificadores, el contrato, el generador y las dependencias. También se consultó el entorno de PyCharm, que informó que no hay intérprete configurado.

No se instalaron dependencias ni se ejecutaron el pipeline o las pruebas. Por tanto, los comandos documentan cómo ponerlo en marcha, pero no constituyen una ejecución exitosa comprobada en este equipo.

**Actualización posterior:** esta sección conserva el registro de aquella
revisión inicial. La [línea base de Fase 1](./LINEA_BASE_FASE1.md) documenta
una ejecución posterior de 78 pruebas aprobadas y de ambos sprints con datos
sintéticos el 14/11/2026.

Una vez preparado el entorno, puedes ejecutar las pruebas funcionales existentes sin la prueba de rendimiento:

```powershell
& .\.venv\Scripts\python.exe -m pytest -m 'not performance'
```
