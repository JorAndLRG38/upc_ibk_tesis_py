"""La exportacion debe ser reproducible, portable y contener solo fuentes."""
import base64
import hashlib
import io
import json
import runpy
import subprocess
import sys
import zipfile

from scripts.build_colab_demo import ROOT, SOURCE_FILES, build


def test_colab_bundle_has_only_current_sources(tmp_path):
    script, notebook = build(tmp_path)
    exported = runpy.run_path(str(script), run_name='inspect_export')
    raw = base64.b64decode(exported['BUNDLE_BASE64'], validate=True)
    assert hashlib.sha256(raw).hexdigest() == exported['BUNDLE_SHA256']
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert set(archive.namelist()) == set(SOURCE_FILES) | {
            'scripts/__init__.py', 'colab_bundle_manifest.json'}
        manifest = json.loads(archive.read('colab_bundle_manifest.json'))
        for name in SOURCE_FILES:
            content = archive.read(name)
            assert content == (ROOT / name).read_text(encoding='utf-8').encode('utf-8')
            assert hashlib.sha256(content).hexdigest() == manifest['sha256'][name]
    # Los archivos entregados no deben quedarse desactualizados frente al proyecto.
    assert script.read_text(encoding='utf-8') == (ROOT / 'colab/demo_sprint2_colab.py').read_text(encoding='utf-8')
    assert notebook.read_text(encoding='utf-8') == (ROOT / 'notebooks/demo_sprint2_colab.ipynb').read_text(encoding='utf-8')
    nb = json.loads(notebook.read_text(encoding='utf-8'))
    for cell in nb['cells']:
        if cell['cell_type'] == 'code':
            assert cell['outputs'] == []
            assert cell['execution_count'] is None


def test_standalone_script_can_start_outside_repository(tmp_path):
    script, _ = build(tmp_path / 'export')
    # -I excluye PYTHONPATH y la carpeta actual; el paquete debe bastar por si solo.
    result = subprocess.run([sys.executable, '-I', str(script), '--help'],
                            cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert '--rows' in result.stdout
    assert '--summary-file' in result.stdout
    assert not (tmp_path / 'artifacts').exists()


def test_failed_demo_does_not_return_success_summary(tmp_path):
    script, _ = build(tmp_path / 'export')
    summary = tmp_path / 'summary.json'
    result = subprocess.run([sys.executable, '-I', str(script), '--rows', '1',
                             '--summary-file', str(summary)], cwd=tmp_path,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode != 0
    assert not summary.exists()
    assert 'OK_DEMO_SINTETICA' not in result.stdout
