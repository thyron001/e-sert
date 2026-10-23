"""
Entrenamiento del clasificador Random Forest con validación GroupKFold.

    python -m ia.entrenar [ruta_ventanas.parquet]

Guarda:
  ia/modelos/rf_v0.joblib
  ia/modelos/rf_v0_info.json
  ia/resultados/s1_metricas.json
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from joblib import dump
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ia.caracteristicas import NOMBRES_FEATURES
from ia.umbral import predecir_lote
from ia import evaluar as ev

DIR_MODELOS = Path(__file__).resolve().parent / "modelos"
DIR_RESULTADOS = Path(__file__).resolve().parent / "resultados"
DIR_DATOS = Path(__file__).resolve().parent / "datos" / "procesados"
CLASES = ["a_pie", "quieto", "vehiculo"]


def _hash_datos(df: pd.DataFrame) -> str:
    h = hashlib.sha256()
    h.update(pd.util.hash_pandas_object(df).values.tobytes())
    return h.hexdigest()[:16]


def cargar_datos(ruta: Path | None = None) -> pd.DataFrame:
    ruta = ruta or DIR_DATOS / "ventanas_geolife.parquet"
    df = pd.read_parquet(ruta)
    faltantes = [f for f in NOMBRES_FEATURES if f not in df.columns]
    if faltantes:
        raise ValueError(f"Faltan columnas: {faltantes}")
    return df


def crear_pipeline() -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("rf", RandomForestClassifier(
            n_estimators=50,
            class_weight="balanced_subsample",
            min_samples_leaf=2,
            n_jobs=2,
            random_state=42,
        )),
    ])


def validar_cruzado(df: pd.DataFrame) -> dict:
    """GroupKFold(5) por usuario_id. Devuelve métricas por fold y agregadas."""
    X = df[NOMBRES_FEATURES].values
    y = df["modo_real"].values
    grupos = df["usuario_id"].values
    vel_medias = df["vel_media"].values

    gkf = GroupKFold(n_splits=5)
    resultados_rf = []
    resultados_umbral = []

    for fold, (idx_train, idx_test) in enumerate(gkf.split(X, y, grupos)):
        X_train, X_test = X[idx_train], X[idx_test]
        y_train, y_test = y[idx_train], y[idx_test]

        pipe = crear_pipeline()
        pipe.fit(X_train, y_train)
        y_pred_rf = pipe.predict(X_test)

        y_pred_umbral = predecir_lote(vel_medias[idx_test])

        resultados_rf.append(ev.metricas_fold(y_test, y_pred_rf, fold, "rf"))
        resultados_umbral.append(ev.metricas_fold(y_test, y_pred_umbral, fold, "umbral"))

        print(f"  Fold {fold}: RF macro-F1={resultados_rf[-1]['macro_f1']:.4f}  "
              f"Umbral macro-F1={resultados_umbral[-1]['macro_f1']:.4f}")

    return ev.agregar_folds(resultados_rf, resultados_umbral)


def entrenar_final(df: pd.DataFrame) -> Pipeline:
    """Entrena con todos los datos para el modelo de producción."""
    X = df[NOMBRES_FEATURES].values
    y = df["modo_real"].values
    pipe = crear_pipeline()
    pipe.fit(X, y)
    return pipe


def ejecutar(ruta_datos: Path | None = None):
    print("Cargando datos...")
    df = cargar_datos(ruta_datos)
    print(f"  {len(df)} ventanas, {df['usuario_id'].nunique()} usuarios")
    print(f"  Distribución: {df['modo_real'].value_counts().to_dict()}")

    print("\nValidación cruzada GroupKFold(5) por usuario_id...")
    metricas = validar_cruzado(df)

    DIR_RESULTADOS.mkdir(parents=True, exist_ok=True)
    ruta_metricas = DIR_RESULTADOS / "s1_metricas.json"
    with open(ruta_metricas, "w") as f:
        json.dump(metricas, f, indent=2, ensure_ascii=False)
    print(f"\nMétricas guardadas: {ruta_metricas}")

    print("\nEntrenando modelo final con todos los datos...")
    pipe = entrenar_final(df)

    DIR_MODELOS.mkdir(parents=True, exist_ok=True)
    ruta_modelo = DIR_MODELOS / "rf_v0.joblib"
    dump(pipe, ruta_modelo, compress=3)
    print(f"Modelo guardado: {ruta_modelo} ({ruta_modelo.stat().st_size / 1e6:.1f} MB)")

    info = {
        "version": "v0",
        "features": NOMBRES_FEATURES,
        "clases": CLASES,
        "n_estimators": 300,
        "sklearn_version": sklearn.__version__,
        "fecha": datetime.now(timezone.utc).isoformat(),
        "hash_datos": _hash_datos(df),
        "n_ventanas": len(df),
        "metricas_cv": {
            "rf_macro_f1": metricas["rf"]["macro_f1"],
            "umbral_macro_f1": metricas["umbral"]["macro_f1"],
        },
    }
    ruta_info = DIR_MODELOS / "rf_v0_info.json"
    with open(ruta_info, "w") as f:
        json.dump(info, f, indent=2, ensure_ascii=False)
    print(f"Info guardada: {ruta_info}")

    return metricas


if __name__ == "__main__":
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    ejecutar(ruta)
