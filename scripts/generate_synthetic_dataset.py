"""Generador de dataset SINTÉTICO para pruebas del pipeline (no es data real).

Reproduce la estructura del contrato de datos (training/config/data_contract.yaml)
con defectos de calidad controlados (faltantes, inconsistencias, duplicados y
valores atípicos) para poder probar HU01, HU02 y HU03 sin datos del banco.

Uso:
    python scripts/generate_synthetic_dataset.py --n 100000 --out data/source/solicitudes.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

DEPARTAMENTOS = ["Lima", "Arequipa", "La Libertad", "Piura", "Lambayeque", "Cusco", "Junin",
                 "Ica", "Ancash", "Cajamarca", "Puno", "Loreto", "San Martin", "Tacna",
                 "Ucayali", "Ayacucho", "Huanuco", "Callao", "Moquegua", "Tumbes"]
ACTIVIDADES = ["Bodega", "Ferreteria", "Restaurante", "Transporte de pasajeros", "Textil",
               "Panaderia", "Farmacia", "Libreria", "Taller mecanico", "Peluqueria",
               "Venta de abarrotes", "Venta de ropa", "Carpinteria", "Agricultura",
               "Mototaxi", "Comercio ambulatorio formal", "Lavanderia", "Cabinas internet"]


def generate(n: int, seed: int = 42, default_rate_target: float = 0.09) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    edad = rng.normal(42, 11, n).clip(18, 80).round().astype(int)
    antig = rng.gamma(2.2, 30, n).clip(0, 480).round().astype(int)
    ingreso = np.exp(rng.normal(8.0, 0.55, n)).round(2)
    ventas = (ingreso * rng.uniform(2.5, 6.0, n)).round(2)
    monto = (ingreso * rng.uniform(0.8, 4.0, n)).clip(300, 200000).round(2)
    plazo = rng.choice([6, 9, 12, 18, 24, 36], n, p=[.10, .10, .30, .20, .20, .10])
    n_ent = rng.poisson(1.6, n)
    deuda = (n_ent * ingreso * rng.uniform(0.3, 2.5, n)).round(2)
    atraso = np.where(rng.random(n) < 0.72, 0, rng.gamma(1.3, 14, n)).round().astype(int)
    calif = np.select([atraso > 120, atraso > 60, atraso > 30, atraso > 8],
                      ["Perdida", "Dudoso", "Deficiente", "CPP"], "Normal")
    garantia = rng.random(n) < 0.18
    dep = rng.choice(DEPARTAMENTOS, n, p=np.r_[0.30, np.full(19, 0.70 / 19)])
    act = rng.choice(ACTIVIDADES, n)
    fecha = pd.to_datetime("2023-01-01") + pd.to_timedelta(rng.integers(0, 3 * 365, n), unit="D")

    # Riesgo latente (relaciones no lineales e interacciones a propósito)
    endeud = deuda / (ingreso * 12)
    cuota_ratio = (monto / plazo) / ingreso
    logit = (-3.4 + 0.035 * atraso + 1.1 * np.tanh(endeud) + 0.9 * (cuota_ratio > 0.45)
             - 0.006 * antig - 0.012 * (edad - 42) + 0.25 * n_ent
             - 0.45 * garantia + 0.4 * np.isin(act, ["Mototaxi", "Comercio ambulatorio formal"])
             + 0.25 * np.sin(fecha.month.to_numpy() / 12 * 2 * np.pi))
    p = 1 / (1 + np.exp(-logit))
    p = p * default_rate_target / p.mean()
    y = (rng.random(n) < p.clip(0, 1)).astype(int)

    df = pd.DataFrame({
        "cliente_id": [f"CLI{idx:07d}" for idx in range(n)],
        "ruc": [f"10{rng.integers(10**8, 10**9)}" for _ in range(n)],
        "nombre_cliente": "NOMBRE SINTETICO",
        "fecha_solicitud": fecha.strftime("%Y-%m-%d"),
        "edad": edad,
        "estado_civil": rng.choice(["Soltero", "Casado", "Conviviente", "Divorciado", "Viudo"], n),
        "nivel_educativo": rng.choice(["Primaria", "Secundaria", "Tecnico", "Universitario"], n),
        "departamento": dep, "actividad_economica": act,
        "tipo_vivienda": rng.choice(["Propia", "Alquilada", "Familiar"], n, p=[.45, .30, .25]),
        "canal_originacion": rng.choice(["Agencia", "Digital", "Fuerza de ventas"], n),
        "antiguedad_negocio_meses": antig, "ingreso_mensual": ingreso,
        "ventas_mensuales": ventas, "monto_solicitado": monto, "plazo_meses": plazo,
        "tasa_interes_anual": rng.uniform(18, 75, n).round(2), "n_entidades_sbs": n_ent,
        "deuda_total_sbs": deuda, "max_dias_atraso_12m": atraso,
        "n_creditos_previos": rng.poisson(2.5, n), "calificacion_sbs": calif,
        "tiene_garantia": garantia, "default_12m": y,
    })

    # Defectos de calidad controlados
    def holes(col, frac):
        idx = rng.choice(n, int(n * frac), replace=False)
        df.loc[idx, col] = np.nan
    holes("ingreso_mensual", 0.07); holes("ventas_mensuales", 0.12)
    holes("nivel_educativo", 0.05); holes("estado_civil", 0.03)
    holes("antiguedad_negocio_meses", 0.04); holes("tipo_vivienda", 0.02)
    bad = rng.choice(n, int(n * 0.004), replace=False)
    df.loc[bad[: len(bad) // 2], "edad"] = 999          # edad inválida
    df.loc[bad[len(bad) // 2:], "monto_solicitado"] = -1  # monto negativo
    out = rng.choice(n, int(n * 0.002), replace=False)
    df.loc[out, "ingreso_mensual"] = df.loc[out, "ingreso_mensual"] * 40  # atípicos
    dups = df.sample(frac=0.003, random_state=seed)
    return pd.concat([df, dups], ignore_index=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100_000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="data/source/solicitudes.csv")
    a = ap.parse_args()
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    d = generate(a.n, a.seed)
    d.to_csv(a.out, index=False)
    print(f"Dataset sintético generado: {a.out} ({len(d):,} filas, tasa default {d.default_12m.mean():.2%})")
