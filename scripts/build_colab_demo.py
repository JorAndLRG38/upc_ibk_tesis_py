"""Genera los entregables autónomos de la demo de Sprint 2.

``SOURCE_FILES`` mantiene la lista explícita de fuentes del pipeline que se
copian al bundle; no duplica los algoritmos. El bundle añade un
``scripts/__init__.py`` generado porque la demo exportada importa módulos de
``scripts`` aunque el repositorio no necesita archivos ``__init__.py``.

Ejecutar otra vez tras modificar cualquiera de las fuentes incluidas.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = (
    'requirements-colab.txt',
    'training/common.py', 'training/security.py',
    'training/ingestion.py', 'training/preprocessing.py', 'training/sprint2.py',
    'training/run_sprint2.py', 'training/config/data_contract.yaml',
    'training/config/sprint2.yaml',
    'scripts/generate_synthetic_dataset.py', 'scripts/demo_colab.py',
)

BOOTSTRAP = '''"""Demo autonoma de HU04-HU06, exportada desde el proyecto UPC.

Google Colab o Python >=3.11, CPU:
    python demo_sprint2_colab.py --install

--install instala requirements-colab.txt antes de ejecutar en un proceso nuevo.
Sin ese argumento se utilizan las dependencias ya instaladas.
Contiene una copia comprimida y verificable del codigo, sin datos ni secretos.
Para regenerarla: python scripts/build_colab_demo.py en el repositorio original.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

BUNDLE_SHA256 = __SHA256__
BUNDLE_BASE64 = __BUNDLE__


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--install', action='store_true')
    options, remaining = parser.parse_known_args()
    if sys.version_info < (3, 11):
        raise RuntimeError('Esta demo necesita Python 3.11 o posterior.')
    archive_bytes = base64.b64decode(BUNDLE_BASE64, validate=True)
    if hashlib.sha256(archive_bytes).hexdigest() != BUNDLE_SHA256:
        raise RuntimeError('El paquete de codigo esta incompleto o fue modificado.')
    with tempfile.TemporaryDirectory(prefix='upc_colab_codigo_') as temporary:
        root = Path(temporary).resolve()
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            manifest = json.loads(archive.read('colab_bundle_manifest.json'))
            expected = set(manifest['sha256']) | {'colab_bundle_manifest.json'}
            if set(archive.namelist()) != expected or len(archive.namelist()) != len(expected):
                raise RuntimeError('Lista de archivos del paquete invalida.')
            for name in archive.namelist():
                destination = (root / name).resolve()
                if not destination.is_relative_to(root):
                    raise RuntimeError('Ruta invalida dentro del paquete.')
                content = archive.read(name)
                if name in manifest['sha256']:
                    if hashlib.sha256(content).hexdigest() != manifest['sha256'][name]:
                        raise RuntimeError('Una fuente no coincide con su manifiesto.')
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
        if options.install:
            print('Instalando/verificando dependencias de la demo...', flush=True)
            subprocess.run([sys.executable, '-m', 'pip', 'install', '--quiet',
                            '--disable-pip-version-check', '-r',
                            str(root / 'requirements-colab.txt')], check=True)
        # El proceso nuevo evita reutilizar imports anteriores a la instalacion.
        # El directorio de trabajo se conserva: los resultados no van al temporal.
        child_env = os.environ.copy()
        child_env['PYTHONIOENCODING'] = 'utf-8'
        result = subprocess.run([sys.executable, '-u', str(root / 'scripts/demo_colab.py'),
                                 *remaining], env=child_env)
        return result.returncode


if __name__ == '__main__':
    sys.exit(main())
