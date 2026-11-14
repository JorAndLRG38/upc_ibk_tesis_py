# Matriz de trazabilidad entre tesis y repositorio

## Alcance y fuente

Esta matriz confronta el documento de tesis **Modelo predictivo basado en XGBoost para la identificación temprana del riesgo de incumplimiento en créditos otorgados a microempresas unipersonales** (versión proporcionada el 14/11/2026) con el estado verificable del repositorio. La tesis no se incorpora al repositorio. Los números de capítulo, sección, OE y HU remiten a ese documento; los enlaces apuntan a evidencia versionada. Una descripción en la tesis de trabajo *planificado* o *desarrollado* no acredita por sí sola que exista el ejecutable en este checkout.

Estados: **implementado** significa que existe código y prueba o ejecución; **parcial** significa que hay una base técnica sin cumplir el alcance completo; **pendiente** significa que no hay implementación verificada; **por confirmar** requiere datos o decisión externa.

| Referencia de tesis | Resultado esperado | Evidencia del repositorio | Estado y brecha |
|---|---|---|---|
| Cap. 1, §1.2.1, OE1; cap. 2 | Analizar y seleccionar técnicas para riesgo de incumplimiento | [Revisión de tesis](./decisiones_metodologicas.md) y [configuración de selección](../training/config/sprint2.yaml) | Parcial: Boruta y RFECV están elegidos; falta evaluación con datos definitivos. |
| Cap. 1, §1.2.1, OE2; cap. 3 | Arquitectura con XGBoost, SMOTE-ENN, SHAP y LIME | [Implementación de Sprint 2](../training/sprint2.py) y [documentación del flujo](./sprint2_hu04_hu06.md) | Parcial: existe preparación y balanceo, no modelo ni explicabilidad. |
| Cap. 1, §1.2.1, OE3; cap. 4, §4.2, HU07 | Modelo XGBoost v1 entrenado en entorno controlado | [Ejecutor de Sprint 2](../training/run_sprint2.py) declara que no entrena XGBoost | Pendiente en este checkout. La tesis narra pruebas iniciales de XGBoost, pero el código correspondiente no está disponible aquí. |
| Cap. 1, §1.2.1–1.2.2, OE4 | Validación con AUC-ROC, Recall, F1-score, KS y Brier Score | [Línea base](./LINEA_BASE_FASE1.md) | Pendiente: no hay probabilidades ni cálculo de estas métricas finales. Metas preliminares de tesis: AUC-ROC ≥ 0,80; Recall de incumplidores ≥ 85 %; KS ≥ 0,30, sujetas a validación con asesor y negocio. |
| Cap. 4, §4.1, HU01–HU03 | Ingesta, EDA y preparación | [Ejecutor de Sprint 1](../training/run_sprint1.py), [pruebas de ingesta](../test/test_hu01_ingestion.py), [EDA](../test/test_hu02_eda.py) y [preparación](../test/test_hu03_preprocessing.py) | Implementado para la fuente sintética/local; no acredita integración con datos bancarios. |
| Cap. 4, §4.2, HU04 | Selección inicial con Boruta | [Sprint 2](../training/sprint2.py) y [pruebas](../test/test_sprint2.py) | Implementado para variables numéricas sintéticas. |
| Cap. 4, §4.2, HU05 | Refinamiento con RFECV | [Sprint 2](../training/sprint2.py) y [curva de selección](./sprint2_hu04_hu06.md) | Implementado para variables confirmadas por Boruta; `average_precision` es criterio interno, no AUC final. |
| Cap. 4, §4.2, HU06 | Balanceo SMOTE-ENN solo en entrenamiento | [Sprint 2](../training/sprint2.py) y [pruebas](../test/test_sprint2.py) | Implementado en la base numérica; validación y test no se remuestrean. |
| Cap. 3 y cap. 4, §4.2 | Comparación con regresión logística, Random Forest, LightGBM y CatBoost | No se identificó ejecutable de comparación; [estado actual](../README.md) | Pendiente. Los bosques auxiliares de selección no equivalen a modelos comparativos evaluados. |
| Cap. 3 y objetivo OE2 | Explicabilidad global y local con SHAP y LIME | No se identificó componente de explicabilidad; [estado actual](../README.md) | Pendiente; requiere predictor entrenado y validado. |
| Glosario, «Incumplimiento operativo del estudio» | `default_12m`: atraso ≥ 30 días en los 12 meses posteriores al desembolso | [Contrato de datos](../training/config/data_contract.yaml) | Definición documental alineada; construcción, madurez y disponibilidad histórica por confirmar con dataset definitivo. |
| Cap. 1, §1.2.1 y cap. 3 | Scoring de solicitudes en originación, RUC 10 | [Contrato de datos](../training/config/data_contract.yaml) y [README](../README.md) | Alineación documental realizada; se debe verificar que las variables existían en la fecha de originación. |
| Cap. 4, §4.2, DoD del sprint | Código, configuración, semillas, pruebas y evidencias reproducibles | [Línea base](./LINEA_BASE_FASE1.md) y [bitácora](../BITACORA_DESARROLLO.md) | Parcial: 78 pruebas aprobadas con datos sintéticos; no acredita HU07 ni métricas de éxito. |

## Cuestiones que pasan a las fases siguientes

1. Validar `default_12m` contra fechas de desembolso y pagos observados; definir población elegible y madurez completa de 12 meses.
2. Comprobar que cada predictor, en particular `max_dias_atraso_12m`, usa exclusivamente información anterior o disponible en originación. El nombre de la variable por sí solo no permite descartar fuga de información.
3. Conciliar el texto heredado de 90 días presente en comentarios y reportes generados por el ejecutor con el objetivo de la tesis. Su corrección funcional queda en la Fase 2.
4. Después de validar `default_12m` como primera actividad de la Fase 2, localizar, si existe fuera de este checkout, el código y las evidencias de las pruebas iniciales de XGBoost descritas en el cap. 4, §4.2. Mientras no se integren y verifiquen, HU07 permanece pendiente en el repositorio.

**Aclaración resuelta el 14/11/2026:** el usuario confirmó que la métrica prevista es KS y que “K2” fue un error al escribir. No se añadirá una técnica de selección K2.
