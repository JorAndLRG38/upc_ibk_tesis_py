"""Controles de seguridad de la información aplicados al pipeline.

Referencia: ISO/IEC 27001:2022, Anexo A
  - 5.12 Clasificación de la información (contrato marca columnas PII)
  - 5.34 Privacidad y protección de PII (Ley N.° 29733 en Perú)
  - 8.11 Enmascaramiento de datos (seudonimización HMAC-SHA256)
  - 8.15 Registro (logs sin PII)
  - 8.24 Uso de criptografía (hash de integridad SHA-256)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from pathlib import Path

import pandas as pd

SALT_ENV = "RISK_PSEUDO_SALT"
_DEV_SALT = "solo-desarrollo-cambiar-en-entorno-real"

# Patrones de PII peruana: RUC 10/20 (11 dígitos), DNI (8 dígitos), correo, celular
PII_PATTERNS = {
    "ruc": re.compile(r"^(10|20)\d{9}$"),
    "dni": re.compile(r"^\d{8}$"),
    "correo": re.compile(r"^[\w.+-]+@[\w-]+\.[\w.]+$"),
    "celular": re.compile(r"^9\d{8}$"),
}


class SecurityError(RuntimeError):
    """Se detectó información personal donde no debería existir."""


def _salt() -> bytes:
    return os.environ.get(SALT_ENV, _DEV_SALT).encode()


def pseudonymize_series(s: pd.Series) -> pd.Series:
    """HMAC-SHA256 truncado a 16 hex: irreversible sin la sal, determinista para joins."""
    key = _salt()
    return s.astype(str).map(lambda v: hmac.new(key, v.encode(), hashlib.sha256).hexdigest()[:16])


def protect(df: pd.DataFrame, drop_cols: list[str], pseudo_cols: list[str]) -> tuple[pd.DataFrame, dict]:
    present_drop = [c for c in drop_cols if c in df.columns]
    out = df.drop(columns=present_drop)
    for c in pseudo_cols:
        if c in out.columns:
            out[c] = pseudonymize_series(out[c])
    return out, {"pii_eliminadas": present_drop, "seudonimizadas": [c for c in pseudo_cols if c in df.columns]}


def scan_pii(df: pd.DataFrame, sample: int = 2000) -> dict[str, list[str]]:
    """Busca valores con forma de PII en columnas de texto. Devuelve {columna: [tipos]}."""
    found: dict[str, list[str]] = {}
    for col in df.select_dtypes(include=["object", "string", "category"]).columns:
        vals = df[col].dropna().astype(str).head(sample)
        if vals.empty:
            continue
        hits = [k for k, rx in PII_PATTERNS.items() if vals.str.match(rx).mean() > 0.5]
        if hits:
            found[col] = hits
    return found


def assert_no_pii(df: pd.DataFrame, forbidden_cols: list[str]) -> None:
    leaked = [c for c in forbidden_cols if c in df.columns]
    pattern_hits = scan_pii(df)
    if leaked or pattern_hits:
        raise SecurityError(f"PII detectada. Columnas prohibidas: {leaked}; patrones: {pattern_hits}")


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def write_manifest(artifact: str | Path, meta: dict) -> Path:
    artifact = Path(artifact)
    manifest = artifact.with_suffix(artifact.suffix + ".manifest.json")
    payload = {"artefacto": artifact.name, "sha256": sha256_file(artifact), **meta}
    manifest.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return manifest


def verify_manifest(artifact: str | Path) -> bool:
    artifact = Path(artifact)
    manifest = artifact.with_suffix(artifact.suffix + ".manifest.json")
    expected = json.loads(manifest.read_text(encoding="utf-8"))["sha256"]
    return hmac.compare_digest(expected, sha256_file(artifact))
