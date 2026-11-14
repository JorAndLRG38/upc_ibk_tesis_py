# Base de desarrollo del Sprint 2: HU04, HU05 y HU06

## Diagnóstico y alcance

Antes de este incremento, el código contenía ingesta, EDA, preparación del
Sprint 1 y una comprobación de conexión SQL Server. No tenía implementaciones
de Boruta, RFECV ni SMOTE-ENN ni sus dependencias.

Este incremento implementa **algoritmos reales**, un recorrido reproducible y
pruebas para las tres historias. Es una **base experimental de laboratorio**:
no constituye el cierre académico integral de las HU ni un modelo listo para
evaluar clientes. Los criterios completos de aceptación/DoD deben revisarse
cuando estén disponibles; la imagen recibida contiene las historias, prioridad
y estimación, pero no sus criterios de aceptación.

| Historia | Implementación | Evidencia producida | Límite actual |
|---|---|---|---|
| HU04: aplicar Boruta | `BorutaPy` con Random Forest, semilla y presupuesto configurables | Estado confirmada/tentativa/rechazada y ranking por variable | Primera base solo numérica; sin confirmadas la ejecución falla explícitamente |
| HU05: aplicar RFECV | `RFECV` con Average Precision, bosques auxiliares e imputación dentro de cada fold interno | Subconjunto, rankings y curva de selección | Curva interna condicionada por Boruta, no estimación independiente del desempeño |
| HU06: aplicar SMOTE-ENN a entrenamiento | `SMOTEENN` con SMOTE y Edited Nearest Neighbours; escalado ajustado con train | Conteos antes/después y número generado/eliminado | No se aplica a validación/test; no garantiza clases finales idénticas ni mejora predictiva |

## Ejecutar en este equipo

Desde PowerShell, en la raíz del proyecto:

```powershell
cd C:\Users\jorAN\Downloads\codigo
& .\.venv\Scripts\python.exe -m pip install -r requirements-sprint2.txt
$env:RISK_PSEUDO_SALT = 'solo-prueba-local-datos-sinteticos'
& .\.venv\Scripts\python.exe -m training.run_sprint2 --demo --source .\data\source\solicitudes_demo.csv
```

`--demo` es obligatorio y declara que se está usando una fuente sintética.
No utilizarlo para presentar registros bancarios reales como sintéticos.
La ingesta no puede demostrar la procedencia de un CSV por sí sola.
El valor de la clave de seudonimización del ejemplo es solo para estos datos.

La configuración reside en `training/config/sprint2.yaml`. Para probar otra:

```powershell
& .\.venv\Scripts\python.exe -m training.run_sprint2 --demo --source .\data\source\solicitudes_demo.csv --config .\training\config\sprint2.yaml
```

Cada ejecución crea una carpeta nueva en `artifacts/sprint2/<fechaUTC>_<id>/`.
No sobrescribe los resultados anteriores ni el preprocesador del Sprint 1.
La consola informa qué fold se procesa y la ruta del resultado. El tiempo
depende de las filas, árboles, iteraciones de Boruta y folds configurados.
Código de salida 0: recorrido completado; 2: error de entrada/configuración
o resultado insuficiente. `ERROR.json` registra fallos sin declarar éxito.

## Archivos que puedes mostrar en la exposición

| Archivo generado | Qué permite verificar |
|---|---|
| `LEER_RESULTADOS.md` | Resumen de ejecución, alcance y límites |
| `reporte_sprint2.json` | Fuente/hash, contrato, versiones, parámetros, particiones y resultados por fold y ajuste final |
| `boruta_variables.csv` | Variables confirmadas, tentativas y rechazadas; ranking |
| `rfecv_variables.csv` | Refinamiento del subconjunto de Boruta |
| `rfecv_curva.csv` | Average Precision interna según número de variables |
| `balance_clases.csv` | Conteos por clase antes y después de SMOTE-ENN |
| `train_sin_remuestreo.parquet` | Desarrollo transformado, antes de balancear; base para comparación posterior |
| `train_smoteenn.parquet` | Entrenamiento seleccionado, imputado, escalado y remuestreado |
| `test_sin_remuestreo.parquet` | Prueba con las mismas columnas y transformaciones, sin cambiar filas ni etiquetas |
| `preparacion_sprint2.joblib` | Selección y transformaciones ajustadas; **no es un clasificador XGBoost** |
| `*.manifest.json` | Hash SHA-256 e información de los artefactos principales |

