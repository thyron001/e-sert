"""
Mezcla GeoLife + SUMO → ventanas_v2.parquet (entrenamiento).
Aparte: ventanas_prueba_geolife.parquet (usuarios de prueba sin aumentar).

    python -m ia.mezclar_datasets [sigma_entr]

sigma_entr: 'mezcla' o un float. Si no se pasa, usa 'mezcla' U(3,15).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ia.caracteristicas import NOMBRES_FEATURES
from ia.ruido import aplicar_ruido_ar1

DIR_IA = Path(__file__).resolve().parent
DIR_DATOS = DIR_IA / "datos" / "procesados"
RUTA_PARTICION = DIR_IA / "particion_usuarios.json"

COLS_META = ["modo_real", "usuario_id", "grupo", "t_inicio", "origen",
             "sigma_aplicado_m", "aumentada"]
CLASES = ["a_pie", "quieto", "vehiculo"]


def ejecutar(sigma_entr: str = "mezcla"):
    with open(RUTA_PARTICION) as f:
        particion = json.load(f)

    usuarios_prueba = set(particion["usuarios_prueba"])

    print("Cargando ventanas GeoLife...")
    df_geo = pd.read_parquet(DIR_DATOS / "ventanas_geolife.parquet")

    df_prueba = df_geo[df_geo["usuario_id"].isin(usuarios_prueba)].copy()
    df_prueba["grupo"] = df_prueba["usuario_id"]
    df_prueba["origen"] = "geolife"
    df_prueba["sigma_aplicado_m"] = 0.0
    df_prueba["aumentada"] = False
    if "t_inicio" not in df_prueba.columns:
        df_prueba["t_inicio"] = 0

    df_entr_geo = df_geo[~df_geo["usuario_id"].isin(usuarios_prueba)].copy()
    df_entr_geo["grupo"] = df_entr_geo["usuario_id"]
    df_entr_geo["origen"] = "geolife"
    df_entr_geo["sigma_aplicado_m"] = 0.0
    df_entr_geo["aumentada"] = False
    if "t_inicio" not in df_entr_geo.columns:
        df_entr_geo["t_inicio"] = 0

    print(f"  GeoLife entrenamiento: {len(df_entr_geo)} ventanas")
    print(f"  GeoLife prueba: {len(df_prueba)} ventanas")

    # Augmentation: 50% de GeoLife con ruido
    rng = np.random.default_rng(2026)
    n_aug = len(df_entr_geo) // 2
    idx_aug = rng.choice(len(df_entr_geo), size=n_aug, replace=False)
    df_aug = df_entr_geo.iloc[idx_aug].copy()

    if sigma_entr == "mezcla":
        sigmas = rng.uniform(3.0, 15.0, size=n_aug)
    else:
        sigmas = np.full(n_aug, float(sigma_entr))

    for feat in NOMBRES_FEATURES:
        if feat == "vel_media":
            noise = 1.0 + rng.normal(0, 0.05 * sigmas / 10.0)
            df_aug[feat] = df_aug[feat].values * noise
        elif feat in ("vel_std", "vel_p95"):
            noise = 1.0 + rng.normal(0, 0.03 * sigmas / 10.0)
            df_aug[feat] = df_aug[feat].values * abs(noise)
        elif feat == "precision_media":
            df_aug[feat] = sigmas * rng.uniform(0.8, 1.5, size=n_aug)

    df_aug["aumentada"] = True
    df_aug["sigma_aplicado_m"] = sigmas
    print(f"  GeoLife aumentado: {len(df_aug)} ventanas")

    # SUMO
    print("Cargando ventanas SUMO...")
    df_sumo = pd.read_parquet(DIR_DATOS / "ventanas_sumo.parquet")

    # Aplicar ruido a SUMO
    if sigma_entr == "mezcla":
        sigmas_sumo = rng.uniform(3.0, 15.0, size=len(df_sumo))
    else:
        sigmas_sumo = np.full(len(df_sumo), float(sigma_entr))

    for feat in NOMBRES_FEATURES:
        if feat == "vel_media":
            noise = 1.0 + rng.normal(0, 0.05 * sigmas_sumo / 10.0)
            df_sumo[feat] = df_sumo[feat].values * noise
        elif feat in ("vel_std", "vel_p95"):
            noise = 1.0 + rng.normal(0, 0.03 * sigmas_sumo / 10.0)
            df_sumo[feat] = df_sumo[feat].values * abs(noise)
        elif feat == "precision_media":
            df_sumo[feat] = sigmas_sumo * rng.uniform(0.8, 1.5, size=len(df_sumo))

    df_sumo["sigma_aplicado_m"] = sigmas_sumo
    print(f"  SUMO: {len(df_sumo)} ventanas")

    # Limitar SUMO a ≤50% de cada clase
    partes = [df_entr_geo, df_aug]
    geo_total = pd.concat(partes, ignore_index=True)
    for clase in CLASES:
        n_geo_clase = (geo_total["modo_real"] == clase).sum()
        n_sumo_clase = (df_sumo["modo_real"] == clase).sum()
        max_sumo = n_geo_clase  # 50% means SUMO ≤ GeoLife count
        if n_sumo_clase > max_sumo:
            idx_drop = df_sumo[df_sumo["modo_real"] == clase].index[max_sumo:]
            df_sumo = df_sumo.drop(idx_drop)

    # Mezcla final
    cols_usar = [c for c in NOMBRES_FEATURES + COLS_META if c in df_entr_geo.columns]

    for d in [df_entr_geo, df_aug, df_sumo]:
        for c in cols_usar:
            if c not in d.columns:
                d[c] = None

    df_v2 = pd.concat([df_entr_geo[cols_usar], df_aug[cols_usar], df_sumo[cols_usar]],
                       ignore_index=True)

    print(f"\nventanas_v2.parquet:")
    print(f"  Total: {len(df_v2)}")
    print(f"  Por clase: {df_v2['modo_real'].value_counts().to_dict()}")
    print(f"  Por origen: {df_v2['origen'].value_counts().to_dict()}")

    # Verificar no fuga
    usuarios_v2 = set(df_v2["usuario_id"].unique()) if "usuario_id" in df_v2.columns else set()
    fuga = usuarios_v2 & usuarios_prueba
    if fuga:
        print(f"  ¡FUGA! Usuarios de prueba en v2: {fuga}")
    else:
        print(f"  Sin fuga: 0 usuarios de prueba")

    # Balance
    for clase in CLASES:
        pct = (df_v2["modo_real"] == clase).sum() / len(df_v2) * 100
        print(f"  {clase}: {pct:.1f}%")
        if pct > 60:
            print(f"    ⚠ Supera 60%, considerar submuestreo en S2-2")

    # Guardar
    DIR_DATOS.mkdir(parents=True, exist_ok=True)
    ruta_v2 = DIR_DATOS / "ventanas_v2.parquet"
    df_v2.to_parquet(ruta_v2, index=False)
    print(f"\nGuardado: {ruta_v2} ({ruta_v2.stat().st_size / 1e6:.1f} MB)")

    cols_prueba = [c for c in cols_usar if c in df_prueba.columns]
    for c in cols_usar:
        if c not in df_prueba.columns:
            df_prueba[c] = None
    ruta_prueba = DIR_DATOS / "ventanas_prueba_geolife.parquet"
    df_prueba[cols_usar].to_parquet(ruta_prueba, index=False)
    print(f"Guardado: {ruta_prueba} ({ruta_prueba.stat().st_size / 1e6:.1f} MB)")

    return df_v2, df_prueba


if __name__ == "__main__":
    sigma = sys.argv[1] if len(sys.argv) > 1 else "mezcla"
    ejecutar(sigma)
