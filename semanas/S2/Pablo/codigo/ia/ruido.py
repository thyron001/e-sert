"""
Ruido GPS AR(1) para trazas de movilidad.

Aplica ruido autocorrelacionado a coordenadas GPS, simula pérdida de puntos
y recalcula velocidades, siguiendo el formato CSV del contrato §7.
"""

import numpy as np
import pandas as pd


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en metros entre dos puntos (lat/lon en grados)."""
    R = 6_371_000.0
    rlat1, rlat2 = np.radians(lat1), np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(rlat1) * np.cos(rlat2) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def _haversine_vec(lat1: np.ndarray, lon1: np.ndarray,
                   lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    """Versión vectorizada de haversine (metros)."""
    R = 6_371_000.0
    rlat1, rlat2 = np.radians(lat1), np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(rlat1) * np.cos(rlat2) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def mezcla_sigma(rng: np.random.Generator, n: int,
                 sigma_min: float = 3.0, sigma_max: float = 15.0) -> np.ndarray:
    """Genera n valores de sigma uniformemente entre sigma_min y sigma_max.

    Útil para data augmentation: asignar un sigma distinto a cada
    ventana o segmento de trazas.
    """
    return rng.uniform(sigma_min, sigma_max, size=n)


def aplicar_ruido_ar1(df: pd.DataFrame, sigma_m: float, rho: float = 0.8,
                      p_perdida: float = 0.05, semilla: int = 42) -> pd.DataFrame:
    """Aplica ruido GPS AR(1) a un DataFrame de trazas.

    Parámetros
    ----------
    df : DataFrame con columnas usuario_id, t, lat, lon, precision_m,
         velocidad_mps, modo_real (formato contrato §7).
    sigma_m : desviación estándar del ruido GPS en metros.
    rho : coeficiente de autocorrelación AR(1).
    p_perdida : probabilidad de eliminar cada punto (simula pérdida de señal).
    semilla : semilla para reproducibilidad.

    Retorna
    -------
    DataFrame nuevo con ruido aplicado, velocidades recalculadas y
    puntos eliminados aleatoriamente.
    """
    rng = np.random.default_rng(semilla)
    out = df.copy()

    n = len(out)
    innovacion = np.sqrt(1 - rho ** 2)

    # Ruido AR(1) por eje
    ruido_norte = np.zeros(n)
    ruido_este = np.zeros(n)
    ruido_norte[0] = rng.normal(0, sigma_m)
    ruido_este[0] = rng.normal(0, sigma_m)
    for i in range(1, n):
        ruido_norte[i] = rho * ruido_norte[i - 1] + innovacion * rng.normal(0, sigma_m)
        ruido_este[i] = rho * ruido_este[i - 1] + innovacion * rng.normal(0, sigma_m)

    # Proyección equirectangular: metros a grados
    lat_rad = np.radians(out["lat"].values)
    delta_lat = ruido_norte / 111_320.0
    delta_lon = ruido_este / (111_320.0 * np.cos(lat_rad))

    out["lat"] = out["lat"] + delta_lat
    out["lon"] = out["lon"] + delta_lon

    # Actualizar precision_m
    out["precision_m"] = sigma_m * rng.uniform(0.8, 1.5, size=n)

    # Pérdida de puntos
    conservar = rng.random(n) >= p_perdida
    out = out.loc[conservar].reset_index(drop=True)

    # Recalcular velocidad_mps por usuario
    grupos = []
    for _, g in out.groupby("usuario_id", sort=False):
        g = g.copy()
        lats = g["lat"].values
        lons = g["lon"].values
        ts = g["t"].values.astype(float)

        vel = np.zeros(len(g))
        if len(g) > 1:
            dist = _haversine_vec(lats[:-1], lons[:-1], lats[1:], lons[1:])
            dt = np.diff(ts)
            dt[dt == 0] = 1e-6
            vel[1:] = dist / dt
        vel[0] = vel[1] if len(g) > 1 else 0.0
        g["velocidad_mps"] = vel
        grupos.append(g)

    return pd.concat(grupos, ignore_index=True)
