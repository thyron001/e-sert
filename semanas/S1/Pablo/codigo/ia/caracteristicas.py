"""
Extracción de características de una ventana GPS.

Librería genérica: funciona con cualquier fuente (GeoLife, SUMO, teléfono).
Todas las velocidades se calculan sobre posiciones suavizadas (mediana móvil
de 3 muestras) para robustez ante ruido GPS.
"""
import math

import numpy as np

R_TIERRA_M = 6_371_000.0


def _haversine_vec(lat1, lon1, lat2, lon2):
    """Distancia haversine vectorizada (entrada en grados, salida en metros)."""
    rlat1, rlat2 = np.radians(lat1), np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(rlat1) * np.cos(rlat2) * np.sin(dlon / 2) ** 2
    return 2 * R_TIERRA_M * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def _bearing(lat1, lon1, lat2, lon2):
    """Rumbo en grados (0-360) entre puntos consecutivos."""
    rlat1, rlat2 = np.radians(lat1), np.radians(lat2)
    dlon = np.radians(lon2 - lon1)
    x = np.sin(dlon) * np.cos(rlat2)
    y = np.cos(rlat1) * np.sin(rlat2) - np.sin(rlat1) * np.cos(rlat2) * np.cos(dlon)
    return np.degrees(np.arctan2(x, y)) % 360


def _mediana_movil(arr, k=3):
    """Mediana móvil de tamaño k, con padding en los bordes."""
    n = len(arr)
    resultado = np.empty(n)
    medio = k // 2
    for i in range(n):
        inicio = max(0, i - medio)
        fin = min(n, i + medio + 1)
        resultado[i] = np.median(arr[inicio:fin])
    return resultado


def velocidades_suavizadas(lat, lon, t):
    """
    Velocidad en m/s sobre posiciones suavizadas (mediana móvil de 3).
    Devuelve array de len(lat)-1 velocidades.
    """
    lat_s = _mediana_movil(lat)
    lon_s = _mediana_movil(lon)
    dist = _haversine_vec(lat_s[:-1], lon_s[:-1], lat_s[1:], lon_s[1:])
    dt = np.diff(t)
    dt = np.where(dt > 0, dt, 1e-6)
    return dist / dt


def desplazamiento_neto(lat, lon):
    """Distancia haversine entre el primer y último punto (metros)."""
    if len(lat) < 2:
        return 0.0
    return float(_haversine_vec(
        np.array([lat[0]]), np.array([lon[0]]),
        np.array([lat[-1]]), np.array([lon[-1]])
    )[0])


def extraer(ventana) -> dict:
    """
    Extrae ~18 características de una ventana GPS (DataFrame o dict-like).

    Parámetros:
        ventana: DataFrame con columnas t, lat, lon (y opcionalmente precision_m).

    Retorna:
        dict con las características.
    """
    lat = ventana["lat"].values if hasattr(ventana["lat"], "values") else np.array(ventana["lat"])
    lon = ventana["lon"].values if hasattr(ventana["lon"], "values") else np.array(ventana["lon"])
    t = ventana["t"].values.astype(float) if hasattr(ventana["t"], "values") else np.array(ventana["t"], dtype=float)

    n = len(lat)
    if n < 3:
        return {k: np.nan for k in _NOMBRES_FEATURES}

    vel = velocidades_suavizadas(lat, lon, t)

    # Aceleración
    dt_vel = np.diff(t[:-1])
    dt_vel = np.where(dt_vel > 0, dt_vel, 1e-6)
    acc = np.diff(vel) / dt_vel if len(vel) > 1 else np.array([0.0])

    # Jerk
    dt_acc = np.diff(t[:-2]) if len(t) > 3 else np.array([1.0])
    dt_acc = np.where(dt_acc > 0, dt_acc, 1e-6)
    jerk = np.diff(acc) / dt_acc if len(acc) > 1 else np.array([0.0])

    # Rumbo
    bearing = _bearing(lat[:-1], lon[:-1], lat[1:], lon[1:])
    cambio_rumbo = np.abs(np.diff(bearing))
    cambio_rumbo = np.minimum(cambio_rumbo, 360 - cambio_rumbo)
    dt_bearing = np.diff(t[:-1])
    dt_bearing = np.where(dt_bearing > 0, dt_bearing, 1e-6)
    tasa_rumbo = cambio_rumbo / dt_bearing if len(cambio_rumbo) > 0 else np.array([0.0])

    # Distancias
    dist_seg = _haversine_vec(lat[:-1], lon[:-1], lat[1:], lon[1:])
    dist_total = float(np.sum(dist_seg))
    desp_neto = desplazamiento_neto(lat, lon)
    rectitud = desp_neto / dist_total if dist_total > 0 else 0.0

    # Paradas y arranques
    detenido = vel < 0.5
    transiciones = np.diff(detenido.astype(int))
    n_paradas_arranques = int(np.sum(np.abs(transiciones)))

    # Precision media
    prec_media = np.nan
    if "precision_m" in ventana:
        prec = ventana["precision_m"].values if hasattr(ventana["precision_m"], "values") else np.array(ventana["precision_m"])
        if not np.all(np.isnan(prec)):
            prec_media = float(np.nanmean(prec))

    return {
        "vel_media": float(np.mean(vel)),
        "vel_mediana": float(np.median(vel)),
        "vel_p10": float(np.percentile(vel, 10)),
        "vel_p85": float(np.percentile(vel, 85)),
        "vel_max": float(np.max(vel)),
        "vel_std": float(np.std(vel)),
        "acc_media_abs": float(np.mean(np.abs(acc))),
        "acc_std": float(np.std(acc)),
        "jerk_medio_abs": float(np.mean(np.abs(jerk))) if len(jerk) > 0 else 0.0,
        "tasa_rumbo_media": float(np.mean(tasa_rumbo)) if len(tasa_rumbo) > 0 else 0.0,
        "prop_giros_30": float(np.mean(cambio_rumbo > 30)) if len(cambio_rumbo) > 0 else 0.0,
        "prop_detenido": float(np.mean(detenido)),
        "prop_lento": float(np.mean((vel >= 0.5) & (vel < 2.0))),
        "rectitud": rectitud,
        "distancia_total": dist_total,
        "precision_media": prec_media,
        "n_paradas_arranques": n_paradas_arranques,
        "desplazamiento_neto": desp_neto,
    }


_NOMBRES_FEATURES = list(extraer.__code__.co_varnames)[:0] or [
    "vel_media", "vel_mediana", "vel_p10", "vel_p85", "vel_max", "vel_std",
    "acc_media_abs", "acc_std", "jerk_medio_abs",
    "tasa_rumbo_media", "prop_giros_30",
    "prop_detenido", "prop_lento",
    "rectitud", "distancia_total",
    "precision_media", "n_paradas_arranques", "desplazamiento_neto",
]

NOMBRES_FEATURES = _NOMBRES_FEATURES
