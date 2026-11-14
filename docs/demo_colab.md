# Prueba inicial para Google Colab

## Opción recomendada: abrir el notebook

1. Abre [Google Colab](https://colab.research.google.com/).
2. Selecciona **Archivo → Subir notebook** y carga
   `notebooks/demo_sprint2_colab.ipynb` desde este proyecto.
3. Usa un entorno Python con CPU; no se necesita GPU.
4. Ejecuta las celdas en orden o elige **Ejecutar todas**.
5. La última celda permite descargar `resultados_demo.zip`.

El notebook incluye el script y las fuentes necesarias. No depende de que
el repositorio esté publicado en GitHub. Instala dependencias y ejecuta el
pipeline en un proceso nuevo, para evitar reutilizar paquetes importados
antes de la instalación. Requiere Python 3.11 o posterior y acceso a Internet
para instalar los paquetes. Si la instalación falla, la ejecución se detiene
y muestra el error: no genera un resultado exitoso ficticio.

La posibilidad de subir notebooks y la naturaleza temporal del entorno
están documentadas en la [FAQ oficial de Colab](https://research.google.com/colaboratory/faq.html).
Descarga los resultados antes de cerrar la sesión.

## Alternativa: subir solo el script

En un notebook vacío, ejecuta esta primera celda y selecciona únicamente
`colab/demo_sprint2_colab.py`:

```python
from google.colab import files
files.upload()
```

Luego ejecuta:

```python
import subprocess
import sys

subprocess.run([
    sys.executable, "demo_sprint2_colab.py", "--install",
    "--rows", "5000", "--seed", "42",
    "--output-root", "/content/resultados_demo",
    "--summary-file", "/content/resumen_demo.json",
], check=True)
```

Para descargar el ZIP:

```python
import json
from pathlib import Path
from google.colab import files

resumen = json.loads(Path("/content/resumen_demo.json").read_text())
files.download(resumen["zip"])
```

## Qué demuestra

- Generación de 5000 registros sintéticos más duplicados controlados,
  ingesta, seudonimización y limpieza con el código actual del proyecto.
- HU04: selección con Boruta y reporte de variables confirmadas, tentativas
  y rechazadas.
- HU05: RFECV con particiones por cliente y su estado real de ejecución.
  Puede conservar todas las variables; con una sola confirmada no aplica.
- HU06: SMOTE-ENN solo en entrenamiento, con conteos antes y después.
- Tres folds externos y un test reservado por cliente, sin remuestrear test.
- Tablas, gráfico, reportes JSON, particiones Parquet y un preparador `.joblib`.

No es una prueba de conexión SQL Server/Tailscale. No utiliza el dataset de la
BD, no entrena XGBoost y no genera probabilidades para clientes. El objetivo
heredado `default_12m` sigue siendo una etiqueta sintética para el evento
documentado de atraso de al menos 30 días en los 12 meses posteriores al
desembolso; todavía falta comprobar esa definición con el dataset definitivo
y validar temporalmente el modelo. Las métricas internas de RFECV no son
métricas finales de desempeño bancario.

El pipeline no acepta variables tentativas como confirmadas para forzar un
resultado. Cambiar el tamaño o la semilla puede producir otra selección o un
fallo explícito por evidencia insuficiente. Se recomienda comenzar con los
valores predeterminados.

## Mantenimiento y ejecución local

La lógica de la demo vive en `scripts/demo_colab.py` y reutiliza
`training/run_sprint2.py`; los algoritmos siguen en `training/sprint2.py`.
Las exportaciones contienen una copia de esas fuentes, sin secretos ni datos,
con un manifiesto de integridad. Tras cambiar una fuente incluida:

```powershell
& .\.venv\Scripts\python.exe scripts/build_colab_demo.py
& .\.venv\Scripts\python.exe -m pytest test/test_colab_demo.py
```

Para ejecutar el mismo script autónomo localmente con las dependencias ya instaladas:

```powershell
& .\.venv\Scripts\python.exe colab/demo_sprint2_colab.py --rows 5000 --seed 42
```

Esta entrega se verifica mediante ejecución local del notebook y pruebas de
empaquetado. La ejecución en la infraestructura alojada de Google Colab
debe comprobarse al cargarlo en la cuenta del expositor.
