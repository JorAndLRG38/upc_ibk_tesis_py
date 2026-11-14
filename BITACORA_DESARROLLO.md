# Bitácora de desarrollo

## Instrucción para futuras revisiones

Cada vez que un modelo o integrante revise esta documentación o ejecute una solicitud de cambio, debe agregar una entrada al inicio de la sección **Historial de cambios** con:

- fecha y hora local;
- autor o agente;
- prompt o solicitud ejecutada;
- resultado breve;
- archivos modificados o artefactos generados.

La entrada debe ser breve, verificable y no debe reemplazar la documentación técnica detallada de cada fase.

## Historial de cambios

### 2026-11-14 02:04 America/Lima

- Autor: Codex.
- Prompt ejecutado: “1. Deja anotado en el plan, en la fase siguiente, el validar default_12m con el dataset definitivo como punto inicial del mismo, para que sea lo primero que se realice. 2. La métrica es KS, tienes toda la razón. Por el cansancio me había equivocado. 3. Deja pendiente revisar el tema de XGBoost v1. Anotalo como parte de la fase siguiente o indicalo dentro de esta misma fase, para no perder la trazabilidad de que debemos realizarlo. Con eso terminamos por hoy, muchas gracias.” Referencia: `BITACORA_DESARROLLO.md`.
- Resultado: Fase 2 inicia con la validación de `default_12m`; KS confirmado; revisión de XGBoost v1 programada a continuación. D-03 (K2/KS) resuelta.
- Archivos modificados: `PLAN_ESTRATEGICO_DESARROLLO.md`, `docs/decisiones_metodologicas.md`, `docs/matriz_trazabilidad.md`, `docs/LINEA_BASE_FASE1.md`, `BITACORA_DESARROLLO.md`.
- Código funcional: sin cambios.

### 2026-11-14 01:56 America/Lima

- Autor: Codex.
- Prompt ejecutado: “Genial. Ejecuta la fase 0, una vez terminado, retiralo de del plan. Adicional, no olvide registrar los cambios en la bitacora. Con ello vamos a quedar alineados al proyecto principal. Sí queda alguna duda, hazmelo saber.” Referencia: `PLAN_ESTRATEGICO_DESARROLLO.md`.
- Resultado: tesis y repositorio alineados documentalmente; matriz de trazabilidad y decisiones metodológicas creadas; Fase 0 retirada del plan. Quedan abiertas la validación del dataset definitivo, la diferencia K2/KS y la evidencia de XGBoost v1.
- Archivos modificados o generados: `README.md`, `README_SPRINT1.md`, `PLAN_ESTRATEGICO_DESARROLLO.md`, `BITACORA_DESARROLLO.md`, `docs/matriz_trazabilidad.md`, `docs/decisiones_metodologicas.md`, `docs/estructura_proyecto.md`, `docs/guia_run_sprint1.md`, `docs/sprint2_hu04_hu06.md`, `docs/demo_colab.md`, `docs/LINEA_BASE_FASE1.md`.
- Código funcional: sin cambios.

### 2026-11-14 01:35 America/Lima

- Autor: Codex - Jorge La Rosa
- Solicitud: “Ejecuta la Fase 1, vamos a documentar los avances que tenemos. Una vez realices ello, retiralo del plan. Adicional, genera un archivo tipo bitacora donde indiques la fecha, la hora, el prompt ejecutad y el historial de archivos modificados (sin mucho detalle). y que, a su vez, cuando un modelo revise la documentación sepa que debe registrar en ese punto los cambios realizados con fecha y hora.”
- Resultado: Fase 1 ejecutada; pruebas completas aprobadas; Sprint 1 y Sprint 2 ejecutados con datos sintéticos; línea base documentada.
- Archivos modificados o generados: `PLAN_ESTRATEGICO_DESARROLLO.md`, `docs/LINEA_BASE_FASE1.md`, `BITACORA_DESARROLLO.md`, datos y artefactos locales de la ejecución.
- Código funcional: sin cambios.
