"""
Genera ventanas desde trazas de SUMO (o MOCK si no existen).

    python -m ia.datos_sumo [--sin-mock]

Busca trazas en proyecto/traci/trazas/sumo_semilla*.csv.
Si no existen, genera trazas sintéticas AR(1) marcadas como MOCK.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ia.ventanas import remuestrear, ventanear
from ia.caracteristicas import extraer, NOMBRES_FEATURES

DIR_IA = Path(__file__).resolve().parent
DIR_TRAZAS = Path(__file__).resolve().parents[3] / "proyecto" / "traci" / "trazas"
DIR_DATOS = DIR_IA / "datos" / "procesados"
RUTA_PARTICION = DIR_IA / "particion_usuarios.json"

LAT_CENTRO = -2.8974
LON_CENTRO = -79.0045

# MOCK: reemplazar cuando Freddy entregue trazas reales en proyecto/traci/trazas/
SEMILLAS_ENTRENAMIENTO = [1, 2, 3]
DURACION_S = 3600


def _generar_traza_vehiculo(rng, semilla: int, n_vehiculos: int = 20) -> pd.DataFrame:
    """Genera trazas MOCK de vehículos simulados en el Centro Histórico."""
    filas = []
    for v in range(n_vehiculos):
        duracion = rng.integers(120, 600)
        t0 = rng.integers(0, DURACION_S - duracion)
        ts = np.arange(t0, t0 + duracion, 1.0)

        vel = rng.uniform(3.0, 15.0)  # m/s
        rumbo = rng.uniform(0, 360)
        rumbo_rad = np.radians(rumbo)
        drift_lat = vel * np.cos(rumbo_rad) / 111320.0
        drift_lon = vel * np.sin(rumbo_rad) / (111320.0 * np.cos(np.radians(LAT_CENTRO)))

        lat = LAT_CENTRO + np.cumsum(np.full(len(ts), drift_lat))
        lon = LON_CENTRO + np.cumsum(np.full(len(ts), drift_lon))

        lat += rng.normal(0, 0.5 / 111320, len(ts))
        lon += rng.normal(0, 0.5 / 111320, len(ts))

        for i in range(len(ts)):
            filas.append({
                "usuario_id": f"sumo_s{semilla}_v{v}",
                "t": float(ts[i]),
                "lat": float(lat[i]),
                "lon": float(lon[i]),
                "precision_m": np.nan,
                "velocidad_mps": float(vel + rng.normal(0, 0.3)),
                "modo_real": "vehiculo",
                "segmento_id": f"sumo_s{semilla}_v{v}_seg0",
                "fuente": "sumo",
            })
    return pd.DataFrame(filas)


def _generar_traza_peaton(rng, semilla: int, n_peatones: int = 15) -> pd.DataFrame:
    """Genera trazas MOCK de peatones."""
    filas = []
    for p in range(n_peatones):
        duracion = rng.integers(60, 400)
        t0 = rng.integers(0, DURACION_S - duracion)
        ts = np.arange(t0, t0 + duracion, 1.0)

        vel = rng.uniform(0.8, 1.8)  # m/s
        rumbo = rng.uniform(0, 360)
        rumbo_rad = np.radians(rumbo)
        drift_lat = vel * np.cos(rumbo_rad) / 111320.0
        drift_lon = vel * np.sin(rumbo_rad) / (111320.0 * np.cos(np.radians(LAT_CENTRO)))

        cambios = rng.integers(0, max(1, duracion // 60))
        puntos_cambio = sorted(rng.choice(len(ts), size=min(cambios, len(ts) - 1), replace=False))

        lat = np.zeros(len(ts))
        lon = np.zeros(len(ts))
        lat[0] = LAT_CENTRO + rng.uniform(-0.005, 0.005)
        lon[0] = LON_CENTRO + rng.uniform(-0.005, 0.005)

        for i in range(1, len(ts)):
            if i in puntos_cambio:
                rumbo = rng.uniform(0, 360)
                rumbo_rad = np.radians(rumbo)
                drift_lat = vel * np.cos(rumbo_rad) / 111320.0
                drift_lon = vel * np.sin(rumbo_rad) / (111320.0 * np.cos(np.radians(LAT_CENTRO)))
            lat[i] = lat[i - 1] + drift_lat + rng.normal(0, 0.3 / 111320)
            lon[i] = lon[i - 1] + drift_lon + rng.normal(0, 0.3 / 111320)

        for i in range(len(ts)):
            filas.append({
                "usuario_id": f"sumo_s{semilla}_p{p}",
                "t": float(ts[i]),
                "lat": float(lat[i]),
                "lon": float(lon[i]),
                "precision_m": np.nan,
                "velocidad_mps": float(vel + rng.normal(0, 0.2)),
                "modo_real": "a_pie",
                "segmento_id": f"sumo_s{semilla}_p{p}_seg0",
                "fuente": "sumo",
            })
    return pd.DataFrame(filas)


def _generar_traza_quieto(rng, semilla: int, n_quietos: int = 10) -> pd.DataFrame:
    """Genera trazas MOCK de vehículos estacionados (quietos)."""
    filas = []
    for q in range(n_quietos):
        duracion = rng.integers(60, 600)
        t0 = rng.integers(0, DURACION_S - duracion)
        ts = np.arange(t0, t0 + duracion, 1.0)

        lat_base = LAT_CENTRO + rng.uniform(-0.005, 0.005)
        lon_base = LON_CENTRO + rng.uniform(-0.005, 0.005)

        lat = lat_base + rng.normal(0, 2.0 / 111320, len(ts))
        lon = lon_base + rng.normal(0, 2.0 / 111320, len(ts))

        for i in range(len(ts)):
            filas.append({
                "usuario_id": f"sumo_s{semilla}_q{q}",
                "t": float(ts[i]),
                "lat": float(lat[i]),
                "lon": float(lon[i]),
                "precision_m": np.nan,
                "velocidad_mps": float(abs(rng.normal(0, 0.1))),
                "modo_real": "quieto",
                "segmento_id": f"sumo_s{semilla}_q{q}_seg0",
                "fuente": "sumo",
            })
    return pd.DataFrame(filas)


def cargar_trazas_sumo(semillas: list[int] | None = None) -> pd.DataFrame:
    """Carga trazas reales de SUMO o genera MOCK."""
    semillas = semillas or SEMILLAS_ENTRENAMIENTO

    trazas_reales = []
    for s in semillas:
        patron = DIR_TRAZAS / f"sumo_semilla{s}.csv"
        if patron.exists():
            df = pd.read_csv(patron)
            df["fuente"] = "sumo"
            trazas_reales.append(df)

    if trazas_reales:
        print(f"Cargadas {len(trazas_reales)} trazas reales de SUMO")
        return pd.concat(trazas_reales, ignore_index=True)

    # MOCK: reemplazar cuando Freddy entregue trazas en proyecto/traci/trazas/
    print("MOCK: generando trazas sintéticas (no hay trazas de Freddy)")
    todos = []
    for s in semillas:
        rng = np.random.default_rng(s * 1000)
        todos.append(_generar_traza_vehiculo(rng, s))
        todos.append(_generar_traza_peaton(rng, s))
        todos.append(_generar_traza_quieto(rng, s))
    return pd.concat(todos, ignore_index=True)


def procesar_sumo(df_trazas: pd.DataFrame) -> pd.DataFrame:
    """Remuestrea, ventanea y extrae características de trazas SUMO."""
    print(f"  Remuestreando {len(df_trazas)} puntos...")
    df_1hz = remuestrear(df_trazas)
    if df_1hz.empty:
        return pd.DataFrame()

    print(f"  Ventaneando {len(df_1hz)} puntos a 1 Hz...")
    ventanas_meta = ventanear(df_1hz)
    print(f"  {len(ventanas_meta)} ventanas generadas")

    registros = []
    descartadas = 0
    for vm in ventanas_meta:
        sub = vm["_ventana"]
        feats = extraer(sub)
        if feats is None or all(np.isnan(v) for v in feats.values() if isinstance(v, float)):
            descartadas += 1
            continue
        feats["modo_real"] = vm["modo_real"]
        feats["usuario_id"] = vm["usuario_id"]
        feats["grupo"] = vm["usuario_id"]
        feats["t_inicio"] = vm["t_inicio"]
        feats["origen"] = "sumo"
        feats["sigma_aplicado_m"] = 0.0
        feats["aumentada"] = False
        registros.append(feats)

    if descartadas:
        print(f"  {descartadas} ventanas descartadas (features nulas)")
    return pd.DataFrame(registros)


def ejecutar():
    with open(RUTA_PARTICION) as f:
        particion = json.load(f)

    semillas_prueba = set(particion["semillas_sumo_prueba"])
    semillas_usar = [s for s in SEMILLAS_ENTRENAMIENTO if s not in semillas_prueba]
    print(f"Semillas de entrenamiento: {semillas_usar}")
    print(f"Semillas reservadas (prueba): {list(semillas_prueba)}")

    df_trazas = cargar_trazas_sumo(semillas_usar)
    print(f"Trazas cargadas: {len(df_trazas)} puntos, {df_trazas['usuario_id'].nunique()} usuarios")
    print(f"  Distribución: {df_trazas['modo_real'].value_counts().to_dict()}")

    df_ventanas = procesar_sumo(df_trazas)
    print(f"\nVentanas SUMO: {len(df_ventanas)}")
    if not df_ventanas.empty:
        print(f"  Distribución: {df_ventanas['modo_real'].value_counts().to_dict()}")

    DIR_DATOS.mkdir(parents=True, exist_ok=True)
    ruta = DIR_DATOS / "ventanas_sumo.parquet"
    df_ventanas.to_parquet(ruta, index=False)
    print(f"Guardado: {ruta} ({ruta.stat().st_size / 1e6:.1f} MB)")

    return df_ventanas


if __name__ == "__main__":
    ejecutar()