Los CSV de variables se refieren al ajuste final sobre desarrollo. El JSON
también conserva los subconjuntos de cada fold externo, que pueden diferir.
Las columnas de los Parquet están en el espacio estandarizado; los valores
interpolados no representan nuevos clientes, cuotas ni pagos reales. No se
escriben datos en SQL Server.

## Recorrido y prevención de fuga de información

1. Ingestar y seudonimizar el CSV de laboratorio con el contrato existente.
2. Eliminar duplicados y aplicar las reglas deterministas de limpieza del
   Sprint 1. Se usan las variables numéricas explícitas de la configuración;
   se excluyen identificadores, fecha, objetivo y variables categóricas.
3. Reservar un fold de `StratifiedGroupKFold` como test, agrupando por cliente.
   La fracción resultante es aproximadamente 1/5; puede variar por grupos.
4. Dividir desarrollo en folds externos. En **cada entrenamiento externo**:
   - Ajustar la mediana de entrada a Boruta y ejecutar Boruta.
   - Pasar solo variables confirmadas a RFECV, todavía sin imputar.
   - RFECV ajusta su imputador y estimador auxiliar dentro de cada fold interno,
     también separado por cliente.
   - Ajustar imputación y StandardScaler sobre el entrenamiento externo con
     las variables seleccionadas. La escala es necesaria para las distancias
     utilizadas por SMOTE y ENN.
   - Ejecutar SMOTE-ENN exclusivamente sobre ese entrenamiento.
   - Transformar la validación externa usando lo aprendido, sin remuestrearla.
5. Reajustar el procedimiento sobre todo desarrollo y transformar el test
   reservado una sola vez. Conservar su número de filas, índices y etiquetas.

El diseño no consume `data/prepared/preprocessor.joblib` ni los datos ajustados
globalmente del Sprint 1. Evita reutilizar un TargetEncoder o imputador que ya
haya observado las etiquetas/estadísticas de una validación interna.

Boruta selecciona con todo el entrenamiento externo; RFECV refina esa selección
mediante CV interna. Por ello, sus scores son **criterios de selección
condicionados por la etapa anterior**, no métricas de generalización. Los folds
externos rehacen todas las etapas. En este incremento no se ajusta un predictor
final sobre ellos: se registra el funcionamiento de preparación por partición,
sin inventar AUC, recall, F1 ni probabilidades de atraso.

Agrupar por cliente evita que un cliente aparezca en los dos lados de una
partición, pero **no equivale a validación temporal**. La prueba fuera de tiempo,
el control de ventanas de 90 días y los snapshots maduros siguen pendientes.

## Por qué la base inicial usa solo variables numéricas

El Sprint 1 también produce one-hot, ordinales, booleanos e indicadores de
faltantes. Aplicar SMOTE directamente a esas columnas puede producir categorías
fraccionarias sin una interpretación válida. Por eso esta base no remuestrea
automáticamente todas las columnas del artefacto anterior.

La configuración enumera once variables numéricas del contrato de laboratorio.
La selección final la deciden Boruta y RFECV. Para integrar las categorías deben
evaluarse alternativas como SMOTENC y una limpieza compatible, y justificarse
experimentalmente su representación. Los conteos/edades pueden adquirir valores
intermedios en el espacio sintético: no se redondean arbitrariamente ni se
presentan como registros operativos reales.

## Manejo de situaciones insuficientes

- Boruta sin variables confirmadas: error; no se sustituyen por tentativas ni
  se eligen variables manualmente para forzar éxito.
- Boruta con una sola confirmada: RFECV queda marcado
  `NO_APLICA_UNA_VARIABLE`; no se finge una búsqueda imposible.
- Pocas observaciones minoritarias para SMOTE o un fold sin ambas clases: error
  explicativo; no se cambian los parámetros silenciosamente.
- ENN elimina toda una clase: error; no se guarda una preparación como válida.
- Columnas completamente vacías en entrenamiento, infinitos, categorías,
  etiquetas/grupos desalineados o cambio de esquema: rechazo explícito.
