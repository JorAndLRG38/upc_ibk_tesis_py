"""Medición de MC2 (rendimiento) y MC3 (escalabilidad) del incremento del Sprint 1.

Ejecuta HU01 + HU03 (sin gráficos) sobre volúmenes crecientes de datos sintéticos y registra
tiempo total y memoria pico. El exponente b de t = a * n^b estima la escalabilidad
(b ~= 1 indica crecimiento lineal).
"""
from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from generate_synthetic_dataset import generate  # noqa: E402
from training.common import load_contract  # noqa: E402
from training.ingestion import ingest  # noqa: E402
from training.preprocessing import prepare  # noqa: E402

SIZES = [int(x) for x in os.environ.get("BENCH_SIZES", "25000,50000,100000,200000").split(",")]
REPS = int(os.environ.get("BENCH_REPS", "3"))


def one_run(src: Path, contract) -> tuple[float, float]:
    tracemalloc.start()
    t0 = time.perf_counter()
    res = ingest(src, contract, persist=False, log_path=src.parent / "l.jsonl")
    prepare(res.df, contract)
    dt = time.perf_counter() - t0
    peak = tracemalloc.get_traced_memory()[1] / 2**20
    tracemalloc.stop()
    return dt, peak


def main() -> None:
    contract = load_contract()
    rows = []
    with tempfile.TemporaryDirectory() as d:
        for n in SIZES:
            src = Path(d) / f"s{n}.csv"
            generate(n, seed=3).to_csv(src, index=False)
            runs = [one_run(src, contract) for _ in range(REPS)]
            t = float(np.median([r[0] for r in runs])); m = float(np.median([r[1] for r in runs]))
            rows.append({"n": n, "tiempo_s": round(t, 2), "memoria_pico_mb": round(m, 1),
                         "ms_por_1000_filas": round(1000 * t / n * 1000, 2)})
            print(rows[-1], flush=True)
    b, _ = np.polyfit(np.log([r["n"] for r in rows]), np.log([r["tiempo_s"] for r in rows]), 1)
    bm, _ = np.polyfit(np.log([r["n"] for r in rows]), np.log([r["memoria_pico_mb"] for r in rows]), 1)
    out = {"entorno": {"python": platform.python_version(), "cpu": os.cpu_count(),
                       "so": platform.platform()}, "repeticiones": REPS, "mediciones": rows,
           "exponente_tiempo_b": round(float(b), 3), "exponente_memoria": round(float(bm), 3)}
    Path("reports/quality").mkdir(parents=True, exist_ok=True)
    Path("reports/quality/benchmark_sprint1.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
