"""Pruebas HU01 - Ingesta (CP001, CP002, CP010, CP011, CP014)."""
import json

import pandas as pd
import pytest

from training.ingestion import (MSG_SOURCE_DOWN, DataSourceUnavailableError, SchemaValidationError,
                                ingest, main)
from training.security import verify_manifest


@pytest.mark.cp("CP001")
def test_cp001_ingesta_exitosa(source_csv, contract, workdir, raw_df):
    res = ingest(source_csv, contract, out_dir="raw", log_path="logs/ingestion_log.jsonl")
    assert res.report["filas"] == len(raw_df)
    assert res.report["columnas"] == len(contract.columns)
    assert res.output_path.exists() and verify_manifest(res.output_path)
    entry = json.loads(open("logs/ingestion_log.jsonl").read().splitlines()[-1])
    assert entry["estado"] == "OK" and {"fecha_utc", "filas", "columnas", "sha256_fuente"} <= entry.keys()
    assert str(res.df["edad"].dtype) == "Int64" and str(res.df["fecha_solicitud"].dtype).startswith("datetime64")


@pytest.mark.cp("CP002")
def test_cp002_fuente_no_disponible(contract, workdir, capsys):
    with pytest.raises(DataSourceUnavailableError, match="fuente de datos no disponible"):
        ingest(workdir / "inexistente.csv", contract, out_dir="raw", log_path="logs/log.jsonl")
    entry = json.loads(open("logs/log.jsonl").read().splitlines()[-1])
    assert entry["estado"] == "ERROR" and entry["tipo_error"] == "DataSourceUnavailableError"
    assert not (workdir / "raw").exists() or not any((workdir / "raw").iterdir())  # sin dataset parcial
    assert main(["--source", str(workdir / "inexistente.csv")]) == 2
    assert MSG_SOURCE_DOWN in capsys.readouterr().err


def test_cp002b_archivo_vacio(contract, workdir):
    p = workdir / "vacio.csv"; p.write_text("")
    with pytest.raises(DataSourceUnavailableError):
        ingest(p, contract, persist=False, log_path="l.jsonl")


@pytest.mark.cp("CP010")
def test_cp010_contrato_columnas_faltantes(raw_df, contract, workdir):
    p = workdir / "incompleto.csv"
    raw_df.drop(columns=["ingreso_mensual", "plazo_meses"]).to_csv(p, index=False)
    with pytest.raises(SchemaValidationError, match="ingreso_mensual"):
        ingest(p, contract, persist=False, log_path="l.jsonl")


def test_cp010b_objetivo_invalido(raw_df, contract, workdir):
    p = workdir / "obj.csv"
    raw_df.assign(default_12m=raw_df.default_12m.replace({1: 7})).to_csv(p, index=False)
    with pytest.raises(SchemaValidationError, match="objetivo"):
        ingest(p, contract, persist=False, log_path="l.jsonl")


def test_cp010c_formato_no_permitido_y_filas_minimas(raw_df, contract, workdir):
    p = workdir / "x.json"; p.write_text("{}")
    with pytest.raises(SchemaValidationError, match="Formato"):
        ingest(p, contract, persist=False, log_path="l.jsonl")
    q = workdir / "pocas.csv"; raw_df.head(50).to_csv(q, index=False)
    with pytest.raises(SchemaValidationError, match="mínimo"):
        ingest(q, contract, persist=False, log_path="l.jsonl")


def test_ingesta_parquet(raw_df, contract, workdir):
    p = workdir / "s.parquet"; raw_df.to_parquet(p, index=False)
    assert ingest(p, contract, persist=False, log_path="l.jsonl").report["filas"] == len(raw_df)


@pytest.mark.cp("CP011")
def test_cp011_pii_eliminada_y_seudonimizada(source_csv, contract, workdir, raw_df):
    res = ingest(source_csv, contract, persist=False, log_path="logs/l.jsonl")
    assert not {"ruc", "nombre_cliente"} & set(res.df.columns)
    assert not set(raw_df.cliente_id) & set(res.df.cliente_id)          # no quedan IDs originales
    assert res.df.cliente_id.str.fullmatch(r"[0-9a-f]{16}").all()
    log_txt = open("logs/l.jsonl").read()
    assert raw_df.ruc.iloc[0] not in log_txt and raw_df.cliente_id.iloc[0] not in log_txt


@pytest.mark.cp("CP014")
def test_cp014_integridad_manifest(source_csv, contract, workdir):
    res = ingest(source_csv, contract, out_dir="raw", log_path="l.jsonl")
    assert verify_manifest(res.output_path)
    df = pd.read_parquet(res.output_path); df.loc[0, "edad"] = 99
    df.to_parquet(res.output_path, index=False)                         # alteración maliciosa
    assert verify_manifest(res.output_path) is False
