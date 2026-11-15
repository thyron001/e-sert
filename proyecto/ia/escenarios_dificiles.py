"""
Generador de escenarios difíciles de SUMO para evaluación de generalización.

Corre dentro del contenedor van3twin con las semillas reservadas 101-105.
Genera 3 tipos de escenarios: trafico_lento, peaton_rapido, normal.
Luego aplica barrido de σ GPS con aplicar_ruido_ar1.

Uso (desde el contenedor):
    python3 -m ia.escenarios_dificiles --semillas 101 102 103 104 105
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

AQUI = Path(__file__).resolve().parent
DIR_DATOS = AQUI / "datos" / "escenarios"
DIR_REPORTES = AQUI / "reportes"
SIGMAS = [3, 5, 8, 10, 15]

COLUMNAS_LIMPIA = [
    "usuario_id", "t", "lat", "lon", "precision_m",
    "velocidad_mps", "modo_real", "escenario",
]

sys.path.insert(0, os.path.join(os.environ.get("SUMO_HOME", "/usr/share/sumo"), "tools"))


def _cargar_traci():
    import traci
    return traci


def _cargar_sumolib():
    import sumolib
    return sumolib


def _conversor_red(traci_mod, net_path: Path):
    """Usa traci.simulation.convertGeo para convertir (x,y) -> (lat,lon)."""
    def a_geo(x: float, y: float):
        lon, lat = traci_mod.simulation.convertGeo(x, y)
        return lat, lon
    return a_geo


def _generar_peatones_xml(red, ruta: Path, semilla: int, n: int,
                          desde: float, hasta: float, frac_rapidos: float = 0.15):
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
            dist = ((dx - ox) ** 2 + (dy - oy) ** 2) ** 0.5
            if minimo <= dist <= maximo and d is not origen:
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
            f'    <person id="p{i}" depart="{salida:.1f}" '
            f'type="{"peaton_rapido" if rapido else "peaton"}">\n'
            f'        <walk from="{a.getID()}" to="{b.getID()}" '
            f'arrivalPos="{pos:.1f}"/>\n'
            f'        <stop lane="{carril.getID()}" '
            f'startPos="{max(0.0, pos - 1):.1f}" '
            f'endPos="{min(largo, pos + 1):.1f}" '
            f'duration="{rng.uniform(60, 240):.0f}" actType="diligencia"/>\n'
            f'        <walk to="{c.getID()}"/>\n'
            f'    </person>\n'
        )))
    personas.sort()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<routes>\n')
        f.write('    <vType id="peaton" vClass="pedestrian" maxSpeed="1.35"/>\n')
        f.write('    <vType id="peaton_rapido" vClass="pedestrian" maxSpeed="2.5"/>\n')
        f.write("</routes>\n")
        # Rewrite with persons
    with ruta.open("w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<routes>\n')
        f.write('    <vType id="peaton" vClass="pedestrian" maxSpeed="1.35"/>\n')
        f.write('    <vType id="peaton_rapido" vClass="pedestrian" maxSpeed="2.5"/>\n')
        for _, xml in personas:
            f.write(xml)
        f.write("</routes>\n")
    return len(personas)


def correr_semilla(semilla: int, cfg_path: Path, duracion: float = 1800,
                   calentamiento: float = 300, n_peatones: int = 100) -> Dict:
    traci = _cargar_traci()
    sumolib = _cargar_sumolib()

    cfg_path = cfg_path.resolve()
    net_path = cfg_path.parent / "red" / "centro.net.xml"
    red = sumolib.net.readNet(str(net_path), withPedestrianConnections=True)

    desde = calentamiento
    hasta = calentamiento + duracion

    dir_salidas = DIR_DATOS / f"semilla_{semilla}"
    dir_salidas.mkdir(parents=True, exist_ok=True)

    ruta_peatones = dir_salidas / f"peatones_{semilla}.rou.xml"
    n_pers = _generar_peatones_xml(red, ruta_peatones, semilla, n_peatones, desde, hasta)

    ruta_demanda = str(cfg_path.parent / "demanda" / "demanda.rou.xml")
    ruta_adicional = str(cfg_path.parent / "red" / "centro.poly.xml") + "," + \
                     str(cfg_path.parent / "parqueos" / "parqueos.add.xml") + "," + \
                     str(cfg_path.parent / "demanda" / "rerouters.add.xml")

    label = f"escenario_{semilla}"
    cmd = [
        "sumo", "-c", str(cfg_path),
        "--seed", str(semilla),
        "--begin", "0",
        "--end", str(int(hasta + 1)),
        "--route-files", f"{ruta_demanda},{ruta_peatones}",
        "--additional-files", ruta_adicional,
        "--no-step-log", "true",
        "--time-to-teleport", "300",
        "--ignore-route-errors", "true",
        "--no-warnings", "true",
    ]

    traci.start(cmd, label=label)
    a_geo = _conversor_red(traci, net_path)

    rng_vel = random.Random(semilla * 10 + 1)
    rng_ped = random.Random(semilla * 10 + 2)
    rng_follow = random.Random(semilla * 10 + 3)

    vehiculos_seguidos = set()
    vehiculos_lento = {}
    filas_normales = []
    filas_trafico_lento = []
    filas_peaton_rapido = []

    t_sim = traci.simulation.getTime()
    while t_sim < hasta and traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()
        t_sim = traci.simulation.getTime()

        if t_sim < desde:
            continue

        for veh in traci.simulation.getDepartedIDList():
            if rng_follow.random() < 0.4:
                vehiculos_seguidos.add(veh)
                if rng_vel.random() < 0.3:
                    max_spd = rng_vel.uniform(0.8, 2.0)
                    vehiculos_lento[veh] = max_spd

        for veh in traci.simulation.getArrivedIDList():
            vehiculos_seguidos.discard(veh)
            vehiculos_lento.pop(veh, None)

        for veh in list(vehiculos_lento):
            try:
                traci.vehicle.setMaxSpeed(veh, vehiculos_lento[veh])
            except Exception:
                vehiculos_lento.pop(veh, None)

        for per_id in traci.simulation.getDepartedPersonIDList():
            try:
                tipo = traci.person.getTypeID(per_id)
                if tipo == "peaton_rapido":
                    spd = rng_ped.uniform(1.8, 2.5)
                    traci.person.setSpeed(per_id, spd)
            except Exception:
                pass

        for veh in vehiculos_seguidos:
            try:
                x, y = traci.vehicle.getPosition(veh)
                vel = traci.vehicle.getSpeed(veh)
                lat, lon = a_geo(x, y)
                stop_state = traci.vehicle.getStopState(veh)
                estacionado = bool(int(stop_state) & 2)
                modo = "quieto" if estacionado else "vehiculo"

                fila = {
                    "usuario_id": f"sim_{veh}",
                    "t": round(t_sim, 1),
                    "lat": round(lat, 7),
                    "lon": round(lon, 7),
                    "precision_m": 0.0,
                    "velocidad_mps": round(vel, 3),
                    "modo_real": modo,
                }

                if veh in vehiculos_lento and not estacionado:
                    fila["escenario"] = "trafico_lento"
                    filas_trafico_lento.append(fila)
                else:
                    fila["escenario"] = "normal"
                    filas_normales.append(fila)
            except Exception:
                pass

        for per_id in traci.person.getIDList():
            try:
                x, y = traci.person.getPosition(per_id)
                vel = traci.person.getSpeed(per_id)
                lat, lon = a_geo(x, y)
                tipo = traci.person.getTypeID(per_id)

                stage_type = 2
                try:
                    stage_type = traci.person.getStage(per_id).type
                except Exception:
                    pass

                if stage_type == 2:
                    modo = "a_pie"
                elif stage_type == 3:
                    modo = "vehiculo"
                else:
                    modo = "quieto"

                fila = {
                    "usuario_id": f"ped_{per_id}",
                    "t": round(t_sim, 1),
                    "lat": round(lat, 7),
                    "lon": round(lon, 7),
                    "precision_m": 0.0,
                    "velocidad_mps": round(vel, 3),
                    "modo_real": modo,
                }

                if tipo.startswith("peaton_rapido") and modo == "a_pie":
                    fila["escenario"] = "peaton_rapido"
                    filas_peaton_rapido.append(fila)
                else:
                    fila["escenario"] = "normal"
                    filas_normales.append(fila)
            except Exception:
                pass

    traci.close()

    csv_limpia = dir_salidas / "trazas_limpias.csv"
    todas = filas_normales + filas_trafico_lento + filas_peaton_rapido
    todas.sort(key=lambda r: (r["t"], r["usuario_id"]))
    with csv_limpia.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS_LIMPIA)
        w.writeheader()
        w.writerows(todas)

    resumen = {
        "semilla": semilla,
        "csv_limpia": str(csv_limpia),
        "filas_total": len(todas),
        "filas_normal": len(filas_normales),
        "filas_trafico_lento": len(filas_trafico_lento),
        "filas_peaton_rapido": len(filas_peaton_rapido),
        "peatones_generados": n_pers,
        "vehiculos_seguidos": len(vehiculos_seguidos),
    }
    print(json.dumps(resumen, indent=2))
    return resumen


def aplicar_barrido_sigma(csv_limpia: Path, dir_salida: Path, semilla_base: int):
    """Aplica ruido AR(1) con σ ∈ {3,5,8,10,15} a las trazas limpias."""
    import numpy as np
    import pandas as pd
    sys.path.insert(0, str(AQUI.parent))
    from ia.ruido import aplicar_ruido_ar1
    ruta_lit = AQUI / "calibracion" / "ruido_literatura.json"
    with ruta_lit.open() as f:
        lit = json.load(f)
    rho = lit.get("rho_ar1", 0.8)

    df_limpia = pd.read_csv(csv_limpia)
    dir_salida.mkdir(parents=True, exist_ok=True)

    for sigma in SIGMAS:
        semilla_ruido = semilla_base * 1000 + sigma
        df_ruidosa = aplicar_ruido_ar1(
            df_limpia.copy(), sigma_m=sigma, rho=rho,
            p_perdida=0.02, semilla=semilla_ruido,
        )
        if "escenario" not in df_ruidosa.columns:
            escenario_map = df_limpia.set_index(
                ["usuario_id", "t"]
            )["escenario"].to_dict()
            df_ruidosa["escenario"] = df_ruidosa.apply(
                lambda r: escenario_map.get((r["usuario_id"], r["t"]), "normal"),
                axis=1,
            )
        ruta = dir_salida / f"trazas_sigma{sigma}.csv"
        df_ruidosa.to_csv(ruta, index=False)
        print(f"  σ={sigma}: {len(df_ruidosa)} filas → {ruta.name}")

    ruta_sigma0 = dir_salida / "trazas_sigma0.csv"
    df_limpia.to_csv(ruta_sigma0, index=False)
    print(f"  σ=0 (limpia): {len(df_limpia)} filas → {ruta_sigma0.name}")


def generar_hash_resumen(dir_datos: Path) -> str:
    h = hashlib.sha256()
    for csv_f in sorted(dir_datos.rglob("*.csv")):
        h.update(csv_f.name.encode())
        h.update(str(csv_f.stat().st_size).encode())
    return h.hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser(
        description="Genera escenarios difíciles de SUMO para evaluación"
    )
    ap.add_argument("--semillas", type=int, nargs="+", default=[101, 102, 103, 104, 105])
    ap.add_argument("--cfg", type=str,
                    default="proyecto/sumo/centro_base.sumocfg")
    ap.add_argument("--duracion", type=float, default=1800)
    ap.add_argument("--calentamiento", type=float, default=300)
    ap.add_argument("--peatones", type=int, default=100)
    ap.add_argument("--solo-ruido", action="store_true",
                    help="Solo aplica barrido σ a trazas existentes")
    args = ap.parse_args()

    cfg_path = Path(args.cfg)
    DIR_DATOS.mkdir(parents=True, exist_ok=True)
    resumenes = []

    if not args.solo_ruido:
        for semilla in args.semillas:
            print(f"\n{'='*60}")
            print(f"Semilla {semilla}")
            print(f"{'='*60}")
            inicio = time.perf_counter()
            res = correr_semilla(
                semilla, cfg_path, args.duracion,
                args.calentamiento, args.peatones,
            )
            res["tiempo_s"] = round(time.perf_counter() - inicio, 1)
            resumenes.append(res)

    for semilla in args.semillas:
        dir_sem = DIR_DATOS / f"semilla_{semilla}"
        csv_limpia = dir_sem / "trazas_limpias.csv"
        if csv_limpia.exists():
            print(f"\nBarrido σ para semilla {semilla}:")
            aplicar_barrido_sigma(csv_limpia, dir_sem, semilla)

    resumen_global = {
        "semillas": args.semillas,
        "sigmas": [0] + SIGMAS,
        "resumenes": resumenes,
        "hash": generar_hash_resumen(DIR_DATOS),
    }
    DIR_REPORTES.mkdir(parents=True, exist_ok=True)
    with (DIR_REPORTES / "escenarios_resumen.json").open("w") as f:
        json.dump(resumen_global, f, indent=2)
    print(f"\nResumen: {DIR_REPORTES / 'escenarios_resumen.json'}")


if __name__ == "__main__":
    main()
