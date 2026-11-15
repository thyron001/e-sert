"""Generador de trazas GPS de entrenamiento desde SUMO (para el clasificador de Pablo, S2).

Corre el escenario de Tyrone (red OSM + parkingAreas + demanda de hora pico) y le añade
peatones propios (Tyrone no tiene peatones): caminan, se detienen unos minutos y siguen. El
15 % son **peatones rápidos** (≈ 2,2 m/s), un caso difícil para el clasificador. Los autos en
**congestión** (< 7 km/h sin estar estacionados) salen solos de la hora pico.

Escribe `traci/trazas/sumo_semilla<N>.csv` con las 7 columnas del contrato (§8) y, después,
4 columnas extra: `lat_real, lon_real, velocidad_real_mps, caso`.

Dentro del contenedor, desde `semanas/S1/Freddy/codigo`:

    python3 -m traci.generar_trazas --semilla 1
    python3 -m traci.generar_trazas --semilla 1 --muestra 5000   # además, la muestra para el repo
"""

from __future__ import annotations

import argparse
import csv
import random
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Set

from .controlador import ConfigControlador, Controlador
from .gps import EmuladorGPS, muestrear_controlador
from .sumo import cargar_sumolib

AQUI = Path(__file__).resolve().parent
CFG_TYRONE = AQUI / "escenario" / "tyrone" / "sumo" / "centro_base.sumocfg"
CARPETA_TRAZAS = AQUI / "trazas"
CARPETA_SALIDAS = AQUI / "salidas"

COLUMNAS = ["usuario_id", "t", "lat", "lon", "precision_m", "velocidad_mps", "modo_real",
            "lat_real", "lon_real", "velocidad_real_mps", "caso"]


# ---------------------------------------------------------------------------
# Peatones
# ---------------------------------------------------------------------------


def generar_peatones(red, ruta: Path, semilla: int, n: int, desde: float, hasta: float,
                     frac_rapidos: float = 0.15) -> int:
    """Escribe un archivo de personas: caminar → detenerse 1–4 min → caminar. Devuelve cuántas."""
    rng = random.Random(semilla)
    aceras = [e for e in red.getEdges(withInternal=False)
              if e.getLength() > 20 and any(l.allows("pedestrian") for l in e.getLanes())]

    def carril_peatonal(e):
        return next(l for l in e.getLanes() if l.allows("pedestrian"))

    def destino_cerca(origen, minimo=200.0, maximo=800.0):
        ox, oy = origen.getBoundingBox()[:2]
        for _ in range(50):
            d = rng.choice(aceras)
            dx, dy = d.getBoundingBox()[:2]
            if minimo <= ((dx - ox) ** 2 + (dy - oy) ** 2) ** 0.5 <= maximo and d is not origen:
                return d
        return rng.choice(aceras)

    personas = []
    for i in range(n):
        a = rng.choice(aceras)
        b = destino_cerca(a)
        c = destino_cerca(b)
        rapido = rng.random() < frac_rapidos
        salida = rng.uniform(desde, desde + 0.6 * (hasta - desde))
        carril = carril_peatonal(b)
        largo = carril.getLength()
        pos = rng.uniform(0.2, 0.8) * largo
        personas.append((salida, (
            f'    <person id="p{i}" depart="{salida:.1f}" type="{"peaton_rapido" if rapido else "peaton"}">\n'
            f'        <walk from="{a.getID()}" to="{b.getID()}" arrivalPos="{pos:.1f}"/>\n'
            f'        <stop lane="{carril.getID()}" startPos="{max(0.0, pos - 1):.1f}" endPos="{min(largo, pos + 1):.1f}" '
            f'duration="{rng.uniform(60, 240):.0f}" actType="diligencia"/>\n'
            f'        <walk to="{c.getID()}"/>\n'
            f'    </person>\n')))
    personas.sort()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<routes>\n')
        # En SUMO 1.12 la velocidad de un vType es `maxSpeed` (`speed` se ignora sin avisar).
        f.write('    <vType id="peaton" vClass="pedestrian" maxSpeed="1.35"/>\n')
        f.write('    <vType id="peaton_rapido" vClass="pedestrian" maxSpeed="2.2"/>\n')
        for _, xml in personas:
            f.write(xml)
        f.write("</routes>\n")
    return len(personas)


