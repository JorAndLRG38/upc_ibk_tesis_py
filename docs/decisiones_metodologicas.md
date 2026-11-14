# Decisiones metodológicas y cuestiones abiertas

## Fuente y criterio de estado

La referencia es la tesis **Modelo predictivo basado en XGBoost para la identificación temprana del riesgo de incumplimiento en créditos otorgados a microempresas unipersonales**, proporcionada el 14/11/2026. Esta página distingue lo **documentado en la tesis**, lo **implementado en el repositorio** y lo **pendiente de validación**. No sustituye la confirmación del asesor ni del responsable del dataset definitivo.

## Definiciones documentadas en la tesis

| Tema | Definición documentada | Estado técnico actual |
|---|---|---|
| Población y momento de decisión | Solicitudes de microempresas unipersonales (RUC 10) en originación; *application scoring*. | [Contrato](../training/config/data_contract.yaml) y [README](../README.md) alineados en su descripción; datos actuales sintéticos. |
| Variable objetivo | `default_12m`: al menos 30 días de atraso durante los 12 meses posteriores al desembolso, según el glosario de la tesis. | El [contrato](../training/config/data_contract.yaml) declara esta definición; la etiqueta llega ya calculada y no se valida contra pagos reales. |
| Selección de variables | Boruta seguido de RFECV. | [Sprint 2](../training/sprint2.py) implementa ambos en la base experimental numérica. |
| Balanceo | SMOTE-ENN solo en entrenamiento. | Implementado en [Sprint 2](../training/sprint2.py), sin remuestrear validación o test. |
| Modelo principal | XGBoost. | No existe entrenamiento XGBoost en el checkout revisado. |
| Modelos de referencia | Regresión logística, Random Forest, LightGBM y CatBoost. | Comparación pendiente. |
| Explicabilidad | SHAP global y LIME local. | Pendiente. |
| Evaluación | AUC-ROC, Recall, F1-score, KS y Brier Score en validación cruzada; metas preliminares AUC-ROC ≥ 0,80, Recall ≥ 85 % y KS ≥ 0,30. | Pendiente; primero se requieren probabilidades de un clasificador. Las metas deben sustentarse y aprobarse antes de la prueba final, no ajustarse según sus resultados. |

## Distinciones necesarias

- La curva de RFECV usa `average_precision` para elegir subconjuntos dentro de los folds internos. No es AUC-ROC ni una evaluación independiente del modelo final.
- El experimento de Sprint 2 utiliza `StratifiedGroupKFold` para separar clientes. La tesis habla de validación cruzada estratificada; agrupar por cliente añade una salvaguarda, pero no demuestra por sí solo validación temporal. La estrategia exacta de evaluación se definirá antes de entrenar el modelo final.
- El objetivo `default_12m` debe observarse después del desembolso, mientras las variables predictoras deben estar disponibles en originación. La fecha efectiva, el tratamiento de solicitudes no desembolsadas y la madurez de la ventana requieren evidencia del dataset definitivo.
- `max_dias_atraso_12m` necesita una definición temporal inequívoca. Si resume atrasos **posteriores** a la solicitud, sería fuga de información; si resume historial **anterior**, debe documentarse y comprobarse.
- El documento de tesis narra avances iniciales de XGBoost, pero este checkout no contiene un ejecutable que los reproduzca. Se conserva esta diferencia como brecha de trazabilidad, sin presentar la narración como resultado verificado del repositorio.

## Aclaración confirmada

El 14/11/2026 el usuario confirmó que “K2” fue un error al escribir y que la métrica prevista es **KS** (Kolmogorov-Smirnov), tal como figura en la tesis. No se incorporará un método K2 a la selección de variables. Se conserva el identificador D-03 como decisión resuelta para trazabilidad.

## Cuestiones abiertas, no decisiones adoptadas

| ID | Pregunta | Responsable o momento de resolución |
|---|---|---|
| D-01 | ¿El dataset definitivo permite reconstruir `default_12m` con ≥ 30 días de atraso en los 12 meses posteriores al desembolso y verificar el horizonte completo? | Responsable de datos y Fase 2. |
| D-02 | ¿Qué variables financieras, tributarias y crediticias estaban disponibles en la fecha de originación? ¿Cuál es la ventana de `max_dias_atraso_12m`? | Responsable de datos y Fase 2. |
| D-04 | ¿Existen código o registros de XGBoost v1 fuera de este checkout que sustenten el cap. 4, §4.2 de la tesis? | Revisar después de validar `default_12m`, en la Fase 2, antes de afirmar HU07 implementada. |
| D-05 | ¿Cómo combinar agrupación por cliente y control temporal con la validación cruzada estratificada descrita en la tesis? | Protocolo experimental de Fases 4 y 6. |

La métrica **KS forma parte de la evaluación prevista**. Ningún resultado sintético demuestra cumplimiento de las metas de desempeño de la tesis.
