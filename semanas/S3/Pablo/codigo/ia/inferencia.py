"""
Servicio de inferencia del clasificador de movimiento (contrato §2).

    from ia.inferencia import clasificar, clasificar_lote

    resultado = clasificar(ventana)
    resultados = clasificar_lote(ventanas)

Robusto ante huecos, duplicados, ruido y datos faltantes.
Latencia objetivo: p95 < 5 ms individual, < 0.5 ms/ventana en lote.
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import warnings
from pathlib import Path
from typing import TypedDict

import numpy as np

from .caracteristicas import (
    NOMBRES_FEATURES,
    R_TIERRA_M,
    _haversine_vec,
    velocidades_suavizadas,
    desplazamiento_neto as _desplaz_neto,
    _mediana_movil,
    _bearing,
)
from .umbral import UMBRAL_VEHICULO_MPS, UMBRAL_QUIETO_MPS
from .validacion import limpiar, Calidad

DIR_MODELOS = Path(__file__).resolve().parent / "modelos"
META_PATH = DIR_MODELOS / "rf_v1.meta.json"

_warn_modelo_emitido = False


class PuntoGPS(TypedDict, total=False):
    t: float
    lat: float
    lon: float
    precision_m: float | None


class ResultadoModo(TypedDict):
    modo: str
    confianza: float
    fuente: str


# ── Carga perezosa del modelo ──────────────────────────────────────────────


@functools.lru_cache(maxsize=1)
def _cargar_meta() -> dict | None:
    ruta = META_PATH
    alt = DIR_MODELOS / "rf_v1.json"
    for r in (ruta, alt):
        if r.exists():
            with open(r) as f:
                return json.load(f)
    return None


@functools.lru_cache(maxsize=1)
def _cargar_modelo():
    forzar = os.environ.get("ESERT_CLASIFICADOR", "").lower()
    if forzar == "umbral":
        return None

    ruta_env = os.environ.get("ESERT_MODELO", "")
    ruta = Path(ruta_env) if ruta_env else DIR_MODELOS / "rf_v1.joblib"

    if not ruta.exists():
        return None

    try:
        from joblib import load as jl_load
        modelo = jl_load(ruta)
    except Exception:
        return None

    meta = _cargar_meta()
    if meta:
        sk_esperada = meta.get("sklearn_version", "")
        try:
            import sklearn
            if sk_esperada and sklearn.__version__ != sk_esperada:
                warnings.warn(
                    f"sklearn {sklearn.__version__} != modelo entrenado con {sk_esperada}",
                    stacklevel=2,
                )
        except ImportError:
            pass

        sha_esperado = meta.get("joblib_sha256", "")
        if sha_esperado:
            h = hashlib.sha256()
            with open(ruta, "rb") as f:
                for bloque in iter(lambda: f.read(1 << 20), b""):
                    h.update(bloque)
            if h.hexdigest() != sha_esperado:
                warnings.warn("SHA-256 del modelo no coincide con rf_v1.meta.json", stacklevel=2)

    try:
        from .bosque_plano import BosquePlano
        return BosquePlano(modelo)
    except Exception:
        return modelo


def _orden_features() -> list[str]:
    meta = _cargar_meta()
    if meta and "features" in meta:
        return meta["features"]
    return list(NOMBRES_FEATURES)


def _reset_cache():
    _cargar_modelo.cache_clear()
    _cargar_meta.cache_clear()
    global _warn_modelo_emitido
    _warn_modelo_emitido = False


# ── Extracción de features sin pandas ──────────────────────────────────────


def _mediana3(x: np.ndarray) -> np.ndarray:
    """Mediana móvil de 3 a lo largo del eje 1 (bordes: media de 2)."""
    r = np.empty_like(x)
    a, b, c = x[:, :-2], x[:, 1:-1], x[:, 2:]
    r[:, 1:-1] = np.maximum(np.minimum(a, b), np.minimum(np.maximum(a, b), c))
    r[:, 0] = (x[:, 0] + x[:, 1]) / 2
    r[:, -1] = (x[:, -2] + x[:, -1]) / 2
    return r


def _features_2d(t, lat, lon, prec) -> np.ndarray:
    """Características de B ventanas de N puntos (arrays (B, N)). Devuelve (B, F)."""
    ls, os_ = _mediana3(lat), _mediana3(lon)
    dt = np.diff(t, axis=1)
    dt = np.where(dt > 0, dt, 1e-6)
    vel = _haversine_vec(ls[:, :-1], os_[:, :-1], ls[:, 1:], os_[:, 1:]) / dt

    dt2 = np.diff(t[:, :-1], axis=1)
    dt2 = np.where(dt2 > 0, dt2, 1e-6)
    acc = np.diff(vel, axis=1) / dt2
    if acc.shape[1] > 1:
        dt3 = np.diff(t[:, :-2], axis=1)
        dt3 = np.where(dt3 > 0, dt3, 1e-6)
        jerk = np.diff(acc, axis=1) / dt3
        jerk_m = np.mean(np.abs(jerk), axis=1)
    else:
        jerk_m = np.zeros(len(t))

    rumbo = _bearing(lat[:, :-1], lon[:, :-1], lat[:, 1:], lon[:, 1:])
    cr = np.abs(np.diff(rumbo, axis=1))
    cr = np.minimum(cr, 360 - cr)
    tasa = cr / dt2

    dist_total = np.sum(_haversine_vec(lat[:, :-1], lon[:, :-1], lat[:, 1:], lon[:, 1:]), axis=1)
    desp = _haversine_vec(lat[:, 0], lon[:, 0], lat[:, -1], lon[:, -1])
    rectitud = np.where(dist_total > 0, desp / np.where(dist_total > 0, dist_total, 1.0), 0.0)

    detenido = vel < 0.5
    n_paradas = np.sum(np.abs(np.diff(detenido.astype(np.int8), axis=1)), axis=1)

    fin = np.isfinite(prec)
    cuenta = fin.sum(axis=1)
    prec_media = np.where(
        cuenta > 0, np.where(fin, prec, 0.0).sum(axis=1) / np.maximum(cuenta, 1), np.nan
    )
    p10, p85 = np.percentile(vel, (10, 85), axis=1)

    f = {
        "vel_media": vel.mean(axis=1),
        "vel_mediana": np.median(vel, axis=1),
        "vel_p10": p10,
        "vel_p85": p85,
        "vel_max": vel.max(axis=1),
        "vel_std": vel.std(axis=1),
        "acc_media_abs": np.mean(np.abs(acc), axis=1),
        "acc_std": acc.std(axis=1),
        "jerk_medio_abs": jerk_m,
        "tasa_rumbo_media": tasa.mean(axis=1),
        "prop_giros_30": np.mean(cr > 30, axis=1),
        "prop_detenido": detenido.mean(axis=1),
        "prop_lento": np.mean((vel >= 0.5) & (vel < 2.0), axis=1),
        "rectitud": rectitud,
        "distancia_total": dist_total,
        "precision_media": prec_media,
        "n_paradas_arranques": n_paradas.astype(np.float64),
        "desplazamiento_neto": desp,
    }
    return np.stack([f[n] for n in _orden_features()], axis=1)


def _extraer_features_np(arr: np.ndarray) -> np.ndarray | None:
    """Características de una ventana limpia (N, 4) = [t, lat, lon, precision_m]."""
    if arr.shape[0] < 3:
        return None
    return _features_2d(arr[None, :, 0], arr[None, :, 1], arr[None, :, 2], arr[None, :, 3])[0]


def _extraer_features_lote(arrs: list[np.ndarray]) -> list[np.ndarray | None]:
    """Como _extraer_features_np, agrupando ventanas por longitud."""
    out: list[np.ndarray | None] = [None] * len(arrs)
    grupos: dict[int, list[int]] = {}
    for i, a in enumerate(arrs):
        if a.shape[0] >= 3:
            grupos.setdefault(a.shape[0], []).append(i)
    for idx in grupos.values():
        S = np.stack([arrs[i] for i in idx])
        F = _features_2d(S[:, :, 0], S[:, :, 1], S[:, :, 2], S[:, :, 3])
        for j, i in enumerate(idx):
            out[i] = F[j]
    return out


# ── Clasificación por umbral ──────────────────────────────────────────────


def _umbral_desde_vel(vel_media: float) -> str:
    if vel_media > UMBRAL_VEHICULO_MPS:
        return "vehiculo"
    if vel_media < UMBRAL_QUIETO_MPS:
        return "quieto"
    return "a_pie"


def _vel_media_arr(arr: np.ndarray) -> float:
    """Velocidad media (m/s) de una ventana limpia: distancia total / duracion."""
    if arr.shape[0] < 2:
        return 0.0
    dist = _haversine_vec(arr[:-1, 1], arr[:-1, 2], arr[1:, 1], arr[1:, 2])
    dur = arr[-1, 0] - arr[0, 0]
    return float(np.sum(dist) / dur) if dur > 0 else 0.0


def _vel_umbral(arr: np.ndarray) -> float:
    if arr.shape[0] < 3:
        return _vel_media_arr(arr)
    return float(np.mean(velocidades_suavizadas(arr[:, 1], arr[:, 2], arr[:, 0])))


# ── API pública ────────────────────────────────────────────────────────────


MODOS_VALIDOS = {"a_pie", "quieto", "vehiculo"}
COBERTURA_MIN_RF = 0.6
HUECO_MAX_RF_S = 10.0
PUNTOS_MIN_UMBRAL = 5


def _validar_entrada(ventana) -> None:
    if not isinstance(ventana, list) or not all(isinstance(p, dict) for p in ventana):
        raise TypeError("ventana debe ser una lista de puntos (dict con t, lat, lon)")


def clasificar(
    ventana: list[PuntoGPS],
    previo: ResultadoModo | None = None,
) -> ResultadoModo:
    """
    Clasifica una ventana de puntos GPS.

    Estrategia de fallback:
    - cobertura ≥ 0.6 y hueco_max ≤ 10s → RF (fuente: "rf")
    - cobertura menor pero ≥ 5 puntos → umbral con confianza × cobertura
    - < 5 puntos → previo con confianza ×0.5, o umbral con confianza 0
    - modelo no disponible → umbral + warnings.warn una sola vez
    """
    _validar_entrada(ventana)

    if len(ventana) == 0:
        if previo is not None:
            return ResultadoModo(
                modo=previo["modo"],
                confianza=previo["confianza"] * 0.5,
                fuente=previo["fuente"],
            )
        return ResultadoModo(modo="quieto", confianza=0.0, fuente="umbral")

    arr, cal = limpiar(ventana)

    if cal.n_validos < PUNTOS_MIN_UMBRAL:
        if previo is not None:
            return ResultadoModo(
                modo=previo["modo"],
                confianza=max(previo["confianza"] * 0.5, 0.0),
                fuente=previo["fuente"],
            )
        vel = _vel_media_arr(arr)
        return ResultadoModo(modo=_umbral_desde_vel(vel), confianza=0.0, fuente="umbral")

    usar_rf = cal.cobertura >= COBERTURA_MIN_RF and cal.hueco_max_s <= HUECO_MAX_RF_S

    if usar_rf:
        feats = _extraer_features_np(arr)
        if feats is not None:
            modelo = _intentar_modelo()
            if modelo is not None:
                try:
                    probas = modelo.predict_proba(feats.reshape(1, -1))[0]
                    idx = int(np.argmax(probas))
                    return ResultadoModo(
                        modo=str(modelo.classes_[idx]), confianza=float(probas[idx]), fuente="rf"
                    )
                except Exception:
                    _avisar_una_vez("predict_proba fallo, usando fallback por umbral")

    vel = _vel_umbral(arr)
    modo = _umbral_desde_vel(vel)
    conf = 1.0 * cal.cobertura
    return ResultadoModo(modo=modo, confianza=conf, fuente="umbral")


def clasificar_lote(
    ventanas: list[list[PuntoGPS]],
    previos: list[ResultadoModo | None] | None = None,
    con_probas: bool = False,
):
    """
    Clasifica un lote de ventanas con una sola llamada a predict_proba.

    Con `con_probas=True` devuelve `(resultados, probas)`, donde `probas[i]` es el vector de
    probabilidades en el orden a_pie, quieto, vehiculo (None si esa ventana uso el umbral).
    """
    if previos is None:
        previos = [None] * len(ventanas)

    limpias = []
    calidades = []
    for v in ventanas:
        _validar_entrada(v)
        a, c = limpiar(v)
        limpias.append(a)
        calidades.append(c)

    rf_indices = []
    rf_features = []
    resultados: list[ResultadoModo | None] = [None] * len(ventanas)
    probas_out: list[np.ndarray | None] = [None] * len(ventanas)

    modelo = _intentar_modelo()

    for i, (arr, cal, prev) in enumerate(zip(limpias, calidades, previos)):
        if cal.n_validos < PUNTOS_MIN_UMBRAL:
            if prev is not None:
                resultados[i] = ResultadoModo(
                    modo=prev["modo"],
                    confianza=max(prev["confianza"] * 0.5, 0.0),
                    fuente=prev["fuente"],
                )
            else:
                vel = _vel_media_arr(arr)
                resultados[i] = ResultadoModo(
                    modo=_umbral_desde_vel(vel), confianza=0.0, fuente="umbral"
                )
            continue

        usar_rf = cal.cobertura >= COBERTURA_MIN_RF and cal.hueco_max_s <= HUECO_MAX_RF_S
        if usar_rf and modelo is not None and arr.shape[0] >= 3:
            rf_indices.append(i)
            continue

        vel = _vel_umbral(arr)
        resultados[i] = ResultadoModo(
            modo=_umbral_desde_vel(vel),
            confianza=1.0 * cal.cobertura,
            fuente="umbral",
        )

    if rf_indices and modelo is not None:
        rf_features = _extraer_features_lote([limpias[i] for i in rf_indices])
        try:
            probas_all = modelo.predict_proba(np.vstack(rf_features))
            clases = modelo.classes_
            for j, idx_orig in enumerate(rf_indices):
                idx_max = int(np.argmax(probas_all[j]))
                probas_out[idx_orig] = probas_all[j]
                resultados[idx_orig] = ResultadoModo(
                    modo=str(clases[idx_max]),
                    confianza=float(probas_all[j][idx_max]),
                    fuente="rf",
                )
        except Exception:
            _avisar_una_vez("predict_proba fallo, usando fallback por umbral")
            for idx_orig in rf_indices:
                arr = limpias[idx_orig]
                resultados[idx_orig] = ResultadoModo(
                    modo=_umbral_desde_vel(_vel_umbral(arr)),
                    confianza=calidades[idx_orig].cobertura,
                    fuente="umbral",
                )

    if con_probas:
        return resultados, probas_out
    return resultados  # type: ignore[return-value]


def _avisar_una_vez(msg: str) -> None:
    global _warn_modelo_emitido
    if not _warn_modelo_emitido:
        warnings.warn(msg, stacklevel=3)
        _warn_modelo_emitido = True


def _intentar_modelo():
    try:
        modelo = _cargar_modelo()
    except Exception:
        modelo = None
    if modelo is None:
        _avisar_una_vez("Modelo RF no disponible, usando fallback por umbral")
    return modelo


# ── Clasificador con estado (suavizado temporal) ──────────────────────────


class ClasificadorConEstado:
    """
    Clasificador con suavizado temporal por usuario (histéresis k=1).
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
            meta = _cargar_meta()
            if meta and meta.get("suavizado"):
                s = meta["suavizado"]
                metodo = metodo or s.get("metodo", "media_movil")
                k = k or s.get("k", 3)
            else:
                metodo = metodo or "media_movil"
                k = k or 3

        self._suavizador = Suavizador(metodo=metodo, k=k)
        self._inicializado = True

    def clasificar(self, ventana: list[PuntoGPS], previo: ResultadoModo | None = None) -> ResultadoModo:
        resultado = clasificar(ventana, previo)

        if resultado["fuente"] != "rf":
            return resultado

        modelo = _cargar_modelo()
        if modelo is None:
            return resultado

        arr, cal = limpiar(ventana)
        feats = _extraer_features_np(arr)
        if feats is None:
            return resultado

        X = feats.reshape(1, -1)
        probas = modelo.predict_proba(X)[0]

        self._init_suavizador()
        modo_suavizado = self._suavizador.paso(probas)

        if modo_suavizado in list(modelo.classes_):
            idx_clase = list(modelo.classes_).index(modo_suavizado)
            confianza = float(probas[idx_clase])
        else:
            confianza = resultado["confianza"]

        return ResultadoModo(modo=modo_suavizado, confianza=confianza, fuente="rf")

    def reset(self):
        if self._suavizador:
            self._suavizador.reset()
