"""
Limpieza y validación de ventanas GPS para inferencia robusta.

    from ia.validacion import limpiar, Calidad

    puntos_limpios, calidad = limpiar(ventana)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Calidad:
    n_validos: int
    cobertura: float
    hueco_max_s: float
    precision_mediana_m: float


# Rango válido de coordenadas (Centro Histórico de Cuenca + margen amplio)
LAT_MIN, LAT_MAX = -90.0, 90.0
LON_MIN, LON_MAX = -180.0, 180.0

PRECISION_MAX_M = 50.0
VEL_MAX_MPS = 50.0
HUECO_INTERP_MAX_S = 5.0
SPAN_MAX_S = 120.0  # una ventana dura 30 s; evita mallas gigantes con tiempos absurdos


def limpiar(
    ventana: list[dict],
    precision_max_m: float = PRECISION_MAX_M,
) -> tuple[np.ndarray, Calidad]:
    """
    Limpia una ventana GPS y retorna puntos remuestreados a 1 Hz.

    Retorna:
        (arr, calidad) donde arr tiene columnas [t, lat, lon, precision_m]
        y calidad describe la cobertura tras limpieza.
    """
    if not ventana:
        return np.empty((0, 4)), Calidad(0, 0.0, 0.0, 0.0)

    n_orig = len(ventana)

    try:
        t = np.array([p.get("t", np.nan) for p in ventana], dtype=np.float64)
        lat = np.array([p.get("lat", np.nan) for p in ventana], dtype=np.float64)
        lon = np.array([p.get("lon", np.nan) for p in ventana], dtype=np.float64)
        prec = np.array([p.get("precision_m", np.nan) for p in ventana], dtype=np.float64)
    except (TypeError, ValueError):
        t, lat, lon, prec = (
            np.array([_num(p.get(k)) for p in ventana], dtype=np.float64)
            for k in ("t", "lat", "lon", "precision_m")
        )

    # 1. Ordenar por t
    orden = np.argsort(t)
    t, lat, lon, prec = t[orden], lat[orden], lon[orden], prec[orden]

    # 2. Eliminar t duplicados (quedarse con el primero)
    _, idx_uniq = np.unique(t, return_index=True)
    t, lat, lon, prec = t[idx_uniq], lat[idx_uniq], lon[idx_uniq], prec[idx_uniq]

    # 3. Descartar NaN en t, lat, lon y fuera de rango
    valido = (
        np.isfinite(t)
        & np.isfinite(lat)
        & np.isfinite(lon)
        & (lat >= LAT_MIN) & (lat <= LAT_MAX)
        & (lon >= LON_MIN) & (lon <= LON_MAX)
    )
    t, lat, lon, prec = t[valido], lat[valido], lon[valido], prec[valido]

    # 4. Descartar puntos con precision_m > precision_max_m
    prec_ok = np.isnan(prec) | (prec <= precision_max_m)
    t, lat, lon, prec = t[prec_ok], lat[prec_ok], lon[prec_ok], prec[prec_ok]

    if len(t) >= 2 and t[-1] - t[0] > SPAN_MAX_S:
        k = t >= t[-1] - SPAN_MAX_S
        t, lat, lon, prec = t[k], lat[k], lon[k], prec[k]

    # 5. Eliminar saltos imposibles (velocidad implícita > 50 m/s)
    while len(t) >= 2:
        v = _vel_implicita(t, lat, lon)
        malos = np.flatnonzero(v > VEL_MAX_MPS)
        if malos.size == 0:
            break
        k = int(malos[0]) + 1
        t, lat, lon, prec = (np.delete(x, k) for x in (t, lat, lon, prec))

    if len(t) < 2:
        prec_med = float(np.nanmedian(prec)) if len(prec) > 0 and not np.all(np.isnan(prec)) else 0.0
        return (
            np.column_stack([t, lat, lon, prec]) if len(t) > 0 else np.empty((0, 4)),
            Calidad(int(len(t)), len(t) / max(n_orig, 1), 0.0, prec_med),
        )

    # 6. Remuestrear a 1 Hz e interpolar huecos de hasta HUECO_INTERP_MAX_S
    dts = np.diff(t)
    if np.all(dts == 1.0) and t[0] == np.floor(t[0]):
        t_out, lat_out, lon_out, prec_out = t, lat, lon, prec
        n_grid = len(t)
    else:
        t_inicio = float(np.floor(t[0]))
        t_grid = np.arange(t_inicio, np.ceil(t[-1]) + 0.5, 1.0)
        n_grid = len(t_grid)
        lat_i = np.interp(t_grid, t, lat)
        lon_i = np.interp(t_grid, t, lon)
        seg = np.clip(np.searchsorted(t, t_grid, side="right") - 1, 0, len(t) - 2)
        prec_i = prec[np.clip(np.searchsorted(t, t_grid, side="right") - 1, 0, len(t) - 1)]
        en_hueco = (t_grid > t[seg]) & (dts[seg] > HUECO_INTERP_MAX_S)
        ok = ~en_hueco
        t_out, lat_out, lon_out, prec_out = t_grid[ok], lat_i[ok], lon_i[ok], prec_i[ok]

    # Calcular métricas de calidad
    n_validos = int(len(t_out))
    cobertura = n_validos / max(n_grid, 1)

    if n_validos >= 2:
        huecos = np.diff(t_out)
        hueco_max = float(np.max(huecos)) if len(huecos) > 0 else 0.0
    else:
        hueco_max = 0.0

    prec_finitas = prec_out[np.isfinite(prec_out)]
    prec_med = float(np.median(prec_finitas)) if len(prec_finitas) > 0 else 0.0

    arr = np.column_stack([t_out, lat_out, lon_out, prec_out])
    return arr, Calidad(n_validos, cobertura, hueco_max, prec_med)


R_TIERRA_M = 6_371_000.0


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    rlat1, rlat2 = np.radians(lat1), np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(rlat1) * np.cos(rlat2) * np.sin(dlon / 2) ** 2
    return float(2 * R_TIERRA_M * np.arcsin(np.sqrt(min(a, 1.0))))


def _vel_implicita(t, lat, lon):
    rl = np.radians(lat)
    dlat = np.diff(rl)
    dlon = np.radians(np.diff(lon))
    a = np.sin(dlat / 2) ** 2 + np.cos(rl[:-1]) * np.cos(rl[1:]) * np.sin(dlon / 2) ** 2
    d = 2 * R_TIERRA_M * np.arcsin(np.sqrt(np.minimum(a, 1.0)))
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        return d / np.diff(t)


def _num(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")