# ---------------------------------------------------------------------------
# Proyección rápida (equivalente a convertGeo)
# ---------------------------------------------------------------------------


def conversor_red(ruta_red: Path):
    """(x, y) → (lat, lon) con la proyección de la red (`netOffset` + `projParameter`), en Python.

    Es lo mismo que hace `traci.simulation.convertGeo`, sin una llamada TraCI por punto.
    """
    import pyproj

    with ruta_red.open(encoding="utf-8") as f:
        cabecera = f.read(20_000)
    loc = re.search(r'<location netOffset="([^"]+)"[^>]*projParameter="([^"]+)"', cabecera)
    ox, oy = (float(v) for v in loc.group(1).split(","))
    proj = pyproj.Proj(loc.group(2))

    def a_geo(x: float, y: float):
        lon, lat = proj(x - ox, y - oy, inverse=True)
        return lat, lon

    return a_geo


def _valor_cfg(cfg: Path, clave: str) -> str:
    nodo = ET.parse(cfg).getroot().find(f".//{clave}")
    return nodo.get("value") if nodo is not None else ""


# ---------------------------------------------------------------------------
# Corrida
# ---------------------------------------------------------------------------


def generar(semilla: int, cfg: Path = CFG_TYRONE, duracion: float = 1800, calentamiento: float = 300,
            n_peatones: int = 150, frac_vehiculos: float = 0.3, n_fondo: int = 25,
            sigma_m: float = 5.0, salida: Optional[Path] = None) -> Dict[str, object]:
    """Corre una semilla y escribe el CSV. Devuelve un resumen con conteos por clase y caso."""
    sumolib = cargar_sumolib()
    cfg = cfg.resolve()
    ruta_red = cfg.parent / _valor_cfg(cfg, "net-file")
    red = sumolib.net.readNet(str(ruta_red), withPedestrianConnections=True)
    desde, hasta = calentamiento, calentamiento + duracion
    ruta_personas = CARPETA_SALIDAS / f"peatones_semilla{semilla}.rou.xml"
    n_pers = generar_peatones(red, ruta_personas, semilla, n_peatones, desde, hasta)

    rutas = [str(cfg.parent / r) for r in _valor_cfg(cfg, "route-files").split(",") if r]
    args = ["--route-files", ",".join(rutas + [str(ruta_personas)]),
            "--output-prefix", f"trazas{semilla}_", "--end", str(hasta + 1),
            "--no-warnings", "true"]
    rng = random.Random(1000 + semilla)
    seguidos: Set[str] = set()
    fondo = [0]

    def filtro(veh: str) -> bool:
        # Autos de fondo (estacionados desde t=0): solo una muestra. Los demás, una fracción.
        if veh.startswith("fondo"):
            if fondo[0] < n_fondo and rng.random() < 0.02:
                fondo[0] += 1
                seguidos.add(veh)
                return True
            return False
        if rng.random() < frac_vehiculos:
            seguidos.add(veh)
            return True
        return False

    conf = ConfigControlador(cfg=cfg, semilla=semilla, args_extra=args, filtro_vehiculos=filtro,
                             etiqueta=f"trazas{semilla}")
    gps = EmuladorGPS(semilla=semilla, sigma_m=sigma_m)
    salida = salida or CARPETA_TRAZAS / f"sumo_semilla{semilla}.csv"
    salida.parent.mkdir(parents=True, exist_ok=True)
    conteo: Counter = Counter()
    inicio = time.perf_counter()
    ctrl = Controlador(conf)
    ctrl.a_geo = conversor_red(ruta_red)
    with ctrl, salida.open("w", encoding="utf-8", newline="") as f:
        esc = csv.DictWriter(f, fieldnames=COLUMNAS)
        esc.writeheader()

        def hook(c: Controlador, t: float) -> None:
            for veh in c.traci.simulation.getArrivedIDList():
                gps.olvidar(f"sim_{veh}")
            for per in c.traci.simulation.getArrivedPersonIDList():
                gps.olvidar(f"ped_{per}")
            if t < desde:
                return
            for fila in muestrear_controlador(gps, c, t):
                esc.writerow({k: ("" if v is None else v) for k, v in fila.items()})
                conteo[(fila["modo_real"], fila["caso"])] += 1

        ctrl.agregar_hook(hook)
        ctrl.correr(hasta)
    resumen = {
        "semilla": semilla, "csv": str(salida.relative_to(AQUI.parent)), "filas": sum(conteo.values()),
        "peatones": n_pers, "vehiculos_seguidos": len(seguidos), "fondo_seguidos": fondo[0],
        "por_clase_y_caso": {f"{m}/{c}": n for (m, c), n in sorted(conteo.items())},
        "segundos": round(time.perf_counter() - inicio, 1),
    }
    return resumen