'''


def build(output_root: Path | None = None) -> tuple[Path, Path]:
    destination = output_root or ROOT
    # Normalizar LF mantiene la exportacion estable entre checkouts Windows/Linux.
    payload = {name: (ROOT / name).read_text(encoding='utf-8').encode('utf-8')
               for name in SOURCE_FILES}
    payload['scripts/__init__.py'] = b'"""Scripts de demostracion del proyecto."""\n'
    manifest = {'tipo': 'FUENTES_DEMO_SINTETICA_HU04_HU06',
                'sha256': {name: hashlib.sha256(data).hexdigest() for name, data in payload.items()}}
    payload['colab_bundle_manifest.json'] = json.dumps(
        manifest, ensure_ascii=False, indent=2).encode('utf-8')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for name, content in sorted(payload.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
    raw = buffer.getvalue()
    script = BOOTSTRAP.replace('__SHA256__', repr(hashlib.sha256(raw).hexdigest())).replace(
        '__BUNDLE__', repr(base64.b64encode(raw).decode('ascii')))
    script_path = destination / 'colab/demo_sprint2_colab.py'
    notebook_path = destination / 'notebooks/demo_sprint2_colab.ipynb'
    script_path.parent.mkdir(parents=True, exist_ok=True)
    notebook_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(script, encoding='utf-8')
    cells = []

    def md(source):
        cells.append({'cell_type': 'markdown', 'metadata': {}, 'source': source})

    def code(source, *, hidden=False):
        cells.append({'cell_type': 'code', 'execution_count': None, 'outputs': [],
                      'metadata': {'cellView': 'form'} if hidden else {}, 'source': source})

    md('''# Prueba inicial del Sprint 2 · UPC

**Boruta (HU04) → RFECV (HU05) → SMOTE-ENN (HU06)**

Sube este notebook a Google Colab y ejecuta las celdas en orden. Usa CPU;
no necesitas GPU, acceso a GitHub, SQL Server, Tailscale ni un archivo de datos.
La instalación de dependencias requiere acceso a Internet.

La prueba genera **5000 registros sintéticos y duplicados controlados** con el
generador del proyecto. Ejecuta el mismo pipeline, con tres folds externos y
un test reservado por cliente. El tiempo depende de los recursos de la sesión.

**Alcance:** aún utiliza `default_12m` (etiqueta simulada de atraso ≥30 días en
12 meses). No valida el objetivo de atraso ≥1 día en los próximos 90 días en
créditos vigentes. No entrena XGBoost ni produce probabilidades de clientes.
''')
    md('''## 1. Preparar el script

Esta celda contiene una copia del código necesario, empaquetada con hashes
SHA-256. Solo extrae fuentes y configuración de laboratorio; no incluye `.env`,
contraseñas, datasets ni modelos. El archivo también puede ejecutarse como `.py`.
''')
    code('#@title Preparar el código del proyecto\n'
         'from pathlib import Path\nimport tempfile\n'
         'carpeta_sesion = Path(tempfile.mkdtemp(prefix="upc_demo_colab_"))\n'
         'script_demo = carpeta_sesion / "demo_sprint2_colab.py"\n'
         f'script_demo.write_text({script!r}, encoding="utf-8")\n'
         'print("Código preparado. Continúa con la ejecución.")', hidden=True)
    md('''## 2. Ejecutar la prueba

Se generan datos, se validan y limpian, y se separan clientes de entrenamiento
y test. Cada fold vuelve a ajustar Boruta, RFECV, imputación y escala; SMOTE-ENN
solo modifica entrenamiento. El test conserva su tamaño y distribución.

RFECV puede conservar todas las variables confirmadas por Boruta. Si Boruta
solo confirma una, se informa que RFECV no aplica. Si no confirma ninguna,
se informa el error en lugar de inventar una selección.
''')
    code('''# Parámetros de la prueba: mantener estos valores para la exposición inicial.
FILAS = 5000
SEMILLA = 42
INSTALAR_DEPENDENCIAS = True

import json
import subprocess
import sys

salida_json = carpeta_sesion / "resumen_demo.json"
comando = [sys.executable, "-u", str(script_demo),
           "--rows", str(FILAS), "--seed", str(SEMILLA),
           "--output-root", str(carpeta_sesion / "resultados"),
           "--summary-file", str(salida_json)]
if INSTALAR_DEPENDENCIAS:
    comando.append("--install")
with subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                      text=True, encoding="utf-8", errors="replace") as proceso:
    for linea in proceso.stdout:
        print(linea.rstrip(), flush=True)
    estado = proceso.wait()
if estado:
    raise RuntimeError(f"La prueba no terminó correctamente (código {estado}). Revisa el error anterior.")
