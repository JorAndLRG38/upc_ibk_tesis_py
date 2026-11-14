"""Demostracion CPU de HU04-HU06 con el mismo codigo del proyecto.

La exportacion autonoma para Colab se genera con scripts/build_colab_demo.py.
Solo genera datos sinteticos; no acepta fuentes bancarias ni consulta SQL.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ''):
    sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from scripts.generate_synthetic_dataset import generate
from training.run_sprint2 import run_demo
from training.sprint2 import Sprint2Config


def create_figure(report: dict, path: Path) -> None:
    final = report['ajuste_final']
    counts = final['hu06']
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout='constrained')
    bars = axes[0].bar(['Entrada', 'Boruta', 'RFECV'],
                       [len(final['configuracion']['features']),
                        len(final['hu04']['confirmadas']), len(final['hu05']['seleccionadas'])],
                       color=['#7c8da4', '#2d718e', '#249c88'])
    axes[0].bar_label(bars, padding=4)
    axes[0].set(title='Selección de variables', ylabel='Número de variables')
    axes[0].set_ylim(0, max(len(final['configuracion']['features']) + 2, 4))
    for offset, label, key, color in [(-.18, 'Antes', 'antes', '#2d718e'),
                                      (.18, 'Después', 'despues', '#249c88')]:
        bars = axes[1].bar([offset, 1 + offset], [counts[key]['0'], counts[key]['1']],
                           width=.36, label=label, color=color)
        axes[1].bar_label(bars, padding=4)
    axes[1].set_xticks([0, 1], ['Clase 0', 'Clase 1'])
    axes[1].set(title='SMOTE-ENN: solo entrenamiento', ylabel='Número de filas')
    axes[1].margins(y=.2)
    axes[1].legend()
    for ax in axes:
        ax.spines[['top', 'right']].set_visible(False)
    fig.suptitle('Prueba sintética • default_12m • sin predictor final', fontsize=13)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def execute_demo(rows: int = 5000, seed: int = 42,
                 output_root: str | Path = 'artifacts/colab') -> dict:
    if type(rows) is not int or rows < 1000:
        raise ValueError('Use al menos 1000 filas para esta prueba; recomendado: 5000.')
    if type(seed) is not int or seed < 0:
        raise ValueError('La semilla debe ser un entero no negativo.')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8]
    workspace = Path(output_root).resolve() / run_id
    workspace.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    old_salt = os.environ.get('RISK_PSEUDO_SALT')
    os.environ['RISK_PSEUDO_SALT'] = 'solo-prueba-colab-datos-sinteticos'
    try:
        print(f'1/3 Generando {rows} filas sintéticas más duplicados controlados...', flush=True)
        source = workspace / 'solicitudes_demo.csv'
        data = generate(rows, seed)
        data.to_csv(source, index=False)
        config = replace(Sprint2Config.load(), seed=seed)
        print('2/3 Ejecutando Boruta, RFECV y SMOTE-ENN por partición...', flush=True)
        result = run_demo(source, config, workspace / 'resultados')
        destination = Path(result['directorio'])
        report = json.loads((destination / 'reporte_sprint2.json').read_text(encoding='utf-8'))
        print('3/3 Preparando gráfico y archivos para la exposición...', flush=True)
        create_figure(report, destination / 'resumen_visual.png')
        requirements = ROOT / 'requirements-colab.txt'
        shutil.copy2(requirements, destination / requirements.name)
        bundle_manifest = ROOT / 'colab_bundle_manifest.json'
        if bundle_manifest.exists():
            shutil.copy2(bundle_manifest, destination / bundle_manifest.name)
        final = report['ajuste_final']
        summary = {
            'estado': 'OK_DEMO_SINTETICA',
            'filas_generadas_incluidos_duplicados': len(data),
            'filas_entrenamiento_original': final['train_filas'],
            'filas_test_sin_remuestreo': report['particion']['filas_test'],
            'clientes_compartidos_train_test': report['particion']['clientes_compartidos'],
            'folds_externos_ejecutados': len(report['folds_externos']),
            'boruta_confirmadas': final['hu04']['confirmadas'],
            'rfecv_estado': final['hu05']['estado'],
            'rfecv_seleccionadas': final['hu05']['seleccionadas'],
            'clases_antes': final['hu06']['antes'],
            'clases_despues': final['hu06']['despues'],
            'duracion_segundos': round(time.perf_counter() - started, 2),
            'objetivo': report['objetivo_columna'],
            'objetivo_tesis_90_dias_validado': False,
            'conexion_bd_validada': False,
            'predictor_entrenado': False,
            'directorio': str(destination),
            'zip': str(workspace / 'resultados_demo.zip'),
        }
        (destination / 'resumen_demo.json').write_text(
            json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
        (destination / 'GUIA_EXPOSICION.md').write_text('''# Qué explicar durante la prueba

1. Estamos ejecutando una prueba de laboratorio con datos generados, no registros bancarios.
2. La ingesta valida, seudonimiza y limpia antes de reservar clientes para test.
3. HU04 usa Boruta para identificar variables confirmadas; las tentativas se informan aparte.
4. HU05 aplica RFECV al subconjunto. Puede conservar todas las variables; su curva interna
   no demuestra el desempeño de un predictor. Con una sola variable se informa que no aplica.
5. HU06 aplica SMOTE-ENN solo a entrenamiento. Validación y test conservan sus filas.
6. Se ejecutan tres folds externos y un ajuste final en desarrollo. El ZIP deja evidencia.

Esta prueba no consulta SQL Server, no comprueba Tailscale y no entrena XGBoost.
El objetivo heredado default_12m representa una etiqueta simulada de atraso de al menos
30 días en 12 meses. Todavía falta construir snapshots y la etiqueta de al menos un día
de atraso en los siguientes 90 días, integrar la BD, entrenar y evaluar el modelo final.
No se generan probabilidades para clientes ni métricas de desempeño bancario.
''', encoding='utf-8')
        shutil.make_archive(str(workspace / 'resultados_demo'), 'zip', root_dir=destination)
        return summary
    finally:
        if old_salt is None:
            os.environ.pop('RISK_PSEUDO_SALT', None)
        else:
            os.environ['RISK_PSEUDO_SALT'] = old_salt


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Demo sintética CPU: Boruta, RFECV y SMOTE-ENN')
    parser.add_argument('--rows', type=int, default=5000)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output-root', type=Path, default=Path('artifacts/colab'))
    parser.add_argument('--summary-file', type=Path, help='Ruta opcional del JSON para el notebook')
    args = parser.parse_args(argv)
    summary = execute_demo(args.rows, args.seed, args.output_root)
    if args.summary_file:
        args.summary_file.parent.mkdir(parents=True, exist_ok=True)
        args.summary_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
