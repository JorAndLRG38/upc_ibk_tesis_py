"""HU03 - Limpieza, imputación y codificación del dataset (EP01).

Tareas del Sprint Backlog cubiertas:
  TK-03.1 Definir estrategia de imputación por tipo de variable -> IMPUTATION_STRATEGY
  TK-03.2 Implementar imputación de valores faltantes         -> build_preprocessor()
  TK-03.3 Codificar variables categóricas (one-hot y target)  -> build_preprocessor()
  TK-03.4 Validar que no queden nulos en columnas críticas    -> validate_prepared()
  TK-03.5 Versionar dataset preparado y documentar            -> persist_artifacts(), write_data_dictionary()

Decisión técnica (prevención de fuga de información): la partición estratificada
train/test se realiza ANTES de ajustar imputadores y codificadores; estos se ajustan
solo con train y se aplican a test. SMOTE-ENN (Sprint 2) también se aplicará solo a train.

Uso:
    python -m training.preprocessing --input data/raw/dataset_base_<fecha>.parquet
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, OrdinalEncoder, TargetEncoder

from training.common import Contract, get_logger, load_contract, utc_now
from training.security import assert_no_pii, write_manifest

log = get_logger("preprocessing")

# ---------------------------------------------------------------- TK-03.1
IMPUTATION_STRATEGY = {
    "numerica": "Mediana del conjunto de entrenamiento + indicador binario de faltante "
                "(robusta a la asimetría observada en el EDA; el indicador conserva la señal "
                "de que el dato no fue declarado).",
    "categorica_nominal": "Categoría explícita 'Desconocido' (no se asume la moda para no sesgar).",
    "ordinal": "Moda del entrenamiento; luego codificación ordinal según el orden regulatorio SBS.",
    "booleana": "Moda del entrenamiento (False si empata).",
    "fecha": "No se imputa: se usa solo para análisis temporal y se excluye del vector de entrada.",
}


def to_float(X: pd.DataFrame) -> pd.DataFrame:
    """Convierte tipos nullable (Int64, boolean) a float64 con NaN para los imputadores."""
    return X.astype("float64")


def to_obj(X: pd.DataFrame) -> pd.DataFrame:
    """Convierte StringDtype a object con np.nan para los imputadores/codificadores."""
    return X.astype(object).where(pd.notna(X), np.nan)


class DataQualityError(ValueError):
    pass


@dataclass
class PreparedData:
    X_train: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_test: pd.Series
    preprocessor: ColumnTransformer
    report: dict


def clean(df: pd.DataFrame, contract: Contract) -> tuple[pd.DataFrame, dict]:
    """Elimina duplicados y convierte a NaN los valores fuera del rango de negocio."""
    out = df.drop_duplicates().copy()
    n_dups = len(df) - len(out)
    fixed = {}
    for c, spec in contract.columns.items():
        if "rango" in spec and c in out:
            lo, hi = spec["rango"]
            s = pd.to_numeric(out[c], errors="coerce")
            mask = (s < lo) | (s > hi)
            if mask.any():
                out.loc[mask, c] = np.nan
                fixed[c] = int(mask.sum())
    out = out[out[contract.target].notna()]
    return out.reset_index(drop=True), {"duplicados_eliminados": n_dups, "fuera_de_rango_a_nulo": fixed}


def split_columns(df: pd.DataFrame, contract: Contract) -> dict[str, list[str]]:
    thr = contract.prep["umbral_alta_cardinalidad"]
    nominal = contract.cols_of("category")
    return {
        "numericas": contract.cols_of("int", "float"),
        "booleanas": contract.cols_of("bool"),
        "ordinales": contract.cols_of("ordinal"),
        "onehot": [c for c in nominal if df[c].nunique(dropna=True) <= thr],
        "target_enc": [c for c in nominal if df[c].nunique(dropna=True) > thr],
    }


# ---------------------------------------------------------------- TK-03.2 / TK-03.3
def build_preprocessor(groups: dict[str, list[str]], contract: Contract) -> ColumnTransformer:
    seed = contract.prep["semilla"]
    unk = contract.prep["categoria_faltante"]
    ord_cols = groups["ordinales"]
    orders = [contract.columns[c]["orden"] for c in ord_cols]
    return ColumnTransformer([
        ("num", Pipeline([("cast", FunctionTransformer(to_float, feature_names_out="one-to-one")),
                          ("imp", SimpleImputer(strategy="median", add_indicator=True))]),
         groups["numericas"]),
        ("bool", Pipeline([("cast", FunctionTransformer(to_float, feature_names_out="one-to-one")),
                           ("imp", SimpleImputer(strategy="most_frequent"))]), groups["booleanas"]),
        ("ord", Pipeline([("cast", FunctionTransformer(to_obj, feature_names_out="one-to-one")),
                          ("imp", SimpleImputer(strategy="most_frequent")),
                          ("enc", OrdinalEncoder(categories=orders, handle_unknown="use_encoded_value",
                                                 unknown_value=-1))]), ord_cols),
        ("ohe", Pipeline([("cast", FunctionTransformer(to_obj, feature_names_out="one-to-one")),
                          ("imp", SimpleImputer(strategy="constant", fill_value=unk)),
                          ("enc", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]),
         groups["onehot"]),
        ("te", Pipeline([("cast", FunctionTransformer(to_obj, feature_names_out="one-to-one")),
                         ("imp", SimpleImputer(strategy="constant", fill_value=unk)),
                         ("enc", TargetEncoder(target_type="binary", cv=5, shuffle=True,
                                               random_state=seed))]), groups["target_enc"]),
    ], remainder="drop", verbose_feature_names_out=True).set_output(transform="pandas")


# ---------------------------------------------------------------- TK-03.4
def validate_prepared(X: pd.DataFrame, critical_sources: list[str], threshold: float) -> dict:
    crit_cols = [c for c in X.columns if any(c.split("__", 1)[-1].startswith(src) for src in critical_sources)]
    null_pct = X[crit_cols].isna().mean() if crit_cols else pd.Series(dtype=float)
    worst = float(null_pct.max()) if len(null_pct) else 0.0
    non_numeric = [c for c in X.columns if not pd.api.types.is_numeric_dtype(X[c])]
    if worst >= threshold:
        raise DataQualityError(f"Nulos en columnas críticas: {worst:.2%} (umbral {threshold:.0%})")
    if non_numeric:
        raise DataQualityError(f"Columnas no numéricas tras la codificación: {non_numeric}")
    if not np.isfinite(X.to_numpy(dtype="float64")).all():
        raise DataQualityError("Existen valores infinitos o NaN en la matriz preparada")
    return {"columnas_criticas_validadas": len(crit_cols), "max_pct_nulos_criticos": round(worst * 100, 4),
            "columnas_finales": X.shape[1]}


def prepare(df: pd.DataFrame, contract: Contract | None = None) -> PreparedData:
    contract = contract or load_contract()
    p = contract.prep
    cleaned, clean_rep = clean(df, contract)
    tgt = contract.target
    y = cleaned[tgt].astype(int)
    X = cleaned.drop(columns=[tgt])
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=p["test_size"], stratify=y,
                                              random_state=p["semilla"])
    groups = split_columns(X_tr, contract)
    pre = build_preprocessor(groups, contract)
    Xt_tr = pre.fit_transform(X_tr, y_tr)   # ajuste SOLO con entrenamiento
    Xt_te = pre.transform(X_te)
    crit = [c for c in contract.critical if c not in (tgt, "cliente_id", "fecha_solicitud")]
    val_tr = validate_prepared(Xt_tr, crit, p["umbral_nulos_criticos"])
    validate_prepared(Xt_te, crit, p["umbral_nulos_criticos"])
    report = {"limpieza": clean_rep, "grupos": groups, "estrategia_imputacion": IMPUTATION_STRATEGY,
              "filas_train": len(Xt_tr), "filas_test": len(Xt_te),
              "tasa_default_train": round(float(y_tr.mean()), 4),
              "tasa_default_test": round(float(y_te.mean()), 4), "validacion": val_tr}
    log.info("Preparación OK: train %s x %s | test %s", f"{len(Xt_tr):,}", Xt_tr.shape[1], f"{len(Xt_te):,}")
    return PreparedData(Xt_tr, Xt_te, y_tr, y_te, pre, report)


# ---------------------------------------------------------------- TK-03.5
def write_data_dictionary(prep: PreparedData, contract: Contract, path: Path) -> None:
    g = prep.report["grupos"]
    lines = ["# Diccionario de datos del dataset preparado (Sprint 1)", "",
             f"Generado: {utc_now()} | Contrato v{contract.raw['dataset']['version_contrato']} | "
             f"scikit-learn {sklearn.__version__}", "",
             "| Variable origen | Tipo | Crítica | Tratamiento de faltantes | Codificación |",
             "|---|---|---|---|---|"]
    for c, s in contract.columns.items():
        if c in (contract.target, "cliente_id", "fecha_solicitud"):
            continue
        if c in g["numericas"]:
            trat, enc = "Mediana (train) + indicador", "Numérica"
        elif c in g["booleanas"]:
            trat, enc = "Moda (train)", "Binaria 0/1"
        elif c in g["ordinales"]:
            trat, enc = "Moda (train)", "Ordinal " + " < ".join(s["orden"])
        elif c in g["onehot"]:
            trat, enc = "Categoría 'Desconocido'", "One-hot"
        else:
            trat, enc = "Categoría 'Desconocido'", "Target encoding (cv=5)"
        lines.append(f"| {c} | {s['tipo']} | {'Sí' if s.get('critica') else 'No'} | {trat} | {enc} |")
    lines += ["", f"Variable objetivo: `{contract.target}`: {contract.raw['objetivo']['descripcion']}.",
              "`cliente_id` (seudonimizado) y `fecha_solicitud` se conservan solo para trazabilidad.", "",
              f"Columnas finales tras la codificación: {prep.X_train.shape[1]}"]
    path.write_text("\n".join(lines), encoding="utf-8")


def persist_artifacts(prep: PreparedData, contract: Contract, out_dir: str | Path = "data/prepared") -> dict:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, X, y in (("train", prep.X_train, prep.y_train), ("test", prep.X_test, prep.y_test)):
        p = out / f"dataset_preparado_{name}.parquet"
        assert_no_pii(X, contract.drop_pii)
        X.assign(**{contract.target: y.values}).to_parquet(p, index=False)
        write_manifest(p, {"filas": len(X), "columnas": X.shape[1], "fecha_utc": utc_now()})
        paths[name] = str(p)
    pre_path = out / "preprocessor.joblib"
    joblib.dump(prep.preprocessor, pre_path)
    write_manifest(pre_path, {"sklearn": sklearn.__version__, "fecha_utc": utc_now()})
    (out / "preparation_report.json").write_text(json.dumps(prep.report, indent=2, ensure_ascii=False,
                                                            default=str), encoding="utf-8")
    write_data_dictionary(prep, contract, out / "data_dictionary.md")
    paths["preprocessor"] = str(pre_path)
    return paths


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HU03 - Preparación del dataset analítico")
    ap.add_argument("--input", required=True)
    ap.add_argument("--out-dir", default="data/prepared")
    a = ap.parse_args(argv)
    contract = load_contract()
    try:
        prep = prepare(pd.read_parquet(a.input), contract)
    except DataQualityError as exc:
        print(f"Error de calidad de datos: {exc}", file=sys.stderr)
        return 3
    print(json.dumps(persist_artifacts(prep, contract, a.out_dir), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
