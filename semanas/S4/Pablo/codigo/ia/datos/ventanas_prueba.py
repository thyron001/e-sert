"""Ventanas (listas de PuntoGPS) de usuarios GeoLife de prueba (no vistos en entrenamiento)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ia.ventanas import remuestrear, ventanear

RAIZ_IA = Path(__file__).resolve().parent.parent
# S2 conserva el parquet etiquetado (enlace a S1); S3 lo lee de ahi sin copiarlo.
PARQUET = RAIZ_IA.parents[3] / "S2/Pablo/codigo/ia/datos/procesados/geolife_etiquetado.parquet"


def cargar(n_ventanas: int, semilla: int = 2026, max_filas: int = 80_000):
    """Devuelve [(ventana_df, modo_real)] de hasta n_ventanas, muestreadas al azar."""
    usuarios = json.loads((RAIZ_IA / "particion_usuarios.json").read_text())["usuarios_prueba"]
    df = pd.read_parquet(PARQUET, filters=[("usuario_id", "in", usuarios)])
    if len(df) > max_filas:
        segs = df["segmento_id"].drop_duplicates()
        rng = np.random.default_rng(semilla)
        elegidos, total = [], 0
        conteo = df["segmento_id"].value_counts()
        for s in rng.permutation(segs.to_numpy()):
            elegidos.append(s)
            total += conteo[s]
            if total >= max_filas:
                break
        df = df[df["segmento_id"].isin(elegidos)]
    vs = ventanear(remuestrear(df))
    rng = np.random.default_rng(semilla)
    idx = rng.choice(len(vs), min(n_ventanas, len(vs)), replace=False)
    return [(vs[i]["_ventana"], vs[i]["modo_real"]) for i in idx]


def a_puntos(sub: pd.DataFrame) -> list[dict]:
    return [
        {"t": float(r.t), "lat": float(r.lat), "lon": float(r.lon),
         "precision_m": None if pd.isna(r.precision_m) else float(r.precision_m)}
        for r in sub.itertuples()
    ]


DIR_ESCENARIOS = RAIZ_IA.parents[3] / "S2/Pablo/codigo/ia/datos/escenarios"


def cargar_sumo(n_ventanas: int, semillas=(101, 103), sigma: int = 5, semilla: int = 2026,
                max_filas: int = 60_000):
    """Ventanas SUMO (escenario normal, ruido sigma) de las semillas reservadas. [] si no hay trazas."""
    dfs = []
    for s in semillas:
        ruta = DIR_ESCENARIOS / f"semilla_{s}" / f"trazas_sigma{sigma}.csv"
        if not ruta.exists():
            continue
        df = pd.read_csv(ruta)
        df = df[df["escenario"] == "normal"].copy()
        df["usuario_id"] = f"{s}_" + df["usuario_id"].astype(str)
        df["fuente"] = "sumo"
        dfs.append(df)
    if not dfs:
        return []
    df = pd.concat(dfs, ignore_index=True)
    rng = np.random.default_rng(semilla)
    elegidos, total = [], 0
    conteo = df["usuario_id"].value_counts()
    for u in rng.permutation(conteo.index.to_numpy()):
        elegidos.append(u)
        total += conteo[u]
        if total >= max_filas:
            break
    df = df[df["usuario_id"].isin(elegidos)]
    vs = ventanear(remuestrear(df))
    if not vs:
        return []
    idx = rng.choice(len(vs), min(n_ventanas, len(vs)), replace=False)
    return [(vs[i]["_ventana"], vs[i]["modo_real"]) for i in idx]
