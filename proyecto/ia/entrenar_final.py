"""
Entrenamiento determinista del modelo final `rf_final`.

    python3 -m ia.datos.construir_entrenamiento_final      # 1) ventanas (una vez)
    python3 -m ia.entrenar_final                           # 2) entrena y congela el modelo

Entrada: ia/datos/procesados/ventanas_final.parquet (GeoLife de entrenamiento + episodios de SUMO de las
semillas 201-204, con ruido AR(1) aplicado a las posiciones). Los usuarios de prueba de
`ia/particion_usuarios.json` y las semillas SUMO 101-105 NO entran: se comprueba al entrenar y en
`ia/tests/test_modelo_final.py`.

Salida: ia/modelos/rf_final.joblib (compress=3) y ia/modelos/rf_final.json (SHA-256 del modelo, version de
scikit-learn, caracteristicas ordenadas, clases, ventana y paso, suavizado, parametros del fallback, SHA-256 de
cada archivo de entrada, fecha y metricas). Dos ejecuciones dan el mismo SHA-256 (random_state=42, n_jobs fijo,
filas ordenadas de forma estable).
"""
import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from ia.caracteristicas import NOMBRES_FEATURES

AQUI = Path(__file__).resolve().parent
VENTANAS = AQUI / "datos" / "procesados" / "ventanas_final.parquet"
DATOS_JSON = AQUI / "reportes" / "entrenamiento_final_datos.json"
MODELO = AQUI / "modelos" / "rf_final.joblib"
META = AQUI / "modelos" / "rf_final.json"
PARTICION = AQUI / "particion_usuarios.json"

CLASES = ["a_pie", "quieto", "vehiculo"]
SEMILLA = 42
N_JOBS = 1  # fijo: el resultado no depende de el, pero asi el pico de RAM es predecible

# Hiperparametros del mejor resultado de S2-2 (ia/reportes/cv_rf_v1.json -> mejores_params: 200 arboles,
# profundidad 20, hoja minima 3; la busqueda completa esta en ia/reportes/cv_search_rf_v1.csv). Con las
# ventanas ruidosas esa configuracion daba un .joblib de 106,6 MB (limite del prompt: 50 MB), asi que se
# redujo a 100 arboles y hoja minima 5 y se documenta en la model card. S3-2 (ia/reportes/conclusiones_s3.md)
# confirmo suavizado k = 1, es decir, sin suavizar.
HIPERPARAMETROS = {
    "n_estimators": 100,
    "max_depth": 20,
    "min_samples_leaf": 5,
    "max_features": "sqrt",
    "class_weight": "balanced",
}
SUAVIZADO = {"metodo": "mayoria", "k": 1}
# Reglas del fallback de `ia/inferencia.py` (S3-1): RF solo con cobertura y huecos aceptables.
FALLBACK = {"cobertura_min": 0.6, "hueco_max_s": 10.0, "puntos_min": 5,
            "fuente_si_no_cumple": "umbral", "umbral_vehiculo_kmh": 8.0, "umbral_quieto_kmh": 0.5}


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 22), b""):
            h.update(bloque)
    return h.hexdigest()


def cargar_datos() -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    df = pd.read_parquet(VENTANAS)
    part = json.loads(PARTICION.read_text())
    geo = df[df["origen"] == "geolife"]
    sumo = df[df["origen"] == "sumo"]
    if set(geo["usuario_id"]) & set(part["usuarios_prueba"]):
        raise SystemExit("FUGA: usuarios de prueba de GeoLife en el entrenamiento")
    if set(sumo["semilla_sumo"].astype(int)) & set(part["semillas_sumo_prueba"]):
        raise SystemExit("FUGA: semillas SUMO de prueba en el entrenamiento")
    df = df.sort_values(["origen", "usuario_id", "t_inicio", "modo_real"], kind="stable").reset_index(drop=True)
    return df[NOMBRES_FEATURES].to_numpy(np.float32), df["modo_real"].to_numpy(), df


def entrenar(X: np.ndarray, y: np.ndarray) -> Pipeline:
    pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("rf", RandomForestClassifier(random_state=SEMILLA, n_jobs=N_JOBS, **HIPERPARAMETROS)),
    ])
    return pipe.fit(X, y)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", type=Path, default=MODELO)
    ap.add_argument("--meta", type=Path, default=META)
    a = ap.parse_args()

    t0 = time.time()
    X, y, df = cargar_datos()
    print(f"{len(df)} ventanas; por clase {pd.Series(y).value_counts().to_dict()}", flush=True)
    pipe = entrenar(X, y)
    assert list(pipe.named_steps["rf"].classes_) == CLASES
    a.modelo.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, a.modelo, compress=3)
    digest = sha256(a.modelo)
    tam_mb = a.modelo.stat().st_size / 1e6
    print(f"SHA-256 {digest}  ({tam_mb:.1f} MB, {time.time() - t0:.0f} s)", flush=True)

    datos = json.loads(DATOS_JSON.read_text()) if DATOS_JSON.exists() else {}
    meta = {
        "version": "rf_final",
        "congelado": True,
        "sha256_modelo": digest,
        "tamano_mb": round(tam_mb, 2),
        "sklearn_version": sklearn.__version__,
        "features": NOMBRES_FEATURES,
        "clases": CLASES,
        "ventana_s": 30,
        "paso_s": 5,
        "hiperparametros": {**HIPERPARAMETROS, "random_state": SEMILLA, "n_jobs": N_JOBS},
        "suavizado": SUAVIZADO,
        "fallback": FALLBACK,
        "entrenamiento": {
            "n_ventanas": int(len(df)),
            "por_origen_y_clase": df.groupby(["origen", "modo_real"]).size().rename("n").reset_index().to_dict("records"),
            "semillas_sumo": sorted(int(s) for s in df.loc[df["origen"] == "sumo", "semilla_sumo"].unique()),
            "usuarios_geolife": int(df.loc[df["origen"] == "geolife", "usuario_id"].nunique()),
            "sha256_entradas": datos.get("sha256_entradas", {}),
        },
        "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "metricas": {},
    }
    a.meta.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    print("->", a.meta)


if __name__ == "__main__":
    main()
