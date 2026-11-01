"""KPIs de búsqueda de parqueo a partir de las salidas XML de SUMO.

Uso (desde la carpeta que contiene `kpis/` y `sumo/`):
    python -m kpis.kpis --salidas sumo/salidas/base_1 --escenario base --semilla 1

Definiciones (fijas; las mismas alimentan el informe y el visor):

- Vehículos que buscan: los de `clase=busca` en la demanda. El tráfico de paso (sin parada en
  un parkingArea) y los autos de fondo (ya estacionados al inicio) se excluyen y se cuentan.
- inicio_busqueda: primer instante en que el vehículo ENTRA a un edge que está a menos de
  `--radio-busqueda-m` (300 m por defecto) de su destino, o al edge de su parkingArea objetivo
  original, lo que ocurra primero. La entrada a un edge es la salida del edge anterior en la
  ruta final de vehroute-output (exitTimes), o la hora de salida si es el primero.
- fin_busqueda: `started` de su primera parada en un parkingArea (stop-output).
- tiempo_busqueda_s = fin_busqueda - inicio_busqueda.
- distancia_busqueda_m: suma de las longitudes de los edges que el vehículo termina de
  recorrer (su exitTime cae en (inicio, fin]). El tramo del edge donde estaciona no se cuenta.
- co2_busqueda_g: integral del CO2 del emission-output en [inicio, fin): suma de
  CO2 (mg/s) x periodo (10 s) / 1000.
- ocupacion(t): plazas ocupadas / capacidad total, cada 60 s, con los intervalos
  [started, ended) de TODAS las paradas en parkingArea (una parada sin terminar dura hasta el
  fin). El KPI es su promedio en la hora pico: excluye el warm-up (15 min).
- Si un vehículo estaciona sin haber entrado a la zona del destino (p. ej. guiado por la app a
  un puesto a más de 300 m), su búsqueda es 0 s y 0 m (inicio = fin); se cuentan en
  `buscadores_sin_inicio`. En vehroute-output, un exitTime de -1 (edge aún no recorrido por un
  vehículo sin terminar) se trata como "no recorrido".
- Buscadores sin estacionar al final: no entran en las estadísticas (tiempo censurado); se
  reportan aparte con su tiempo hasta el fin de la simulación.
- Estadísticas de cada KPI: n, media, mediana, p90 e IC 95 % de la media (bootstrap, 1000
  remuestreos). Para la ocupación se usan las muestras por minuto de la hora pico.

Salidas en kpis/salidas/:
    <escenario>_<semilla>_vehiculos.csv   un vehículo que busca por fila
    <escenario>_<semilla>_ocupacion.csv   serie de ocupación cada 60 s
    kpis_<escenario>.json                 todas las semillas disponibles del escenario, con
                                          las claves del mensaje WS `kpi` del contrato
"""
import argparse
import csv
import json
import math
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

from kpis import lectores

DIR = Path(__file__).resolve().parent
DIR_SUMO = DIR.parent / "sumo"
SALIDAS = DIR / "salidas"
CLAVES_KPI = ["tiempo_busqueda_s", "distancia_busqueda_m", "co2_busqueda_g", "ocupacion_pico"]


# --- Funciones puras -------------------------------------------------------------------------

def _dist_punto_segmento(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    largo2 = dx * dx + dy * dy
    u = 0.0 if largo2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / largo2))
    return math.hypot(px - (ax + u * dx), py - (ay + u * dy))


def edges_cerca(red, x, y, radio_m):
    """Edges con algún segmento de su forma a `radio_m` o menos del punto (x, y)."""
    cerca = set()
    for edge, forma in zip(red["edge"], red["forma"]):
        puntos = forma if len(forma) > 1 else forma * 2
        if any(_dist_punto_segmento(x, y, *a, *b) <= radio_m for a, b in zip(puntos, puntos[1:])):
            cerca.add(edge)
    return cerca


def inicio_busqueda(ruta_veh, edges_objetivo):
    """Instante en que el vehículo entra por primera vez a un edge de `edges_objetivo`."""
    ruta = ruta_veh.sort_values("orden")
    entrada = float(ruta["depart"].iloc[0])
    for edge, salida in zip(ruta["edge"], ruta["salida"]):
        if edge in edges_objetivo:
            return entrada
        entrada = float(salida)
        if math.isnan(entrada):
            return None
    return None