- ENN puede dejar proporciones diferentes de 50/50; el reporte registra lo que
  realmente ocurrió y no asume una mejora del modelo.

## Reutilización para la futura conexión a la base de datos

`training.run_sprint2.run_experiment(X, y, groups, config)` acepta variables
numéricas crudas y etiquetas/grupos alineados. `X` debe excluir el objetivo y
los identificadores. `y` debe tener nombre y ambas clases; `groups` identifica
al cliente. `Sprint2Preparation.fit_resample` recibe solo entrenamiento y
`transform(X)` nunca recibe etiquetas ni remuestrea.

El adaptador que construya estos objetos desde SQL Server **aún no está
implementado**. Antes de usarlo, deben verificarse las claves, relaciones,
fechas, filtros y disponibilidad histórica de cada atributo. La etiqueta del
CSV sigue siendo `default_12m` (atraso >= 30 días en 12 meses); no se ha
renombrado para simular el objetivo de la tesis. Hay que construir y comprobar
`target_incumplimiento` para al menos un día de atraso en los siguientes 90 días.

## Pruebas

```powershell
& .\.venv\Scripts\python.exe -m pytest test/test_sprint2.py
& .\.venv\Scripts\python.exe -m pytest
```

Las pruebas ejecutan los tres algoritmos con datos pequeños, revisan señales
conocidas, refinamiento, cambio de distribución, reproducción con semilla,
persistencia/carga y fallos controlados. Comprueban además la separación por
cliente, la imputación interna de RFECV y que test no intervenga en ningún
ajuste ni remuestreo. No requieren BD ni credenciales.

## Ejecución comprobada el 11/11/2026 (Lima)

La suite completa terminó con **75 pruebas aprobadas**, incluidas 25 nuevas.
Las cuatro advertencias existentes corresponden a parámetros de `TargetEncoder`
del Sprint 1; no hubo fallos. `pip check` no encontró conflictos de dependencias.

Se ejecutó el comando de demostración con el CSV existente y la configuración
predeterminada. La carpeta de evidencia es
`artifacts/sprint2/20261112T032603Z_603a5687/` (el nombre utiliza UTC).

| Paso | Resultado observado |
|---|---|
| Entrada | 5 015 filas; 15 duplicados eliminados |
| Partición | 4 000 filas de desarrollo y 1 000 de prueba |
| HU04 | 4 variables confirmadas entre 11 candidatas numéricas |
| HU05 | RFECV evaluó los subconjuntos y conservó las 4 variables; no redujo más el conjunto |
| HU06 | Antes: clase 0 = 3 623, clase 1 = 377; después: clase 0 = 2 101, clase 1 = 2 380 |
| Prueba reservada | 1 000 filas conservadas, sin remuestreo |
| Recorrido por particiones | 3 folds externos y ajuste final ejecutados |

Las cuatro variables finales fueron `antiguedad_negocio_meses`,
`n_entidades_sbs`, `deuda_total_sbs` y `max_dias_atraso_12m`. La selección
corresponde únicamente a este experimento sintético con `default_12m`.
No implica que sean las variables definitivas de la tesis ni acredita mejora
predictiva. Los resultados detallados por fold pueden diferir del ajuste final.

## Continuidad para el cierre integral

Completar la extracción temporal de SQL Server y el contrato de 90 días;
integrar categorías con tratamiento justificado; entrenar XGBoost (HU07) y
comparar con una base sin remuestreo; evaluar con particiones y métricas
adecuadas, calibración y umbrales; documentar resultados y revisar los criterios
de aceptación completos. No se asume que seleccionar o balancear mejore el
desempeño hasta comprobarlo.

## Referencias técnicas consultadas

- [Implementación oficial BorutaPy](https://github.com/scikit-learn-contrib/boruta_py).
- [RFECV, documentación de scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.feature_selection.RFECV.html).
- [SMOTEENN, documentación de imbalanced-learn](https://imbalanced-learn.org/stable/references/generated/imblearn.combine.SMOTEENN.html).
- [SMOTENC y datos mixtos](https://imbalanced-learn.org/stable/references/generated/imblearn.over_sampling.SMOTENC.html).
