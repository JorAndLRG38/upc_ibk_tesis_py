"""HU02 - Análisis exploratorio de datos (EDA) (EP01).

Tareas del Sprint Backlog cubiertas:
  TK-02.1 Estadísticas descriptivas de variables numéricas -> descriptive_stats()
  TK-02.2 Distribución de la variable objetivo             -> target_distribution(), temporal_default_rate()
  TK-02.3 Detección de valores atípicos y faltantes        -> missing_report(), outlier_report(), consistency_report()
  TK-02.4 Matriz de correlaciones y visualizaciones        -> correlation_matrix(), plot_*()
  TK-02.5 Consolidar reporte EDA en notebook Jupyter       -> run_eda() + notebooks/eda_report.ipynb
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from training.common import Contract, get_logger, load_contract  # noqa: E402

log = get_logger("eda")
UPC_BLUE = "#1F3864"
plt.rcParams.update({"font.family": "DejaVu Serif", "font.size": 10, "axes.titleweight": "bold",
                     "axes.titlecolor": UPC_BLUE, "figure.dpi": 110})


# ---------------------------------------------------------------- TK-02.1
def descriptive_stats(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    num = df[cols].apply(pd.to_numeric, errors="coerce").astype("float64")
    st = num.describe(percentiles=[.25, .5, .75]).T.rename(
        columns={"count": "n", "mean": "media", "std": "desv_est", "min": "min",
                 "25%": "q1", "50%": "mediana", "75%": "q3", "max": "max"})
    st["asimetria"] = num.skew()
    st["cv"] = st["desv_est"] / st["media"].replace(0, np.nan)
    return st[["n", "media", "mediana", "desv_est", "min", "q1", "q3", "max", "asimetria", "cv"]].round(3)


# ---------------------------------------------------------------- TK-02.2
def target_distribution(df: pd.DataFrame, target: str) -> dict:
    vc = df[target].value_counts().sort_index()
    pos, neg = int(vc.get(1, 0)), int(vc.get(0, 0))
    return {"n_total": int(len(df)), "n_cumplidos": neg, "n_incumplidos": pos,
            "tasa_incumplimiento": round(pos / max(len(df), 1), 4),
            "ratio_desbalance": round(neg / max(pos, 1), 2)}


def temporal_default_rate(df: pd.DataFrame, target: str, date_col: str) -> pd.DataFrame:
    """Solicitado por el PO: tasa de incumplimiento por año-mes (estacionalidad)."""
    d = df[[date_col, target]].dropna()
    d = d.assign(periodo=d[date_col].dt.to_period("M").astype(str))
    return (d.groupby("periodo")[target].agg(n="size", tasa="mean").reset_index()
            .assign(tasa=lambda x: x["tasa"].round(4)))


# ---------------------------------------------------------------- TK-02.3
def missing_report(df: pd.DataFrame) -> pd.DataFrame:
    rep = pd.DataFrame({"faltantes": df.isna().sum(), "pct_faltantes": (df.isna().mean() * 100).round(2)})
    return rep.sort_values("pct_faltantes", ascending=False)


def outlier_report(df: pd.DataFrame, cols: list[str], k: float = 1.5) -> pd.DataFrame:
    rows = []
    for c in cols:
        s = pd.to_numeric(df[c], errors="coerce").dropna().astype("float64")
        q1, q3 = s.quantile([.25, .75])
        iqr = q3 - q1
        lo, hi = q1 - k * iqr, q3 + k * iqr
        n_out = int(((s < lo) | (s > hi)).sum())
        rows.append({"variable": c, "lim_inf": round(lo, 2), "lim_sup": round(hi, 2),
                     "n_atipicos": n_out, "pct_atipicos": round(100 * n_out / max(len(s), 1), 2)})
    return pd.DataFrame(rows).sort_values("pct_atipicos", ascending=False).reset_index(drop=True)


def consistency_report(df: pd.DataFrame, contract: Contract) -> pd.DataFrame:
    rows = []
    for c, spec in contract.columns.items():
        if "rango" in spec and c in df:
            lo, hi = spec["rango"]
            s = pd.to_numeric(df[c], errors="coerce")
            n_bad = int(((s < lo) | (s > hi)).sum())
            rows.append({"regla": f"{c} en [{lo}, {hi}]", "variable": c, "n_inconsistentes": n_bad})
    rows.append({"regla": "registros duplicados exactos", "variable": "*",
                 "n_inconsistentes": int(df.duplicated().sum())})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- TK-02.4
def correlation_matrix(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    return df[cols].apply(pd.to_numeric, errors="coerce").astype("float64").corr(method="spearman").round(3)


def _save(fig, out: Path, name: str) -> str:
    p = out / f"{name}.png"
    fig.tight_layout()
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    return str(p)


def plot_target(dist: dict, out: Path) -> str:
    fig, ax = plt.subplots(figsize=(5, 3.4))
    bars = ax.bar(["Cumplido (0)", "Incumplido (1)"], [dist["n_cumplidos"], dist["n_incumplidos"]],
                  color=[UPC_BLUE, "#C00000"])
    for b, v in zip(bars, [dist["n_cumplidos"], dist["n_incumplidos"]]):
        ax.annotate(f"{v:,}\n({v / dist['n_total']:.1%})", (b.get_x() + b.get_width() / 2, v),
                    ha="center", va="bottom", fontsize=9)
    ax.set_title("Distribución de la variable objetivo")
    ax.set_ylabel("N.° de solicitudes"); ax.margins(y=0.2)
    return _save(fig, out, "fig_target_distribucion")


def plot_missing(rep: pd.DataFrame, out: Path) -> str:
    r = rep[rep.pct_faltantes > 0]
    fig, ax = plt.subplots(figsize=(6, max(2.2, 0.35 * len(r) + 1)))
    ax.barh(r.index[::-1], r.pct_faltantes[::-1], color=UPC_BLUE)
    for i, v in enumerate(r.pct_faltantes[::-1]):
        ax.text(v + 0.2, i, f"{v:.1f}%", va="center", fontsize=8)
    ax.set_xlabel("% de valores faltantes"); ax.set_title("Valores faltantes por variable")
    return _save(fig, out, "fig_faltantes")


def plot_correlation(corr: pd.DataFrame, out: Path) -> str:
    fig, ax = plt.subplots(figsize=(8, 6.5))
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr))); ax.set_xticklabels(corr.columns, rotation=60, ha="right", fontsize=7)
    ax.set_yticks(range(len(corr))); ax.set_yticklabels(corr.index, fontsize=7)
    for i in range(len(corr)):
        for j in range(len(corr)):
            ax.text(j, i, f"{corr.values[i, j]:.2f}", ha="center", va="center", fontsize=5.5,
                    color="white" if abs(corr.values[i, j]) > 0.5 else "black")
    fig.colorbar(im, ax=ax, shrink=0.8); ax.set_title("Matriz de correlación de Spearman")
    return _save(fig, out, "fig_correlaciones")


def plot_boxplots(df: pd.DataFrame, cols: list[str], target: str, out: Path) -> str:
    n = len(cols); ncol = 3; nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(10, 2.6 * nrow))
    for ax, c in zip(axes.flat, cols):
        data = [pd.to_numeric(df.loc[df[target] == k, c], errors="coerce").dropna().astype(float) for k in (0, 1)]
        ax.boxplot(data, tick_labels=["0", "1"], showfliers=False, patch_artist=True,
                   boxprops={"facecolor": "#D9E2F3"})
        ax.set_title(c, fontsize=9); ax.tick_params(labelsize=7)
    for ax in list(axes.flat)[n:]:
        ax.axis("off")
    fig.suptitle("Variables numéricas según incumplimiento (sin atípicos)", color=UPC_BLUE, fontweight="bold")
    return _save(fig, out, "fig_boxplots_objetivo")


def plot_temporal(tmp: pd.DataFrame, out: Path) -> str:
    fig, ax = plt.subplots(figsize=(9, 3.2))
    ax.plot(tmp.periodo, tmp.tasa * 100, marker="o", ms=3, color=UPC_BLUE)
    ax.set_xticks(range(0, len(tmp), 3)); ax.set_xticklabels(tmp.periodo[::3], rotation=45, fontsize=7)
    ax.set_ylabel("Tasa de incumplimiento (%)"); ax.set_title("Tasa de incumplimiento por mes de solicitud")
    ax.grid(alpha=.3)
    return _save(fig, out, "fig_temporal")


# ---------------------------------------------------------------- TK-02.5
def run_eda(df: pd.DataFrame, contract: Contract | None = None, out_dir: str | Path = "reports/eda") -> dict:
    contract = contract or load_contract()
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    tgt = contract.target
    num = contract.cols_of("int", "float")
    stats = descriptive_stats(df, num)
    dist = target_distribution(df, tgt)
    miss = missing_report(df)
    outl = outlier_report(df, num)
    cons = consistency_report(df, contract)
    corr = correlation_matrix(df, num + [tgt])
    temp = temporal_default_rate(df, tgt, "fecha_solicitud")
    figs = {"objetivo": plot_target(dist, out), "faltantes": plot_missing(miss, out),
            "correlaciones": plot_correlation(corr, out),
            "boxplots": plot_boxplots(df, num[:9], tgt, out), "temporal": plot_temporal(temp, out)}
    for name, frame in {"estadisticas": stats, "faltantes": miss, "atipicos": outl,
                        "consistencia": cons, "correlaciones": corr, "temporal": temp}.items():
        frame.to_csv(out / f"tabla_{name}.csv")
    top_corr = corr[tgt].drop(tgt).abs().sort_values(ascending=False).head(5)
    summary = {"objetivo": dist, "variables_con_faltantes": int((miss.pct_faltantes > 0).sum()),
               "max_pct_faltantes": float(miss.pct_faltantes.max()),
               "duplicados": int(df.duplicated().sum()),
               "inconsistencias": int(cons.n_inconsistentes.sum()),
               "top5_corr_objetivo": top_corr.round(3).to_dict(), "figuras": figs}
    (out / "eda_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("EDA generado en %s", out)
    return {"summary": summary, "stats": stats, "missing": miss, "outliers": outl,
            "consistency": cons, "corr": corr, "temporal": temp}