def distancia_busqueda_m(ruta_veh, inicio, fin, longitudes):
    """Longitud de los edges que el vehículo termina de recorrer en (inicio, fin]."""
    sal = ruta_veh["salida"]
    return float(sum(longitudes.get(e, 0.0)
                     for e in ruta_veh.loc[(sal > inicio) & (sal <= fin), "edge"]))


def co2_busqueda_g(emis_veh, inicio, fin, periodo_s=10.0):
    """CO2 emitido (g) en [inicio, fin): suma de mg/s x periodo / 1000."""
    t = emis_veh["t"]
    return float(emis_veh.loc[(t >= inicio) & (t < fin), "co2_mg_s"].sum() * periodo_s / 1000.0)


def serie_ocupacion(stops, capacidad_total, fin, paso_s=60):
    """Plazas ocupadas cada `paso_s` con los intervalos [started, ended) del stop-output."""
    inicio = stops["started"].to_numpy(dtype=float)
    termino = stops["ended"].to_numpy(dtype=float)
    termino = np.where(termino < 0, fin, termino)
    ts = np.arange(0, int(fin), paso_s)
    ocupados = [int(((inicio <= t) & (t < termino)).sum()) for t in ts]
    return pd.DataFrame({"t": ts.astype(int), "ocupados": ocupados,
                         "ocupacion": [o / capacidad_total for o in ocupados]})


def resumen_estadistico(valores, n_boot=1000, semilla=0):
    """n, media, mediana, p90 e IC 95 % bootstrap de la media."""
    v = np.asarray([x for x in valores if x is not None and not math.isnan(x)], dtype=float)
    if v.size == 0:
        return {"n": 0, "media": None, "mediana": None, "p90": None, "ic95": None}
    medias = np.random.default_rng(semilla).choice(v, size=(n_boot, v.size)).mean(axis=1)
    return {"n": int(v.size), "media": float(v.mean()), "mediana": float(np.median(v)),
            "p90": float(np.percentile(v, 90)),
            "ic95": [float(np.percentile(medias, 2.5)), float(np.percentile(medias, 97.5))]}


# --- Cálculo sobre una corrida ---------------------------------------------------------------

def _cabecera_demanda(ruta):
    texto = Path(ruta).read_text(encoding="utf-8", errors="replace")[:600]
    m = re.search(r"<!-- generar_demanda\.py: (.*?) -->", texto)
    return dict(kv.split("=", 1) for kv in m.group(1).split()) if m else {}


