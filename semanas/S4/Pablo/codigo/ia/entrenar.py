"""
Entrenamiento del clasificador Random Forest v1 con busqueda de hiperparametros.

    python -m ia.entrenar --datos ia/datos/procesados/ventanas_v2.parquet --n-iter 30 --semilla 42

Guarda:
  ia/modelos/rf_v1.joblib
  ia/modelos/rf_v1.json
  ia/reportes/cv_rf_v1.json
"""
import argparse
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
from sklearn.inspection import permutation_importance
from sklearn.model_selection import GroupKFold, RandomizedSearchCV
from sklearn.pipeline import Pipeline

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ia.caracteristicas import NOMBRES_FEATURES
from ia.umbral import predecir_lote
from ia import evaluar as ev

DIR_MODELOS = Path(__file__).resolve().parent / "modelos"
DIR_REPORTES = Path(__file__).resolve().parent / "reportes"
DIR_DATOS = Path(__file__).resolve().parent / "datos" / "procesados"
CLASES = ["a_pie", "quieto", "vehiculo"]

N_JOBS = 2


def _hash_datos(df: pd.DataFrame) -> str:
    h = hashlib.sha256()
    h.update(pd.util.hash_pandas_object(df).values.tobytes())
    return h.hexdigest()[:16]


def cargar_datos(ruta: Path | None = None) -> pd.DataFrame:
    ruta = ruta or DIR_DATOS / "ventanas_v2.parquet"
    df = pd.read_parquet(ruta)
    faltantes = [f for f in NOMBRES_FEATURES if f not in df.columns]
    if faltantes:
        raise ValueError(f"Faltan columnas: {faltantes}")
    return df


def filtrar_entrenamiento(df: pd.DataFrame) -> pd.DataFrame:
    """Filtra usuarios/semillas de prueba del conjunto de entrenamiento."""
    ruta_particion = Path(__file__).resolve().parent / "particion_usuarios.json"
    with open(ruta_particion) as f:
        particion = json.load(f)

    usuarios_prueba = set(particion["usuarios_prueba"])
    semillas_prueba = set(particion.get("semillas_sumo_prueba", []))

    mask_usuario = ~df["usuario_id"].isin(usuarios_prueba)
    mask_semilla = True
    if "semilla_sumo" in df.columns:
        mask_semilla = ~df["semilla_sumo"].isin(semillas_prueba)

    df_train = df[mask_usuario & mask_semilla].copy()
    print(f"  Filtrado: {len(df)} -> {len(df_train)} ventanas (sin usuarios/semillas de prueba)", flush=True)
    return df_train


def _submuestrear_por_grupos(df: pd.DataFrame, fraccion: float, semilla: int,
                              max_ventanas: int = 50_000) -> pd.DataFrame:
    """Submuestrea por grupos y luego por filas si excede max_ventanas."""
    rng = np.random.default_rng(semilla)
    grupos_unicos = df["grupo"].unique()
    n_sel = max(3, int(len(grupos_unicos) * fraccion))
    sel = rng.choice(grupos_unicos, size=n_sel, replace=False)
    df_sub = df[df["grupo"].isin(sel)].copy()
    if len(df_sub) > max_ventanas:
        df_sub = df_sub.sample(n=max_ventanas, random_state=semilla)
    print(f"  Submuestreo: {len(grupos_unicos)} -> {n_sel} grupos, "
          f"{len(df)} -> {len(df_sub)} ventanas", flush=True)
    return df_sub


def espacio_hiperparametros():
    return {
        "rf__n_estimators": [100, 150, 200, 250],
        "rf__max_depth": [8, 12, 16, 20],
        "rf__min_samples_leaf": list(range(1, 11)),
        "rf__max_features": ["sqrt", "log2", 0.3, 0.5],
        "rf__class_weight": [None, "balanced", "balanced_subsample"],
    }


def crear_pipeline_base() -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("rf", RandomForestClassifier(random_state=42, n_jobs=N_JOBS)),
    ])


