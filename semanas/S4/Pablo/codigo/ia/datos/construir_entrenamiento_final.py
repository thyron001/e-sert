"""
Ventanas de entrenamiento del modelo final (`rf_final`).

A diferencia de la mezcla de S2-1 (`mezclar_datasets.py`), que "aumentaba" multiplicando algunas
características por factores aleatorios, aqui el ruido GPS AR(1) se aplica a las POSICIONES de cada
ventana y las 18 características se recalculan con el mismo código de produccion
(`ia.inferencia._features_2d`). Así el modelo ve en entrenamiento lo que verá en inferencia.

Fuentes (solo entrenamiento):
  * GeoLife: todos los usuarios que NO están en `usuarios_prueba` de `ia/particion_usuarios.json`
    (trazas de `geolife_etiquetado.parquet`, remuestreadas a 1 Hz). La mitad de las ventanas se deja
    limpia (ya trae el ruido real de GeoLife) y la otra mitad recibe ruido AR(1) con sigma ~ U(3, 15) m.
  * SUMO: episodios de parqueo grabados con `ia/grabar_episodios.py` con semillas de entrenamiento
    (por defecto 201-204; las semillas 101-105 son SOLO de prueba). Ruido AR(1) con sigma ~ U(3, 15) m
    (10 % de ventanas limpias).

    python3 -m ia.datos.construir_entrenamiento_final

Salida: ia/datos/procesados/ventanas_final.parquet (ignorado por git) y
ia/reportes/entrenamiento_final_datos.json (conteos y SHA-256 de cada entrada).
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from ia.caracteristicas import NOMBRES_FEATURES
from ia.inferencia import _features_2d

RAIZ_IA = Path(__file__).resolve().parent.parent
PARTICION = RAIZ_IA / "particion_usuarios.json"
GEOLIFE = RAIZ_IA.parents[3] / "S2/Pablo/codigo/ia/datos/procesados/geolife_etiquetado.parquet"
EPISODIOS = RAIZ_IA / "sumo" / "salidas"
SALIDA = RAIZ_IA / "datos" / "procesados" / "ventanas_final.parquet"
REPORTE = RAIZ_IA / "reportes" / "entrenamiento_final_datos.json"

CLASES = ["a_pie", "quieto", "vehiculo"]
IDX = {c: i for i, c in enumerate(CLASES)}
LARGO, PASO, PUREZA = 30, 5, 0.8
RHO = 0.8
SIGMA_MIN, SIGMA_MAX = 3.0, 15.0
M_POR_GRADO = 111_320.0
R_TIERRA = 6_371_000.0
SEMILLA = 42


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 22), b""):
            h.update(bloque)
    return h.hexdigest()


def _haversine(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * R_TIERRA * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def ventanas_serie(lat, lon, modo, relabel_quieto):
    """Ventanas de 30 s con paso de 5 s de una serie continua a 1 Hz.

    Devuelve (inicios, etiquetas) de las ventanas con pureza >= 0.8. Con `relabel_quieto`, una ventana
    a_pie/vehiculo con desplazamiento neto < 10 m y velocidad efectiva < 0.3 m/s pasa a `quieto`
    (misma regla que `ia.ventanas.ventanear`, calculada sobre la traza limpia).
    """
    n = len(lat)
    if n < LARGO:
        return np.empty(0, int), np.empty(0, int)
    inicios = np.arange(0, n - LARGO + 1, PASO)
    cuentas = np.stack([np.concatenate([[0], np.cumsum(modo == c)]) for c in range(3)])
    en_ventana = cuentas[:, inicios + LARGO] - cuentas[:, inicios]          # (3, B)
    etiqueta = en_ventana.argmax(axis=0)
    ok = en_ventana.max(axis=0) / LARGO >= PUREZA
    if relabel_quieto:
        desp = _haversine(lat[inicios], lon[inicios], lat[inicios + LARGO - 1], lon[inicios + LARGO - 1])
        quieta = (desp < 10.0) & (desp / (LARGO - 1) < 0.3) & (etiqueta != IDX["quieto"])
        etiqueta = np.where(quieta, IDX["quieto"], etiqueta)
    return inicios[ok], etiqueta[ok]


def ruido_ar1(lat, lon, sigma, rng):
    """Ruido AR(1) por eje (norte y este, rho = 0.8, desviacion `sigma` por ventana). lat/lon: (B, N)."""
    b, n = lat.shape
    z = rng.standard_normal((b, n, 2))
    e = np.empty((b, n, 2))
    e[:, 0] = sigma[:, None] * z[:, 0]
    innov = sigma[:, None] * np.sqrt(1 - RHO ** 2)
    for i in range(1, n):
        e[:, i] = RHO * e[:, i - 1] + innov * z[:, i]
    lat_n = lat + e[:, :, 0] / M_POR_GRADO
    lon_n = lon + e[:, :, 1] / (M_POR_GRADO * np.cos(np.radians(lat)))
    return lat_n, lon_n


def features_de_ventanas(lat_v, lon_v, sigma, rng):
    """18 caracteristicas de B ventanas (B, 30); sigma = 0 deja la ventana limpia (precision NaN)."""
    b = len(lat_v)
    prec = np.where(sigma[:, None] > 0, sigma[:, None] * rng.uniform(0.8, 1.5, (b, LARGO)), np.nan)
    ruidosa = sigma > 0
    if ruidosa.any():
        lat_n, lon_n = ruido_ar1(lat_v[ruidosa], lon_v[ruidosa], sigma[ruidosa], rng)
        lat_v, lon_v = lat_v.copy(), lon_v.copy()
        lat_v[ruidosa], lon_v[ruidosa] = lat_n, lon_n
    t = np.broadcast_to(np.arange(LARGO, dtype=float), (b, LARGO))
    return _features_2d(t, lat_v, lon_v, prec)


def series_geolife(usuarios_prueba):
    """Series 1 Hz continuas (lat, lon, modo) de los usuarios de entrenamiento de GeoLife."""
    from ia.ventanas import remuestrear

    df = pd.read_parquet(GEOLIFE, columns=["usuario_id", "t", "lat", "lon", "modo_real", "segmento_id"])
    df = df[~df["usuario_id"].isin(usuarios_prueba) & df["modo_real"].isin(["a_pie", "vehiculo"])]
    series = []
    for _, g in df.groupby("usuario_id", sort=True):
        r = remuestrear(g)
        if r.empty:
            continue
        for seg, s in r.groupby("segmento_id", sort=True):
            if len(s) >= LARGO:
                series.append((s["usuario_id"].iloc[0], s["lat"].to_numpy(), s["lon"].to_numpy(),
                               np.full(len(s), IDX[s["modo_real"].iloc[0]], dtype=np.int8), "geolife", 0))
    return series


def series_sumo(semillas):
    """Series 1 Hz continuas de los episodios de SUMO (modo real por segundo)."""
    series = []
    for sem in semillas:
        ruta = EPISODIOS / f"episodios_s{sem}.csv"
        df = pd.read_csv(ruta, usecols=["usuario_id", "t", "lat", "lon", "modo_real"])
        df = df[np.isfinite(df["lat"]) & np.isfinite(df["lon"])]
        for uid, g in df.groupby("usuario_id", sort=True):
            t = g["t"].to_numpy(float)
            cortes = np.flatnonzero(np.diff(t) > 1.5) + 1
            lat, lon = g["lat"].to_numpy(), g["lon"].to_numpy()
            modo = g["modo_real"].map(IDX).to_numpy(np.int8)
            for a, b in zip(np.r_[0, cortes], np.r_[cortes, len(t)]):
                if b - a >= LARGO:
                    series.append((f"{sem}_{uid}", lat[a:b], lon[a:b], modo[a:b], "sumo", sem))
        del df
    return series


def construir(series, relabel_por_origen, tope_por_clase, p_limpia, rng):
    """Muestrea ventanas por clase (hasta `tope_por_clase` por clase y origen) y calcula sus caracteristicas."""
    plan = []  # (indice de serie, inicios, etiquetas)
    conteo = np.zeros(3, int)
    for i, (uid, lat, lon, modo, origen, sem) in enumerate(series):
        ini, et = ventanas_serie(lat, lon, modo, relabel_por_origen[origen])
        if len(ini):
            plan.append((i, ini, et))
            conteo += np.bincount(et, minlength=3)
    prob = np.minimum(1.0, tope_por_clase / np.maximum(conteo, 1))
    filas, metas = [], []
    for i, ini, et in plan:
        keep = rng.random(len(ini)) < prob[et]
        if not keep.any():
            continue
        uid, lat, lon, modo, origen, sem = series[i]
        ini, et = ini[keep], et[keep]
        lat_v = sliding_window_view(lat, LARGO)[ini]
        lon_v = sliding_window_view(lon, LARGO)[ini]
        sigma = np.where(rng.random(len(ini)) < p_limpia, 0.0, rng.uniform(SIGMA_MIN, SIGMA_MAX, len(ini)))
        filas.append(features_de_ventanas(np.array(lat_v), np.array(lon_v), sigma, rng).astype(np.float32))
        metas.append(pd.DataFrame({"modo_real": [CLASES[k] for k in et], "usuario_id": uid,
                                   "origen": origen, "semilla_sumo": sem, "sigma_m": sigma, "t_inicio": ini}))
    return conteo, np.vstack(filas), pd.concat(metas, ignore_index=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--semillas", type=int, nargs="+", default=[201, 202, 203, 204])
    ap.add_argument("--tope-geolife", type=int, default=100_000, help="ventanas por clase de GeoLife")
    ap.add_argument("--tope-sumo", type=int, default=50_000, help="ventanas por clase de SUMO")
    a = ap.parse_args()

    part = json.loads(PARTICION.read_text())
    prueba = set(part["usuarios_prueba"])
    reservadas = set(part["semillas_sumo_prueba"])
    assert not (set(a.semillas) & reservadas), "las semillas 101-105 son solo de prueba"
    t0 = time.time()
    rng = np.random.default_rng(SEMILLA)

    print("Series GeoLife...", flush=True)
    s_geo = series_geolife(prueba)
    assert not ({s[0] for s in s_geo} & prueba)
    print(f"  {len(s_geo)} series ({time.time() - t0:.0f} s)", flush=True)
    c_geo, X_geo, m_geo = construir(s_geo, {"geolife": True}, a.tope_geolife, 0.5, rng)
    del s_geo
    print(f"  GeoLife: {len(X_geo)} ventanas de {c_geo.tolist()} disponibles ({time.time() - t0:.0f} s)", flush=True)

    print("Series SUMO...", flush=True)
    s_sumo = series_sumo(a.semillas)
    c_sumo, X_sumo, m_sumo = construir(s_sumo, {"sumo": False}, a.tope_sumo, 0.1, rng)
    del s_sumo
    print(f"  SUMO: {len(X_sumo)} ventanas de {c_sumo.tolist()} disponibles ({time.time() - t0:.0f} s)", flush=True)

    X = pd.DataFrame(np.vstack([X_geo, X_sumo]), columns=NOMBRES_FEATURES)
    meta = pd.concat([m_geo, m_sumo], ignore_index=True)
    df = pd.concat([X, meta], axis=1)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(SALIDA, index=False)

    entradas = {str(GEOLIFE.relative_to(RAIZ_IA.parents[3])): sha256(GEOLIFE)}
    for sem in a.semillas:
        r = EPISODIOS / f"episodios_s{sem}.csv"
        entradas[str(r.relative_to(RAIZ_IA.parents[3]))] = sha256(r)
    entradas[str(PARTICION.relative_to(RAIZ_IA.parents[3]))] = sha256(PARTICION)
    rep = {"semilla": SEMILLA, "semillas_sumo_entrenamiento": a.semillas,
           "n_ventanas": len(df), "por_origen_y_clase": df.groupby(["origen", "modo_real"]).size().rename("n")
           .reset_index().to_dict("records"),
           "ventanas_disponibles_geolife": dict(zip(CLASES, map(int, c_geo))),
           "ventanas_disponibles_sumo": dict(zip(CLASES, map(int, c_sumo))),
           "usuarios_geolife_entrenamiento": int(meta.loc[meta.origen == "geolife", "usuario_id"].nunique()),
           "usuarios_geolife": sorted(meta.loc[meta.origen == "geolife", "usuario_id"].unique().tolist()),
           "sha256_entradas": entradas, "segundos": round(time.time() - t0)}
    REPORTE.write_text(json.dumps(rep, indent=2, ensure_ascii=False))
    print(f"-> {SALIDA} ({len(df)} filas) y {REPORTE}", flush=True)


if __name__ == "__main__":
    main()