def _destinos_xy(ruta_destinos, ruta_net):
    from pyproj import Transformer
    dx, dy, proj = lectores.leer_proyeccion(ruta_net)
    tr = Transformer.from_crs("EPSG:4326", proj, always_xy=True)
    destinos = {}
    with open(ruta_destinos, encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            x, y = tr.transform(float(fila["lon"]), float(fila["lat"]))
            destinos[fila["nombre"]] = (x + dx, y + dy)
    return destinos


def calcular(salidas, dir_sumo=DIR_SUMO, radio_busqueda_m=300.0, periodo_emision_s=10.0,
             ruta_demanda=None):
    """KPIs de una corrida. Devuelve (vehiculos, serie_ocupacion, info).

    La demanda es `ruta_demanda` si se da; si no, salidas/demanda.rou.xml (correr_base.py) o,
    en último caso, sumo/demanda/demanda.rou.xml (semilla 1).
    """
    salidas, dir_sumo = Path(salidas), Path(dir_sumo)
    ruta_net = dir_sumo / "red" / "centro.net.xml"
    ruta_dem = Path(ruta_demanda) if ruta_demanda else salidas / "demanda.rou.xml"
    if not ruta_dem.exists():
        ruta_dem = dir_sumo / "demanda" / "demanda.rou.xml"
    cab = _cabecera_demanda(ruta_dem)
    warmup = float(cab.get("warmup_s", 900))
    fin_sim = warmup + float(cab.get("duracion_s", 3600))

    red = lectores.leer_red(ruta_net)
    longitudes = dict(zip(red["edge"], red["longitud"]))
    destinos = _destinos_xy(dir_sumo / "demanda" / "destinos.csv", ruta_net)
    cerca = {n: edges_cerca(red, x, y, radio_busqueda_m) for n, (x, y) in destinos.items()}
    with open(dir_sumo / "parqueos" / "puestos.csv", encoding="utf-8") as f:
        puestos = list(csv.DictReader(f))
    edge_de_pa = {p["puesto_id"]: p["edge"] for p in puestos}
    capacidad = sum(int(p["capacidad"]) for p in puestos)

    demanda = lectores.leer_demanda(ruta_dem)
    stops = lectores.leer_stops(salidas / "stops.xml")
    primera = stops.sort_values("started").groupby("id").first()
    buscadores = demanda[demanda["clase"] == "busca"]
    ids = set(buscadores["id"])
    rutas = lectores.leer_vehroutes(salidas / "vehroutes.xml")
    rutas = rutas[rutas["id"].isin(ids)]
    por_veh = dict(tuple(rutas.groupby("id")))
    emis = lectores.leer_emisiones(salidas / "emisiones.xml", ids)
    emis_veh = dict(tuple(emis.groupby("id")))
    vacio = pd.DataFrame({"t": [], "co2_mg_s": []})

    filas, censurados, sin_inicio = [], [], 0
    for b in buscadores.itertuples():
        ruta = por_veh.get(b.id)
        if ruta is None:
            continue  # no llegó a insertarse
        nombre = b.destino_nombre or b.destino  # S1: `destino` era el nombre; S2-3: "lat,lon"
        objetivo = set(cerca.get(nombre, set()))
        if b.pa_objetivo in edge_de_pa:
            objetivo.add(edge_de_pa[b.pa_objetivo])
        ini = inicio_busqueda(ruta, objetivo)
        if b.id not in primera.index:
            if ini is not None:
                censurados.append(fin_sim - ini)
            continue
        fin = float(primera.loc[b.id, "started"])
        if ini is None or ini > fin:
            sin_inicio += 1  # estacionó sin entrar a la zona del destino: no hubo búsqueda
            ini = fin
        filas.append({
            "id": b.id, "con_app": b.con_app, "destino": nombre, "pa_objetivo": b.pa_objetivo,
            "pa_final": primera.loc[b.id, "parkingArea"], "inicio_s": ini, "fin_s": fin,
            "tiempo_busqueda_s": fin - ini,
            "distancia_busqueda_m": distancia_busqueda_m(ruta, ini, fin, longitudes),
            "co2_busqueda_g": co2_busqueda_g(emis_veh.get(b.id, vacio), ini, fin, periodo_emision_s),
        })
    vehiculos = pd.DataFrame(filas)
    serie = serie_ocupacion(stops, capacidad, fin_sim)
    info = {
        "demanda": str(ruta_dem), "warmup_s": warmup, "fin_s": fin_sim, "capacidad_total": capacidad,
        "radio_busqueda_m": radio_busqueda_m, "parametros_demanda": cab,
        "vehiculos_por_clase": demanda["clase"].value_counts().to_dict(),
        "excluidos_paso": int((demanda["clase"] == "paso").sum()),
        "excluidos_fondo": int((demanda["clase"] == "fondo").sum()),
        "buscadores": len(buscadores), "buscadores_con_kpi": len(vehiculos),
        "buscadores_sin_estacionar": len(censurados),
        "busqueda_censurada_media_s": float(np.mean(censurados)) if censurados else None,
        "buscadores_sin_inicio": sin_inicio,
    }
    return vehiculos, serie, info


def _resumen_escenario(escenario, salidas_kpi, n_boot=1000):
    """Junta todas las semillas disponibles del escenario en kpis_<escenario>.json."""
    vehs, ocup, por_semilla = [], [], {}
    for ruta in sorted(salidas_kpi.glob(f"{escenario}_*_vehiculos.csv")):
        semilla = ruta.name[len(escenario) + 1:].split("_")[0]
        v = pd.read_csv(ruta)
        info = json.loads((salidas_kpi / f"{escenario}_{semilla}_info.json").read_text(encoding="utf-8"))
        o = pd.read_csv(salidas_kpi / f"{escenario}_{semilla}_ocupacion.csv")
        o = o[(o["t"] >= info["warmup_s"]) & (o["t"] < info["fin_s"])]
        vehs.append(v)
        ocup.append(o)
        por_semilla[semilla] = {
            "tiempo_busqueda_s": resumen_estadistico(v["tiempo_busqueda_s"], n_boot),
            "distancia_busqueda_m": resumen_estadistico(v["distancia_busqueda_m"], n_boot),
            "co2_busqueda_g": resumen_estadistico(v["co2_busqueda_g"], n_boot),
            "ocupacion_pico": resumen_estadistico(o["ocupacion"], n_boot),
            "conteos": {k: info[k] for k in ("buscadores", "buscadores_con_kpi",
                                             "buscadores_sin_estacionar", "buscadores_sin_inicio",
                                             "busqueda_censurada_media_s", "excluidos_paso",
                                             "excluidos_fondo")},
        }
    v, o = pd.concat(vehs), pd.concat(ocup)
    kpis = {
        "tiempo_busqueda_s": resumen_estadistico(v["tiempo_busqueda_s"], n_boot),
        "distancia_busqueda_m": resumen_estadistico(v["distancia_busqueda_m"], n_boot),
        "co2_busqueda_g": resumen_estadistico(v["co2_busqueda_g"], n_boot),
        "ocupacion_pico": resumen_estadistico(o["ocupacion"], n_boot),
    }
    valores = {  # nombres reservados del mensaje WS `kpi` (CONTRATO §6)
        "busqueda_media_s": kpis["tiempo_busqueda_s"]["media"],
        "distancia_busqueda_media_m": kpis["distancia_busqueda_m"]["media"],
        "co2_busqueda_g": kpis["co2_busqueda_g"]["media"],
        "ocupacion_media_pico": kpis["ocupacion_pico"]["media"],
        "falsas_liberaciones_100": None,  # llega en S3
    }
    resultado = {"escenario": escenario, "semillas": sorted(por_semilla),
                 **{k: valores[k] for k in ("busqueda_media_s", "falsas_liberaciones_100")},
                 "valores": valores, "kpis": kpis, "por_semilla": por_semilla}
    destino = salidas_kpi / f"kpis_{escenario}.json"
    destino.write_text(json.dumps(resultado, indent=1, ensure_ascii=False), encoding="utf-8")
    return destino, resultado


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--salidas", required=True, help="carpeta con las salidas XML de SUMO")
    ap.add_argument("--escenario", default="base")
    ap.add_argument("--semilla", default="1")
    ap.add_argument("--radio-busqueda-m", type=float, default=300.0)
    ap.add_argument("--dir-sumo", default=str(DIR_SUMO))
    ap.add_argument("--demanda", default=None, help=".rou.xml de la corrida (escenarios de S2-3)")
    ap.add_argument("--destino", default=str(SALIDAS), help="carpeta de salida de los KPIs")
    args = ap.parse_args()
    t0 = time.time()
    vehiculos, serie, info = calcular(args.salidas, args.dir_sumo, args.radio_busqueda_m,
                                      ruta_demanda=args.demanda)
    destino = Path(args.destino)
    destino.mkdir(parents=True, exist_ok=True)
    base = f"{args.escenario}_{args.semilla}"
    vehiculos.round(3).to_csv(destino / f"{base}_vehiculos.csv", index=False)
    serie.to_csv(destino / f"{base}_ocupacion.csv", index=False)
    (destino / f"{base}_info.json").write_text(json.dumps(info, indent=1, ensure_ascii=False),
                                              encoding="utf-8")
    ruta, res = _resumen_escenario(args.escenario, destino)
    s = res["por_semilla"][str(args.semilla)]
    print(f"{base}: {info['buscadores_con_kpi']}/{info['buscadores']} buscadores con KPI, "
          f"búsqueda media {s['tiempo_busqueda_s']['media']:.1f} s, distancia "
          f"{s['distancia_busqueda_m']['media']:.0f} m, CO2 {s['co2_busqueda_g']['media']:.1f} g, "
          f"ocupación pico {100 * s['ocupacion_pico']['media']:.1f} % "
          f"({time.time() - t0:.1f} s) -> {ruta}")


if __name__ == "__main__":
    main()