def escribir_muestra(origen: Path, destino: Path, filas_max: int = 5000, semilla: int = 0,
                     tramo_max: int = 300) -> Counter:
    """Muestra para el repo: tramos **consecutivos** de hasta `tramo_max` s de muchos agentes
    (sirven para ventanas de 30 s), eligiendo primero agentes de cada combinación clase/caso."""
    por_agente: Dict[str, List[dict]] = {}
    with origen.open(encoding="utf-8", newline="") as f:
        for fila in csv.DictReader(f):
            por_agente.setdefault(fila["usuario_id"], []).append(fila)
    rng = random.Random(semilla)
    grupos: Dict[tuple, List[str]] = {}
    for agente, filas in por_agente.items():
        for clave in {(r["modo_real"], r["caso"]) for r in filas}:
            grupos.setdefault(clave, []).append(agente)
    elegidos: List[str] = []
    for clave in sorted(grupos):  # al menos un agente por combinación
        candidatos = [a for a in grupos[clave] if a not in elegidos]
        if candidatos:
            elegidos.append(rng.choice(candidatos))
    resto = [a for a in por_agente if a not in elegidos]
    rng.shuffle(resto)
    filas_out: List[dict] = []
    for agente in elegidos + resto:
        if len(filas_out) >= filas_max:
            break
        filas = por_agente[agente]
        # El tramo arranca donde aparece la combinación que hizo elegir al agente (si la hay).
        inicio = 0
        for clave in sorted(grupos):
            if agente in grupos[clave]:
                inicio = next(i for i, r in enumerate(filas) if (r["modo_real"], r["caso"]) == clave)
                inicio = max(0, inicio - 30)
                break
        filas_out.extend(filas[inicio: inicio + min(tramo_max, filas_max - len(filas_out))])
    filas_out.sort(key=lambda r: (float(r["t"]), r["usuario_id"]))
    with destino.open("w", encoding="utf-8", newline="") as f:
        esc = csv.DictWriter(f, fieldnames=COLUMNAS)
        esc.writeheader()
        esc.writerows(filas_out)
    return Counter((r["modo_real"], r["caso"]) for r in filas_out)


def main() -> None:
    ap = argparse.ArgumentParser(description="Genera trazas GPS de entrenamiento desde SUMO")
    ap.add_argument("--semilla", type=int, required=True)
    ap.add_argument("--cfg", type=Path, default=CFG_TYRONE)
    ap.add_argument("--duracion", type=float, default=1800, help="Segundos grabados (30 min)")
    ap.add_argument("--calentamiento", type=float, default=300, help="Segundos sin grabar al inicio")
    ap.add_argument("--peatones", type=int, default=150)
    ap.add_argument("--frac-vehiculos", type=float, default=0.3)
    ap.add_argument("--sigma", type=float, default=5.0)
    ap.add_argument("--muestra", type=int, default=0, help="Si > 0, escribe también una muestra de N filas")
    args = ap.parse_args()
    resumen = generar(args.semilla, args.cfg, args.duracion, args.calentamiento, args.peatones,
                      args.frac_vehiculos, sigma_m=args.sigma)
    print(resumen)
    if args.muestra:
        origen = CARPETA_TRAZAS / f"sumo_semilla{args.semilla}.csv"
        destino = CARPETA_TRAZAS / f"sumo_semilla{args.semilla}_muestra.csv"
        print("muestra:", dict(escribir_muestra(origen, destino, args.muestra, args.semilla)))


if __name__ == "__main__":
    main()
