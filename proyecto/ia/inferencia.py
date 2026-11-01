"""
Inferencia del clasificador de movimiento (contrato S2).

    from ia.inferencia import clasificar

    resultado = clasificar(ventana)
    # resultado = {"modo": "vehiculo", "confianza": 0.92, "fuente": "rf"}

Para suavizado temporal por usuario:
    from ia.inferencia import ClasificadorConEstado
    cls = ClasificadorConEstado("usuario_001")
    resultado = cls.clasificar(ventana)

Variables de entorno:
  ESERT_MODELO: ruta al .joblib (default: ia/modelos/rf_v1.joblib)
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
_metadatos_cache: dict | None = None


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
    global _modelo_cache, _modelo_cargado, _metadatos_cache
    if _modelo_cargado:
        return _modelo_cache

    forzar = os.environ.get("ESERT_CLASIFICADOR", "").lower()
    if forzar == "umbral":
        _modelo_cargado = True
        _modelo_cache = None
        return None

    ruta = os.environ.get("ESERT_MODELO", "")
    if not ruta:
        ruta = str(DIR_MODELOS / "rf_v1.joblib")

    ruta_p = Path(ruta)
    if ruta_p.exists():
        from joblib import load
        _modelo_cache = load(ruta_p)
        _modelo_cargado = True

        ruta_json = ruta_p.with_suffix(".json")
        if ruta_json.exists():
            import json
            with open(ruta_json) as f:
                _metadatos_cache = json.load(f)

        return _modelo_cache

    ruta_v0 = DIR_MODELOS / "rf_v0.joblib"
    if ruta_v0.exists():
        from joblib import load
        _modelo_cache = load(ruta_v0)
        _modelo_cargado = True
        return _modelo_cache

    _modelo_cargado = True
    _modelo_cache = None
    return None


def _reset_cache():
    global _modelo_cache, _modelo_cargado, _metadatos_cache
    _modelo_cache = None
    _modelo_cargado = False
    _metadatos_cache = None


def clasificar(ventana: list[PuntoGPS]) -> ResultadoModo:
    """
    Clasifica una ventana de puntos GPS.

    Si el modelo RF esta disponible y la ventana tiene >=10 puntos,
    usa el RF. Si no, usa la regla de umbral.
    """
    import pandas as pd

    if len(ventana) < 10:
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
    if feats is None or all(np.isnan(v) for v in feats.values() if isinstance(v, float)):
        vel_media = _vel_media_puntos(ventana)
        modo = clasificar_umbral(vel_media)
        return {"modo": modo, "confianza": 1.0, "fuente": "umbral"}

    modelo = _cargar_modelo()
    if modelo is None:
        modo = clasificar_umbral(feats["vel_media"])
        return {"modo": modo, "confianza": 1.0, "fuente": "umbral"}

    X = np.array([[feats[f] for f in NOMBRES_FEATURES]])
    probas = modelo.predict_proba(X)[0]
    idx = int(np.argmax(probas))
    modo = modelo.classes_[idx]
    confianza = float(probas[idx])

    return {"modo": modo, "confianza": confianza, "fuente": "rf"}


def clasificar_con_probas(ventana: list[PuntoGPS]) -> tuple[ResultadoModo, np.ndarray | None]:
    """Como clasificar(), pero tambien devuelve el vector de probabilidades."""
    import pandas as pd

    if len(ventana) < 10:
        vel_media = _vel_media_puntos(ventana)
        modo = clasificar_umbral(vel_media)
        return {"modo": modo, "confianza": 1.0, "fuente": "umbral"}, None

    df = pd.DataFrame(ventana)
    for col in ["t", "lat", "lon"]:
        if col not in df.columns:
            vel_media = _vel_media_puntos(ventana)
            modo = clasificar_umbral(vel_media)
            return {"modo": modo, "confianza": 1.0, "fuente": "umbral"}, None

    df = df.sort_values("t").reset_index(drop=True)
    if "usuario_id" not in df.columns:
        df["usuario_id"] = "inference"
    if "segmento_id" not in df.columns:
        df["segmento_id"] = "inference_seg0"

    feats = extraer(df)
    if feats is None or all(np.isnan(v) for v in feats.values() if isinstance(v, float)):
        vel_media = _vel_media_puntos(ventana)
        modo = clasificar_umbral(vel_media)
        return {"modo": modo, "confianza": 1.0, "fuente": "umbral"}, None

    modelo = _cargar_modelo()
    if modelo is None:
        modo = clasificar_umbral(feats["vel_media"])
        return {"modo": modo, "confianza": 1.0, "fuente": "umbral"}, None

    X = np.array([[feats[f] for f in NOMBRES_FEATURES]])
    probas = modelo.predict_proba(X)[0]
    idx = int(np.argmax(probas))
    modo = modelo.classes_[idx]
    confianza = float(probas[idx])

    return {"modo": modo, "confianza": confianza, "fuente": "rf"}, probas


class ClasificadorConEstado:
    """
    Clasificador con suavizado temporal por usuario.

    Mantiene el historial de probabilidades para aplicar suavizado
    (media_movil o histeresis) sobre la secuencia de ventanas.

    Uso en el bucle TraCI de Freddy:
        cls = ClasificadorConEstado("vehiculo_001")
        for ventana in stream_ventanas():
            resultado = cls.clasificar(ventana)
    """

    def __init__(self, usuario_id: str, metodo: str | None = None, k: int | None = None):
        self.usuario_id = usuario_id
        self._suavizador = None
        self._metodo = metodo
        self._k = k
        self._inicializado = False

    def _init_suavizador(self):
        if self._inicializado:
            return
        from .suavizado import Suavizador

        metodo = self._metodo
        k = self._k

        if metodo is None or k is None:
            global _metadatos_cache
            _cargar_modelo()
            if _metadatos_cache and _metadatos_cache.get("suavizado"):
                s = _metadatos_cache["suavizado"]
                metodo = metodo or s.get("metodo", "media_movil")
                k = k or s.get("k", 3)
            else:
                metodo = metodo or "media_movil"
                k = k or 3

        self._suavizador = Suavizador(metodo=metodo, k=k)
        self._inicializado = True

    def clasificar(self, ventana: list[PuntoGPS]) -> ResultadoModo:
        resultado, probas = clasificar_con_probas(ventana)

        if probas is None or resultado["fuente"] == "umbral":
            return resultado

        self._init_suavizador()
        modo_suavizado = self._suavizador.paso(probas)

        modelo = _cargar_modelo()
        if modelo is not None:
            idx_clase = list(modelo.classes_).index(modo_suavizado) if modo_suavizado in modelo.classes_ else 0
            confianza = float(probas[idx_clase])
        else:
            confianza = resultado["confianza"]

        return {"modo": modo_suavizado, "confianza": confianza, "fuente": "rf"}

    def reset(self):
        if self._suavizador:
            self._suavizador.reset()


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
