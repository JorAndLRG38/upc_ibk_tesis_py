# Plan estratégico incremental del proyecto

## Propósito

Este documento establece una ruta de trabajo gradual para desarrollar y documentar el proyecto de tesis. Cada cambio se solicitará y validará por separado. El objetivo es mantener trazabilidad entre el planteamiento de la tesis, los datos, la selección de variables, el entrenamiento y la evaluación final.

El plan evita adelantar una implementación compleja antes de confirmar los criterios metodológicos, las fuentes de datos y el objetivo predictivo.

## Alcance conocido

La revisión actual se realizó sobre el repositorio, su documentación y el documento de tesis proporcionado. La alineación metodológica y su trazabilidad están registradas en [decisiones metodológicas](./docs/decisiones_metodologicas.md) y la [matriz de trazabilidad](./docs/matriz_trazabilidad.md). El proyecto contiene una base experimental para:

- ingesta, limpieza y validación de datos;
- análisis exploratorio;
- selección inicial con Boruta;
- refinamiento con RFECV;
- balanceo experimental con SMOTE-ENN;
- particiones agrupadas por cliente;
- pruebas automatizadas del flujo existente.

La ejecución actual trabaja con variables numéricas y datos sintéticos. La tesis revisada documenta `default_12m`: atraso de al menos 30 días durante los 12 meses posteriores al desembolso, en solicitudes evaluadas en originación. Esta definición debe confirmarse con el dataset definitivo y mantenerse uniforme entre la tesis, el contrato de datos, el código y los reportes.

Actualmente no se consideran implementados:

- cálculo de AUC como métrica de evaluación;
- extracción temporal completa desde SQL Server;
- validación del objetivo `default_12m` con el dataset definitivo;
- entrenamiento y evaluación final de XGBoost;
- validación temporal y análisis de generalización con datos reales.

## Principios de trabajo

1. **Un cambio por solicitud.** Cada etapa debe poder revisarse, ejecutarse y revertirse de forma independiente.
2. **Primero evidencia, después implementación.** Antes de modificar código se revisarán los archivos, contratos, dependencias, pruebas y resultados existentes.
3. **No mezclar selección con evaluación final.** Boruta y RFECV ayudan a seleccionar variables; AUC debe calcularse sobre predicciones de un clasificador y particiones no utilizadas para ajustar el modelo.
4. **Prevenir fuga de información.** La transformación, selección, balanceo y entrenamiento deben ajustarse únicamente con los datos permitidos en cada partición.
5. **Preservar la trazabilidad.** Cada resultado debe registrar fuente, objetivo, variables, configuración, partición, semilla, versiones y limitaciones.
6. **No presentar datos sintéticos como validación bancaria.** Las ejecuciones sintéticas servirán para probar el flujo técnico, no para afirmar desempeño real.
7. **Usar la nomenclatura confirmada.** La métrica correcta es KS; K2 fue un error al formular la solicitud inicial y no es una técnica adicional del proyecto.
8. **Registrar cada intervención.** Todo cambio o ejecución relevante debe anotarse en [BITACORA_DESARROLLO.md](./BITACORA_DESARROLLO.md), con fecha, hora, solicitud, archivos afectados y resultado breve.

## Ruta de desarrollo propuesta

Las fases 0 (alineación documental) y 1 (línea base técnica) están completadas. Sus resultados permanecen en la [matriz de trazabilidad](./docs/matriz_trazabilidad.md), las [decisiones metodológicas](./docs/decisiones_metodologicas.md) y la [línea base de Fase 1](./docs/LINEA_BASE_FASE1.md). Las cuestiones que necesitan datos definitivos o evidencia externa siguen abiertas en esos documentos y se resolverán en las fases correspondientes.

### Fase 2. Formalizar datos y objetivo predictivo

**Objetivo:** asegurar que el flujo use una etiqueta coherente con la tesis.

Actividades, en orden:

1. **Primero:** validar `default_12m` con el dataset definitivo: comprobar que la etiqueta corresponde a un atraso de al menos 30 días durante los 12 meses posteriores al desembolso y que cada observación tiene el horizonte completo.
2. Localizar y revisar el código, las configuraciones y las evidencias de XGBoost v1 mencionados en la tesis. Registrar si existen fuera de este checkout y si son reproducibles; no dar HU07 por implementada sin esa verificación.
3. Precisar la unidad de observación y las fechas de solicitud, desembolso, corte y seguimiento.
4. Identificar las variables disponibles en originación y sus ventanas históricas.
5. Verificar duplicados, clientes compartidos y disponibilidad histórica.
6. Documentar el contrato de datos definitivo y sus reglas de calidad; corregir las referencias heredadas a 90 días en el ejecutor y sus reportes cuando se valide el alcance funcional.

