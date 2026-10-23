"""
Inferencia del clasificador de movimiento (contrato §2).

    from ia.inferencia import clasificar

    resultado = clasificar(ventana)
    # resultado = {"modo": "vehiculo", "confianza": 0.92, "fuente": "rf"}

Variables de entorno:
  ESERT_MODELO: ruta al .joblib (default: ia/modelos/rf_v0.joblib)
  ESERT_CLASIFICADOR: "rf" | "umbral" (default: intenta rf, fallback a umbral)
"""
import os
from pathlib import Path
from typing import TypedDict

import numpy as np

from .caracteristicas import NOMBRES_FEATURES, extraer
from .umbral import clasificar_umbral
from .ventanas import remuestrear, ventanear

DIR_MODELOS = Path(__file__).resolve().parent / "modelos"

_modelo_cache = None
_modelo_cargado = False


class PuntoGPS(TypedDict, total=False):
    t: float
    lat: float
    lon: float
    precision_m: float | None


class ResultadoModo(TypedDict):
    modo: str
    confianza: float
    fuente: str


def _cargar_modelo():
    global _modelo_cache, _modelo_cargado
    if _modelo_cargado:
        return _modelo_cache

    forzar = os.environ.get("ESERT_CLASIFICADOR", "").lower()
    if forzar == "umbral":
        _modelo_cargado = True
        _modelo_cache = None
        return None

    ruta = os.environ.get("ESERT_MODELO", "")
    if not ruta:
        ruta = str(DIR_MODELOS / "rf_v0.joblib")

    ruta_p = Path(ruta)
    if ruta_p.exists():
        from joblib import load
        _modelo_cache = load(ruta_p)
        _modelo_cargado = True
        return _modelo_cache

    _modelo_cargado = True
    _modelo_cache = None
    return None


def _reset_cache():
    global _modelo_cache, _modelo_cargado
    _modelo_cache = None
    _modelo_cargado = False


def clasificar(ventana: list[PuntoGPS]) -> ResultadoModo:
    """
    Clasifica una ventana de puntos GPS.

    Si el modelo RF está disponible y la ventana tiene cobertura suficiente,
    usa el RF. Si no, usa la regla de umbral.
    """
    import pandas as pd

    if len(ventana) < 24:
        vel_media = _vel_media_puntos(ventana)
        modo = clasificar_umbral(vel_media)
        return {"modo": modo, "confianza": 1.0, "fuente": "umbral"}

    df = pd.DataFrame(ventana)
    for col in ["t", "lat", "lon"]:
        if col not in df.columns:
            vel_media = _vel_media_puntos(ventana)
            modo = clasificar_umbral(vel_media)
            return {"modo": modo, "confianza": 1.0, "fuente": "umbral"}

    df = df.sort_values("t").reset_index(drop=True)
    if "usuario_id" not in df.columns:
        df["usuario_id"] = "inference"
    if "segmento_id" not in df.columns:
        df["segmento_id"] = "inference_seg0"

    feats = extraer(df)

    modelo = _cargar_modelo()
    if modelo is None:
        modo = clasificar_umbral(feats["vel_media"])
        return {"modo": modo, "confianza": 1.0, "fuente": "umbral"}

    X = np.array([[feats[f] for f in NOMBRES_FEATURES]])
    modo = modelo.predict(X)[0]
    probas = modelo.predict_proba(X)[0]
    confianza = float(max(probas))

    return {"modo": modo, "confianza": confianza, "fuente": "rf"}


def _vel_media_puntos(ventana: list[PuntoGPS]) -> float:
    if len(ventana) < 2:
        return 0.0
    from .caracteristicas import _haversine_vec
    lats = [p["lat"] for p in ventana]
    lons = [p["lon"] for p in ventana]
    ts = [p["t"] for p in ventana]
    dist = _haversine_vec(
        np.array(lats[:-1]), np.array(lons[:-1]),
        np.array(lats[1:]), np.array(lons[1:])
    )
    dt = np.diff(ts)
    dt = np.where(np.array(dt) > 0, dt, 1e-6)
    return float(np.sum(dist) / np.sum(dt))