def busqueda_hiperparametros(df_sub: pd.DataFrame, n_iter: int = 30, semilla: int = 42) -> dict:
    X = df_sub[NOMBRES_FEATURES].to_numpy()
    y = np.array(df_sub["modo_real"].tolist())
    grupos = np.array(df_sub["grupo"].tolist())

    gkf = GroupKFold(n_splits=3)

    pipe = crear_pipeline_base()
    search = RandomizedSearchCV(
        pipe,
        espacio_hiperparametros(),
        n_iter=n_iter,
        scoring="f1_macro",
        cv=gkf,
        n_jobs=1,
        random_state=semilla,
        verbose=1,
        refit=False,
    )

    print(f"Iniciando RandomizedSearchCV con {n_iter} iteraciones, GroupKFold(3), "
          f"{len(df_sub)} ventanas...", flush=True)
    search.fit(X, y, groups=grupos)

    mejores = search.best_params_
    print(f"\nMejores hiperparametros: {mejores}", flush=True)
    print(f"Mejor macro-F1 (CV): {search.best_score_:.4f}", flush=True)

    resultados_cv = pd.DataFrame(search.cv_results_)
    return {
        "mejores_params": mejores,
        "mejor_score": float(search.best_score_),
        "resultados_cv": resultados_cv,
    }


def validar_con_mejores(df: pd.DataFrame, params: dict) -> dict:
    """GroupKFold(3) con los mejores hiperparametros, submuestreado para no agotar RAM."""
    import gc

    MAX_TRAIN = 200_000
    rng_sub = np.random.default_rng(42)
    df_val = _submuestrear_por_grupos(df, fraccion=0.30, semilla=42, max_ventanas=600_000)

    X = df_val[NOMBRES_FEATURES].to_numpy()
    y = np.array(df_val["modo_real"].tolist())
    grupos = np.array(df_val["grupo"].tolist())
    vel_medias = df_val["vel_media"].to_numpy()
    del df_val; gc.collect()

    gkf = GroupKFold(n_splits=3)
    resultados_rf = []
    resultados_umbral = []
    importancias = []

    for fold, (idx_train, idx_test) in enumerate(gkf.split(X, y, grupos)):
        if len(idx_train) > MAX_TRAIN:
            idx_train = rng_sub.choice(idx_train, size=MAX_TRAIN, replace=False)

        X_train, X_test = X[idx_train], X[idx_test]
        y_train, y_test = y[idx_train], y[idx_test]

        pipe = crear_pipeline_base()
        pipe.set_params(**{**params, "rf__n_jobs": 1})
        pipe.fit(X_train, y_train)
        del X_train, y_train; gc.collect()

        y_pred_rf = pipe.predict(X_test)
        y_pred_umbral = predecir_lote(vel_medias[idx_test])

        resultados_rf.append(ev.metricas_fold(y_test, y_pred_rf, fold, "rf_v1"))
        resultados_umbral.append(ev.metricas_fold(y_test, y_pred_umbral, fold, "umbral"))

        print(f"  Fold {fold}: RF_v1 macro-F1={resultados_rf[-1]['macro_f1']:.4f}  "
              f"Umbral macro-F1={resultados_umbral[-1]['macro_f1']:.4f}", flush=True)

        n_imp_samples = min(20_000, len(X_test))
        imp_idx = rng_sub.choice(len(X_test), size=n_imp_samples, replace=False)
        perm_imp = permutation_importance(
            pipe, X_test[imp_idx], y_test[imp_idx],
            n_repeats=3,
            scoring="f1_macro",
            random_state=42,
            n_jobs=1,
        )
        importancias.append({
            "fold": fold,
            "importances_mean": perm_imp.importances_mean.tolist(),
            "importances_std": perm_imp.importances_std.tolist(),
        })
        print(f"    Importancia fold {fold} calculada ({n_imp_samples} muestras)", flush=True)

        del pipe, X_test, y_test, y_pred_rf
        gc.collect()

    metricas = ev.agregar_folds(resultados_rf, resultados_umbral)

    imp_media = np.mean([imp["importances_mean"] for imp in importancias], axis=0)
    imp_std_entre_folds = np.std([imp["importances_mean"] for imp in importancias], axis=0)
    imp_std_media = np.mean([imp["importances_std"] for imp in importancias], axis=0)

    importancia_agregada = {
        "features": NOMBRES_FEATURES,
        "importancia_media": imp_media.tolist(),
        "importancia_std_entre_folds": imp_std_entre_folds.tolist(),
        "importancia_std_permutaciones": imp_std_media.tolist(),
        "por_fold": importancias,
    }

    return {
        "metricas": metricas,
        "importancia": importancia_agregada,
    }


