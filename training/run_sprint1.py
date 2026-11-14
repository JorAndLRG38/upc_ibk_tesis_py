"""Orquestador del incremento del Sprint 1: HU01 -> HU02 -> HU03.

Uso:
    python -m training.run_sprint1 --source data/source/solicitudes.csv
"""
from __future__ import annotations

import argparse
import json
import time

from training.common import append_jsonl, load_contract, utc_now
from training.eda import run_eda
from training.ingestion import ingest
from training.preprocessing import persist_artifacts, prepare


def run(source: str, persist: bool = True, eda: bool = True) -> dict:
    contract = load_contract()
    t = {}
    t0 = time.perf_counter(); ing = ingest(source, contract, persist=persist); t["hu01_ingesta_s"] = time.perf_counter() - t0
    if eda:
        t0 = time.perf_counter(); run_eda(ing.df, contract); t["hu02_eda_s"] = time.perf_counter() - t0
    t0 = time.perf_counter(); prep = prepare(ing.df, contract)
    paths = persist_artifacts(prep, contract) if persist else {}
    t["hu03_preparacion_s"] = time.perf_counter() - t0
    t = {k: round(v, 3) for k, v in t.items()}
    t["total_s"] = round(sum(t.values()), 3)
    summary = {"evento": "pipeline_sprint1", "fecha_utc": utc_now(), "tiempos": t,
               "filas_entrada": ing.report["filas"], "columnas_finales": prep.X_train.shape[1], "artefactos": paths}
    append_jsonl("logs/pipeline_log.jsonl", summary)
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    a = ap.parse_args()
    print(json.dumps(run(a.source), indent=2, ensure_ascii=False))