**Resultado esperado:** objetivo y contrato de datos validados antes del modelamiento, más el estado verificable de XGBoost v1 registrado para conservar la trazabilidad de HU07.

### Fase 3. Integrar la fuente real de datos

**Objetivo:** reemplazar gradualmente la dependencia de datos sintéticos.

Actividades:

- validar consultas y relaciones de SQL Server;
- extraer un conjunto controlado de desarrollo;
- conservar trazabilidad y seudonimización;
- comparar esquema y distribuciones contra el contrato;
- probar que la extracción no modifica la base de datos.

**Resultado esperado:** dataset reproducible de desarrollo, con controles de seguridad y calidad.

### Fase 4. Definir el protocolo de selección de variables

**Objetivo:** establecer una comparación justa entre los métodos de selección.

Actividades:

- conservar como protocolo base el orden Boruta y RFECV, que es el que aparece en la tesis;
- definir si cada método se ejecutará por separado o como filtro encadenado;
- especificar folds, agrupación por cliente y semilla;
- definir cómo se tratarán variables numéricas, categóricas, booleanas y faltantes;
- evitar que el test o una partición temporal futura participe en la selección;
- registrar variables seleccionadas, ranking, estabilidad entre folds y criterios de descarte.

**Resultado esperado:** protocolo de selección aprobado antes de agregar implementaciones.

### Fase 5. Implementar y validar los métodos faltantes

**Objetivo:** agregar únicamente los componentes necesarios, en cambios pequeños.

Orden sugerido:

1. consolidar el reporte comparable de Boruta y RFECV;
2. entrenar un clasificador base que genere probabilidades;
3. incorporar AUC ROC y, si corresponde, AUC de Precision-Recall;
4. incorporar Recall, F1-score, KS y Brier Score según la tesis;
5. comparar resultados por método y por partición;
6. revisar estabilidad y posibles fugas de información.

**Resultado esperado:** ejecutables independientes o parametrizables, con pruebas enfocadas y reportes reproducibles.

### Fase 6. Entrenar y evaluar el modelo final

**Objetivo:** medir capacidad predictiva sobre datos no utilizados durante la selección.

Actividades:

- definir baseline sin selección y baseline sin remuestreo;
- entrenar XGBoost u otro modelo definido por la tesis;
- evaluar AUC, Average Precision, recall, precisión, F1, KS y calibración cuando corresponda;
- usar validación temporal y mantener un conjunto de prueba final aislado;
- analizar umbrales según el objetivo operativo;
- reportar intervalos o variabilidad entre particiones cuando sea posible.

**Resultado esperado:** evaluación de desempeño, no solo selección de variables.

### Fase 7. Documentación y cierre

**Objetivo:** convertir la evidencia técnica en material utilizable para la tesis.

Actividades:

- actualizar README y documentación de ejecución;
- guardar configuración y manifiestos de cada experimento;
- generar tablas de variables y métricas;
- documentar limitaciones y decisiones descartadas;
- vincular cada resultado con el capítulo o sección correspondiente de la tesis.

**Resultado esperado:** resultados reproducibles y defendibles académicamente.

## Criterios para aceptar cada cambio

Antes de pasar a la siguiente etapa, cada cambio deberá cumplir:

- existe una prueba o verificación concreta;
- no rompe las pruebas anteriores;
- la ejecución se puede repetir con una configuración explícita;
- se conocen las entradas, salidas y artefactos generados;
- se documentan las limitaciones;
- no se afirma desempeño predictivo si solo se ejecutó selección de variables;
- el cambio mantiene separadas las particiones de entrenamiento, validación y prueba.

## Próxima solicitud recomendada

La siguiente acción recomendada es iniciar la Fase 2 por la validación de `default_12m` con el dataset definitivo. Después se revisará la evidencia de XGBoost v1 mencionada en la tesis, antes de continuar con las demás actividades. La métrica confirmada es KS.