def entrenar_final(df: pd.DataFrame, params: dict, max_ventanas: int = 400_000) -> Pipeline:
    import gc
    if len(df) > max_ventanas:
        df = df.sample(n=max_ventanas, random_state=42)
        print(f"  Submuestreo para entrenamiento final: {max_ventanas} ventanas", flush=True)
    X = df[NOMBRES_FEATURES].to_numpy()
    y = np.array(df["modo_real"].tolist())
    pipe = crear_pipeline_base()
    pipe.set_params(**{**params, "rf__n_jobs": 1})
    pipe.fit(X, y)
    return pipe


def guardar_modelo(pipe: Pipeline, df: pd.DataFrame, metricas: dict,
                   params: dict, importancia: dict, suavizado: dict | None = None):
    DIR_MODELOS.mkdir(parents=True, exist_ok=True)

    ruta_modelo = DIR_MODELOS / "rf_v1.joblib"
    dump(pipe, ruta_modelo, compress=3)
    tamano_mb = ruta_modelo.stat().st_size / 1e6
    print(f"Modelo guardado: {ruta_modelo} ({tamano_mb:.1f} MB)", flush=True)

    info = {
        "version": "v1",
        "features": NOMBRES_FEATURES,
        "clases": CLASES,
        "hiperparametros": {k.replace("rf__", ""): v for k, v in params.items()},
        "sklearn_version": sklearn.__version__,
        "fecha": datetime.now(timezone.utc).isoformat(),
        "hash_datos": _hash_datos(df),
        "n_ventanas": len(df),
        "metricas_cv": {
            "rf_v1_macro_f1": metricas["rf"]["macro_f1"],
            "rf_v1_macro_f1_std": metricas["rf"]["macro_f1_std"],
            "umbral_macro_f1": metricas["umbral"]["macro_f1"],
            "umbral_macro_f1_std": metricas["umbral"]["macro_f1_std"],
        },
        "importancia_features": dict(zip(NOMBRES_FEATURES, importancia["importancia_media"])),
        "suavizado": suavizado,
    }
    ruta_info = DIR_MODELOS / "rf_v1.json"
    with open(ruta_info, "w") as f:
        json.dump(info, f, indent=2, ensure_ascii=False)
    print(f"Info guardada: {ruta_info}", flush=True)

    return ruta_modelo, ruta_info, tamano_mb