resumen = json.loads(salida_json.read_text(encoding="utf-8"))
carpeta_resultados = Path(resumen["directorio"])
print("\\nOK: prueba sintética completada; no implica validación bancaria.")
''')
    md('''## 3. Revisar las evidencias de HU04, HU05 y HU06

**Boruta:** identifica variables confirmadas, tentativas y rechazadas.
**RFECV:** evalúa subconjuntos mediante Average Precision interna.
**SMOTE-ENN:** genera ejemplos sintéticos de entrenamiento y elimina vecinos
ambiguos; no garantiza clases finales del mismo tamaño.
''')
    code('''import csv
from html import escape
from IPython.display import HTML, Markdown, display

def mostrar_csv(nombre, titulo):
    with (carpeta_resultados / nombre).open(encoding="utf-8", newline="") as archivo:
        filas = list(csv.reader(archivo))
    display(Markdown("### " + titulo))
    if len(filas) < 2:
        display(Markdown("Sin curva: revisar el estado de RFECV en el reporte."))
        return
    encabezado = "".join("<th>" + escape(c) + "</th>" for c in filas[0])
    cuerpo = "".join("<tr>" + "".join("<td>" + escape(c) + "</td>" for c in fila)
                     + "</tr>" for fila in filas[1:])
    display(HTML("<table><thead><tr>" + encabezado + "</tr></thead><tbody>" + cuerpo + "</tbody></table>"))

mostrar_csv("boruta_variables.csv", "HU04 · Boruta")
mostrar_csv("rfecv_variables.csv", "HU05 · RFECV")
mostrar_csv("balance_clases.csv", "HU06 · SMOTE-ENN")
display(Markdown(f"**Test sin remuestrear:** {resumen['filas_test_sin_remuestreo']} filas. "
                 f"**Clientes compartidos con desarrollo:** {resumen['clientes_compartidos_train_test']}."))
''')
    md('''## 4. Mostrar el gráfico

Los conteos muestran lo que ocurrió en esta ejecución; no son métricas de
exactitud, AUC ni capacidad de anticipar atrasos reales.
''')
    code('''from IPython.display import Image, display
display(Image(filename=str(carpeta_resultados / "resumen_visual.png")))
''')
    md('''## 5. Descargar resultados

El ZIP incluye los reportes JSON, CSV de selección y balanceo, gráfico,
particiones sintéticas Parquet, preparador y manifiestos. El `.joblib` es un
preparador de variables, no un predictor. Descarga los resultados antes de
cerrar la sesión, porque el almacenamiento del entorno es temporal.
''')
    code('''archivo_zip = Path(resumen["zip"])
print("Resultados:", archivo_zip)
try:
    from google.colab import files
except ImportError:
    from IPython.display import FileLink, display
    display(FileLink(str(archivo_zip)))
else:
    files.download(str(archivo_zip))
''')
    md('''## Cierre sugerido para la exposición

> Hemos ejecutado una primera base funcional de Boruta, RFECV y SMOTE-ENN
> con datos sintéticos. La selección y el remuestreo se ajustan en entrenamiento;
> validación y test conservan sus filas. Seguimos desarrollando la integración
> con la base de datos, el objetivo de atraso de un día en 90 días y el
> entrenamiento y evaluación de XGBoost. Esta ejecución demuestra el flujo
> técnico; todavía no valida la capacidad de evaluar clientes reales.

El alcance actual es el seguimiento de **créditos vigentes**. La evaluación
de nuevas solicitudes queda como ampliación futura.

Referencia de uso: [FAQ oficial de Google Colab](https://research.google.com/colaboratory/faq.html).
''')
    for i, cell in enumerate(cells):
        cell['id'] = f'upc-demo-{i:02d}'
    notebook = {'nbformat': 4, 'nbformat_minor': 5, 'cells': cells,
                'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python',
                                           'name': 'python3'},
                             'language_info': {'name': 'python'},
                             'colab': {'name': notebook_path.name, 'provenance': []}}}
    notebook_path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return script_path, notebook_path


if __name__ == '__main__':
    for output in build():
        print(output)
