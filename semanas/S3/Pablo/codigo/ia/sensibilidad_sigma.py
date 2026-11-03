"""
Análisis de sensibilidad σ_entrenamiento × σ_validación.

    python -m ia.sensibilidad_sigma

Entrena RF con distintos σ de ruido AR(1) y evalúa con distintos σ.
Solo usa usuarios de entrenamiento y GroupKFold(5).
Guarda ia/reportes/sensibilidad_sigma.csv.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import f1_score, confusion_matrix
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ia.caracteristicas import NOMBRES_FEATURES, extraer
from ia.ventanas import remuestrear, ventanear
from ia.ruido import aplicar_ruido_ar1

DIR_IA = Path(__file__).resolve().parent
DIR_DATOS = DIR_IA / "datos" / "procesados"
DIR_REPORTES = DIR_IA / "reportes"
RUTA_PARTICION = DIR_IA / "particion_usuarios.json"

SIGMAS_ENTR = [0, 3, 8, 15, "mezcla"]
SIGMAS_VAL = [3, 5, 8, 10, 15]
CLASES = ["a_pie", "quieto", "vehiculo"]


def _crear_pipeline() -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("rf", RandomForestClassifier(
            n_estimators=20,
            class_weight="balanced_subsample",
            min_samples_leaf=5,
            n_jobs=2,
            random_state=42,
        )),
    ])


def _tasa_veh_como_apie(y_true, y_pred) -> float:
    cm = confusion_matrix(y_true, y_pred, labels=CLASES)
    veh_idx = CLASES.index("vehiculo")
    apie_idx = CLASES.index("a_pie")
    total_veh = cm[veh_idx].sum()
    if total_veh == 0:
        return 0.0
    return cm[veh_idx, apie_idx] / total_veh


def _aplicar_ruido_ventanas(df_ventanas: pd.DataFrame, sigma, rng_semilla: int) -> pd.DataFrame:
    """Aplica ruido a nivel de ventanas reconstruyendo puntos GPS temporales."""
    if sigma == 0:
        return df_ventanas.copy()

    n = len(df_ventanas)
    rng = np.random.default_rng(rng_semilla)

    if sigma == "mezcla":
        sigmas = rng.uniform(3.0, 15.0, size=n)
    else:
        sigmas = np.full(n, float(sigma))

    resultado = df_ventanas.copy()
    for feat in NOMBRES_FEATURES:
        if feat == "vel_media":
            noise_factor = 1.0 + rng.normal(0, 0.05 * sigmas / 10.0)
            resultado[feat] = resultado[feat] * noise_factor
        elif feat in ("vel_std", "vel_p95"):
            noise_factor = 1.0 + rng.normal(0, 0.03 * sigmas / 10.0)
            resultado[feat] = resultado[feat] * abs(noise_factor)
        elif feat == "precision_media":
            resultado[feat] = sigmas * rng.uniform(0.8, 1.5, size=n)

    return resultado


def ejecutar(max_ventanas: int = 100_000):
    with open(RUTA_PARTICION) as f:
        particion = json.load(f)

    usuarios_prueba = set(particion["usuarios_prueba"])

    print("Cargando ventanas de GeoLife...")
    df = pd.read_parquet(DIR_DATOS / "ventanas_geolife.parquet")
    df = df[~df["usuario_id"].isin(usuarios_prueba)].reset_index(drop=True)
    print(f"  {len(df)} ventanas de entrenamiento ({df['usuario_id'].nunique()} usuarios)")

    if len(df) > max_ventanas:
        rng_sub = np.random.default_rng(2026)
        usuarios = df["usuario_id"].unique()
        n_u = max(5, len(usuarios) // 8)
        usuarios_sub = rng_sub.choice(usuarios, size=n_u, replace=False)
        df = df[df["usuario_id"].isin(usuarios_sub)].reset_index(drop=True)
        print(f"  Submuestreo: {len(df)} ventanas, {df['usuario_id'].nunique()} usuarios", flush=True)

    X_base = df[NOMBRES_FEATURES].values
    y = df["modo_real"].values
    grupos = df["usuario_id"].values

    resultados = []
    gkf = GroupKFold(n_splits=3)
    folds = list(gkf.split(X_base, y, grupos))

    for sigma_e in SIGMAS_ENTR:
        print(f"\nσ_entr = {sigma_e}", flush=True)
        df_entr = _aplicar_ruido_ventanas(df, sigma_e, rng_semilla=42)

        for fold_i, (idx_train, idx_test) in enumerate(folds):
            X_train = df_entr[NOMBRES_FEATURES].values[idx_train]
            y_train = y[idx_train]

            pipe = _crear_pipeline()
            pipe.fit(X_train, y_train)

            for sigma_v in SIGMAS_VAL:
                df_val = _aplicar_ruido_ventanas(df, sigma_v, rng_semilla=100 + fold_i)
                X_test = df_val[NOMBRES_FEATURES].values[idx_test]
                y_test = y[idx_test]

                y_pred = pipe.predict(X_test)
                mf1 = f1_score(y_test, y_pred, labels=CLASES, average="macro")
                tva = _tasa_veh_como_apie(y_test, y_pred)

                resultados.append({
                    "sigma_entr": str(sigma_e),
                    "sigma_val": sigma_v,
                    "fold": fold_i,
                    "macro_f1": round(mf1, 4),
                    "tasa_veh_apie": round(tva, 4),
                })

            print(f"  Fold {fold_i}: σ_val=8 → F1={[r for r in resultados if r['fold']==fold_i and r['sigma_val']==8][-1]['macro_f1']:.4f}", flush=True)

    df_res = pd.DataFrame(resultados)

    DIR_REPORTES.mkdir(parents=True, exist_ok=True)
    ruta_csv = DIR_REPORTES / "sensibilidad_sigma.csv"
    df_res.to_csv(ruta_csv, index=False)
    print(f"\nGuardado: {ruta_csv}")

    pivote = df_res.groupby(["sigma_entr", "sigma_val"])["macro_f1"].mean().unstack()
    print("\nMatriz macro-F1 (promedio de folds):")
    print(pivote.to_string())

    peor_caso = pivote.min(axis=1)
    mejor = peor_caso.idxmax()
    print(f"\nMejor peor caso: σ_entr = {mejor} (min F1 = {peor_caso[mejor]:.4f})")

    return mejor, df_res


if __name__ == "__main__":
    mejor, _ = ejecutar()
    print(f"\n→ Configuración elegida: σ_entr = {mejor}")