def ejecutar(ruta_datos: str | None = None, n_iter: int = 15, semilla: int = 42,
             skip_search: bool = False):
    import gc
    print("=" * 60, flush=True)
    print("ENTRENAMIENTO RF v1 — RandomizedSearchCV + GroupKFold", flush=True)
    print("=" * 60, flush=True)

    print("\n1. Cargando datos...", flush=True)
    df = cargar_datos(Path(ruta_datos) if ruta_datos else None)
    df = filtrar_entrenamiento(df)
    n_total = len(df)
    print(f"  {n_total} ventanas, {df['grupo'].nunique()} grupos", flush=True)
    print(f"  Distribucion: {df['modo_real'].value_counts().to_dict()}", flush=True)

    DIR_REPORTES.mkdir(parents=True, exist_ok=True)

    if skip_search:
        mejores = {
            "rf__n_estimators": 200,
            "rf__min_samples_leaf": 3,
            "rf__max_features": "sqrt",
            "rf__max_depth": 20,
            "rf__class_weight": "balanced",
        }
        print(f"\n2. Busqueda OMITIDA — usando params previos: {mejores}", flush=True)
    else:
        print("\n2. Busqueda de hiperparametros (submuestreo 10%)...", flush=True)
        df_sub = _submuestrear_por_grupos(df, fraccion=0.10, semilla=semilla)
        resultado_busqueda = busqueda_hiperparametros(df_sub, n_iter=n_iter, semilla=semilla)
        mejores = resultado_busqueda["mejores_params"]
        del df_sub; gc.collect()
        resultado_busqueda["resultados_cv"].to_csv(DIR_REPORTES / "cv_search_rf_v1.csv", index=False)

    print("\n3. Validacion cruzada completa con mejores hiperparametros + importancia...", flush=True)
    resultado_val = validar_con_mejores(df, mejores)
    metricas = resultado_val["metricas"]
    importancia = resultado_val["importancia"]

    rf_f1 = metricas["rf"]["macro_f1"]
    rf_std = metricas["rf"]["macro_f1_std"]
    umb_f1 = metricas["umbral"]["macro_f1"]
    umb_std = metricas["umbral"]["macro_f1_std"]
    print(f"\n  RF_v1: macro-F1 = {rf_f1:.4f} +/- {rf_std:.4f}", flush=True)
    print(f"  Umbral: macro-F1 = {umb_f1:.4f} +/- {umb_std:.4f}", flush=True)

    print("\n  Importancia por permutacion (top 10):", flush=True)
    indices = np.argsort(importancia["importancia_media"])[::-1]
    for rank, idx in enumerate(indices[:10]):
        nombre = NOMBRES_FEATURES[idx]
        imp = importancia["importancia_media"][idx]
        std = importancia["importancia_std_entre_folds"][idx]
        print(f"    {rank+1}. {nombre}: {imp:.4f} +/- {std:.4f}", flush=True)

    with open(DIR_REPORTES / "cv_rf_v1.json", "w") as f:
        json.dump({
            "mejores_params": {k: str(v) if v is None else v for k, v in mejores.items()},
            "metricas": metricas,
            "importancia": importancia,
        }, f, indent=2, ensure_ascii=False, default=str)

    print("\n4. Entrenando modelo final con todos los datos...", flush=True)
    pipe = entrenar_final(df, mejores)

    ruta_modelo, ruta_info, tamano_mb = guardar_modelo(
        pipe, df, metricas, mejores, importancia)

    if tamano_mb > 50:
        print(f"AVISO: el modelo pesa {tamano_mb:.1f} MB (>50 MB). No subir al repo.", flush=True)

    print("\n" + "=" * 60, flush=True)
    print("ENTRENAMIENTO COMPLETO", flush=True)
    print(f"  RF_v1: {rf_f1:.4f} +/- {rf_std:.4f}  vs  Umbral: {umb_f1:.4f} +/- {umb_std:.4f}", flush=True)
    print(f"  Modelo: {ruta_modelo}", flush=True)
    print(f"  Info: {ruta_info}", flush=True)
    print("=" * 60, flush=True)

    return {
        "mejores_params": mejores,
        "metricas": metricas,
        "importancia": importancia,
        "ruta_modelo": str(ruta_modelo),
        "ruta_info": str(ruta_info),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Entrenar RF v1")
    parser.add_argument("--datos", type=str, default=None)
    parser.add_argument("--n-iter", type=int, default=15)
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--skip-search", action="store_true",
                        help="Omitir busqueda y usar hiperparametros previos")
    args = parser.parse_args()
    ejecutar(ruta_datos=args.datos, n_iter=args.n_iter, semilla=args.semilla,
             skip_search=args.skip_search)
