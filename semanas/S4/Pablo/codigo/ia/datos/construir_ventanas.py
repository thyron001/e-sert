"""
Aplica remuestreo, ventaneo y extracción de características al dataset GeoLife.
Guarda ventanas_geolife.parquet con usuario_id, fuente, t_inicio, características y modo_real.

    python -m ia.datos.construir_ventanas
"""
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from tqdm import tqdm

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ia.ventanas import remuestrear, ventanear
from ia.caracteristicas import extraer

DIR_SCRIPT = Path(__file__).resolve().parent
ARCHIVO_PARQUET_IN = DIR_SCRIPT / "procesados" / "geolife_etiquetado.parquet"
ARCHIVO_PARQUET_OUT = DIR_SCRIPT / "procesados" / "ventanas_geolife.parquet"


def procesar_usuario(usuario_id: str, df_usuario: pd.DataFrame) -> list[dict]:
    """Procesa un usuario: remuestreo → ventaneo → características."""
    df_r = remuestrear(df_usuario)
    if df_r.empty:
        return []

    ventanas = ventanear(df_r)
    registros = []
    for v in ventanas:
        feats = extraer(v["_ventana"])
        registro = {
            "usuario_id": v["usuario_id"],
            "fuente": v["fuente"],
            "t_inicio": v["t_inicio"],
            "modo_real": v["modo_real"],
            "reetiquetada_quieto": v["reetiquetada_quieto"],
        }
        registro.update(feats)
        registros.append(registro)

    return registros


def ejecutar():
    print(f"Leyendo {ARCHIVO_PARQUET_IN} ...")
    df = pd.read_parquet(ARCHIVO_PARQUET_IN)
    usuarios = df["usuario_id"].unique()
    print(f"Usuarios: {len(usuarios)}")

    todos = []
    for uid in tqdm(usuarios, desc="Ventanas"):
        df_u = df[df["usuario_id"] == uid]
        registros = procesar_usuario(uid, df_u)
        todos.extend(registros)

    if not todos:
        raise RuntimeError("No se generaron ventanas.")

    df_out = pd.DataFrame(todos)
    df_out.to_parquet(ARCHIVO_PARQUET_OUT, index=False)
    print(f"\nVentanas guardadas: {ARCHIVO_PARQUET_OUT} ({len(df_out)} filas)")

    print("\nDistribución de clases:")
    print(df_out["modo_real"].value_counts().to_string())

    n_reetiq = df_out["reetiquetada_quieto"].sum()
    print(f"\nVentanas reetiquetadas como quieto: {n_reetiq}")

    return ARCHIVO_PARQUET_OUT


if __name__ == "__main__":
    ejecutar()
