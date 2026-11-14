"""HU01 - Ingesta del dataset base (EP01).

Tareas del Sprint Backlog cubiertas:
  TK-01.1 Configurar conexión a la fuente del dataset  -> SourceConfig / _read_source
  TK-01.2 Desarrollar script de ingesta en Python       -> ingest() y CLI
  TK-01.3 Validar número de filas, columnas y tipos     -> validate_schema()
  TK-01.4 Generar log de ingesta y versionar dataset    -> append_jsonl() + write_manifest()

Uso:
    python -m training.ingestion --source data/source/solicitudes.csv
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from training.common import Contract, append_jsonl, get_logger, load_contract, utc_now
from training.security import assert_no_pii, protect, sha256_file, write_manifest

log = get_logger("ingestion")
MSG_SOURCE_DOWN = "Error: fuente de datos no disponible. Verifique la conexión"


class DataSourceUnavailableError(RuntimeError):
    pass


class SchemaValidationError(ValueError):
    pass


@dataclass
class IngestionResult:
    df: pd.DataFrame
    report: dict = field(default_factory=dict)
    output_path: Path | None = None


# ---------------------------------------------------------------- TK-01.1
def _read_source(source: Path, contract: Contract) -> pd.DataFrame:
    fmt = source.suffix.lower().lstrip(".")
    allowed = contract.raw["dataset"]["formato_permitido"]
    if fmt not in allowed:
        raise SchemaValidationError(f"Formato '{fmt}' no permitido. Use: {allowed}")
    if not source.exists() or source.stat().st_size == 0:
        raise DataSourceUnavailableError(MSG_SOURCE_DOWN)
    try:
        if fmt == "csv":
            ds = contract.raw["dataset"]
            return pd.read_csv(source, sep=ds["separador_csv"], encoding=ds["encoding"], low_memory=False)
        if fmt == "parquet":
            return pd.read_parquet(source)
        return pd.read_excel(source)
    except (OSError, pd.errors.EmptyDataError) as exc:
        raise DataSourceUnavailableError(MSG_SOURCE_DOWN) from exc


# ---------------------------------------------------------------- TK-01.3
_CASTERS = {
    "int": lambda s: pd.to_numeric(s, errors="coerce").astype("Int64"),
    "float": lambda s: pd.to_numeric(s, errors="coerce").astype("float64"),
    "string": lambda s: s.astype("string"),
    "category": lambda s: s.astype("string"),
    "ordinal": lambda s: s.astype("string"),
    "date": lambda s: pd.to_datetime(s, errors="coerce"),
    "bool": lambda s: s.map({True: True, False: False, "True": True, "False": False,
                             1: True, 0: False, "1": True, "0": False}).astype("boolean"),
}


def validate_schema(df: pd.DataFrame, contract: Contract) -> tuple[pd.DataFrame, dict]:
    expected = list(contract.columns)
    missing = [c for c in expected if c not in df.columns]
    if missing:
        raise SchemaValidationError(f"Columnas requeridas ausentes: {missing}")
    min_rows = contract.raw["dataset"]["min_filas"]
    if len(df) < min_rows:
        raise SchemaValidationError(f"El dataset tiene {len(df)} filas; mínimo requerido {min_rows}")

    out = df[expected].copy()
    coercion_nulls = {}
    for col, spec in contract.columns.items():
        before = out[col].isna().sum()
        out[col] = _CASTERS[spec["tipo"]](out[col])
        coercion_nulls[col] = int(out[col].isna().sum() - before)

    tgt = contract.target
    bad_target = ~out[tgt].isin(contract.raw["objetivo"]["valores_validos"])
    if bad_target.any():
        raise SchemaValidationError(f"Variable objetivo '{tgt}' con {int(bad_target.sum())} valores inválidos")

    extra = [c for c in df.columns if c not in expected]
    return out, {"columnas_esperadas": len(expected), "columnas_extra_descartadas": extra,
                 "valores_no_convertibles": {k: v for k, v in coercion_nulls.items() if v}}


# ---------------------------------------------------------------- TK-01.2 / TK-01.4
def ingest(source: str | Path, contract: Contract | None = None, out_dir: str | Path = "data/raw",
           log_path: str | Path = "logs/ingestion_log.jsonl", persist: bool = True) -> IngestionResult:
    contract = contract or load_contract()
    source = Path(source)
    t0 = time.perf_counter()
    entry = {"evento": "ingesta", "fecha_utc": utc_now(), "fuente": source.name}
    try:
        raw = _read_source(source, contract)
        protected, sec = protect(raw, contract.drop_pii, contract.pseudonymize)
        df, schema = validate_schema(protected, contract)
        assert_no_pii(df, contract.drop_pii)
    except Exception as exc:  # se registra y se relanza: no se genera dataset parcial
        entry.update(estado="ERROR", tipo_error=type(exc).__name__, mensaje=str(exc),
                     duracion_s=round(time.perf_counter() - t0, 3))
        append_jsonl(log_path, entry)
        log.error(str(exc))
        raise

    report = {"filas": len(df), "columnas": df.shape[1], "sha256_fuente": sha256_file(source),
              **schema, **sec}
    out_path = None
    if persist:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = utc_now().replace(":", "").replace("-", "")
        out_path = out_dir / f"dataset_base_{stamp}.parquet"
        df.to_parquet(out_path, index=False)
        write_manifest(out_path, {"fuente": source.name, "filas": len(df), "columnas": df.shape[1],
                                  "version_contrato": contract.raw["dataset"]["version_contrato"],
                                  "fecha_utc": entry["fecha_utc"]})
        report["salida"] = str(out_path)
    entry.update(estado="OK", duracion_s=round(time.perf_counter() - t0, 3),
                 **{k: v for k, v in report.items() if k != "valores_no_convertibles"})
    append_jsonl(log_path, entry)
    log.info("Ingesta OK: %s filas, %s columnas (%.2f s)", f"{len(df):,}", df.shape[1], entry["duracion_s"])
    return IngestionResult(df=df, report=report, output_path=out_path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HU01 - Ingesta del dataset base")
    ap.add_argument("--source", required=True)
    ap.add_argument("--contract", default=None)
    ap.add_argument("--out-dir", default="data/raw")
    a = ap.parse_args(argv)
    try:
        ingest(a.source, load_contract(a.contract) if a.contract else None, a.out_dir)
    except DataSourceUnavailableError:
        print(MSG_SOURCE_DOWN, file=sys.stderr)
        return 2
    except (SchemaValidationError, ValueError) as exc:
        print(f"Error de validación: {exc}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
