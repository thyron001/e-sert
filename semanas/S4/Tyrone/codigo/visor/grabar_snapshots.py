"""Graba snapshots del contrato (mensaje WS `snapshot`) desde el escenario base con TraCI.

Uso (dentro del contenedor van3twin, desde semanas/S2/Tyrone/codigo/visor):
    python3 grabar_snapshots.py [--desde 1800] [--duracion 900] [--salida datos/snapshots.jsonl]

Simula sin grabar hasta --desde (por defecto t = 1800 s, en plena hora pico) y luego escribe
una línea JSON por segundo durante --duracion segundos. Cada línea es un `MensajeSnapshot` de
`comun/esquemas.py`: vehículos `sim_<vehId>` con lat/lon, `estado` y `con_app`; peatones
`ped_<personId>`; ocupación de cada parkingArea; y `espejos`.

- Los autos de fondo estacionados no se envían: son ~4900 marcadores quietos que ya se ven en la
  ocupación de los puestos. Sí se envían mientras circulan.
- lat/lon se calculan con pyproj y el netOffset de la red, vectorizado. Es equivalente a
  traci.simulation.convertGeo (se comprueba con una muestra al iniciar) pero mucho más rápido
  que una llamada TraCI por vehículo y segundo.
"""
import argparse
import json
import os
import random
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))
import traci  # noqa: E402
import traci.constants as tc  # noqa: E402
from pyproj import Transformer  # noqa: E402

DIR = Path(__file__).resolve().parent
DIR_SUMO = DIR.parent / "sumo"
PARKING = 2  # bit de stopState: detenido en estacionamiento


def proyeccion(ruta_net):
    texto = Path(ruta_net).read_text(encoding="utf-8")[:4000]
    m = re.search(r'<location netOffset="([^"]+)".*?projParameter="([^"]+)"', texto, re.S)
    dx, dy = (float(v) for v in m.group(1).split(","))
    tr = Transformer.from_crs(m.group(2), "EPSG:4326", always_xy=True)

    def a_geo(xs, ys):
        lon, lat = tr.transform([x - dx for x in xs], [y - dy for y in ys])
        return lat, lon
    return a_geo


def estado_mock(vid, stop_state):
    # MOCK: reemplazar por el estado del controlador de Freddy (máquina de estados de S2-2).
    if not vid.startswith("busca_"):
        return None  # sin búsqueda ni app: el contrato pide estado null
    return "ESTACIONADO" if stop_state & PARKING else "BUSCANDO"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--desde", type=float, default=1800.0)
    ap.add_argument("--duracion", type=float, default=900.0)
    ap.add_argument("--salida", default=str(DIR / "datos" / "snapshots.jsonl"))
    ap.add_argument("--semilla", type=int, default=1)
    args = ap.parse_args()
    a_geo = proyeccion(DIR_SUMO / "red" / "centro.net.xml")
    traci.start(["sumo", "-c", str(DIR_SUMO / "centro_base.sumocfg"), "--seed", str(args.semilla),
                 "--tripinfo-output", "/dev/null", "--stop-output", "/dev/null",
                 "--vehroute-output", "/dev/null", "--emission-output", "/dev/null",
                 "--statistic-output", "/dev/null", "--no-warnings"])
    while traci.simulation.getTime() < args.desde:
        traci.simulationStep()

    variables = [tc.VAR_POSITION, tc.VAR_STOPSTATE]
    for vid in traci.vehicle.getIDList():
        traci.vehicle.subscribe(vid, variables)
    pas = traci.parkingarea.getIDList()
    capacidad = {pa: int(traci.simulation.getParameter(pa, "parkingArea.capacity")) for pa in pas}

    # Comprobación: pyproj + netOffset == convertGeo (muestra de 20 vehículos)
    muestra = list(traci.vehicle.getIDList())[:20]
    xs, ys = zip(*(traci.vehicle.getPosition(v) for v in muestra))
    lat, lon = a_geo(xs, ys)
    for v, la, lo, x, y in zip(muestra, lat, lon, xs, ys):
        lo2, la2 = traci.simulation.convertGeo(x, y)
        assert abs(la - la2) < 1e-6 and abs(lo - lo2) < 1e-6, (v, la, la2, lo, lo2)

    rng = random.Random(args.semilla)
    espejo = None  # MOCK: un buscador al azar hace de vehículo seguido por un teléfono espejo
    t0_real = datetime(2026, 10, 20, 13, 0, tzinfo=timezone.utc)  # hora de pico de referencia
    Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
    fin = args.desde + args.duracion
    n = 0
    with open(args.salida, "w", encoding="utf-8") as f:
        while traci.simulation.getTime() < fin:
            traci.simulationStep()
            t = traci.simulation.getTime()
            for vid in traci.simulation.getDepartedIDList():
                traci.vehicle.subscribe(vid, variables)
            res = traci.vehicle.getAllSubscriptionResults()
            ids, xs, ys, estados = [], [], [], []
            for vid, r in res.items():
                parado = r[tc.VAR_STOPSTATE] & PARKING
                if vid.startswith("fondo_") and parado:
                    continue
                x, y = r[tc.VAR_POSITION]
                ids.append(vid)
                xs.append(x)
                ys.append(y)
                estados.append(estado_mock(vid, r[tc.VAR_STOPSTATE]))
            if espejo not in res or (espejo and res[espejo][tc.VAR_STOPSTATE] & PARKING):
                buscando = [v for v, e in zip(ids, estados) if e == "BUSCANDO"]
                espejo = rng.choice(buscando) if buscando else None
            lat, lon = a_geo(xs, ys) if ids else ([], [])
            vehiculos = [{"id": f"sim_{v}", "lat": round(la, 6), "lon": round(lo, 6), "estado": e,
                          "con_app": v == espejo}  # MOCK: solo el espejo lleva app
                         for v, la, lo, e in zip(ids, lat, lon, estados)]
            puestos = [{"puesto_id": pa, "capacidad": capacidad[pa],
                        "ocupados": min(capacidad[pa],
                                        int(traci.simulation.getParameter(pa, "parkingArea.occupancy")))}
                       for pa in pas]
            ts = (t0_real + timedelta(seconds=t)).strftime("%Y-%m-%dT%H:%M:%SZ")
            msg = {"tipo": "snapshot", "t_sim": t, "ts": ts, "vehiculos": vehiculos,
                   "peatones": [], "puestos": puestos,
                   "espejos": [f"sim_{espejo}"] if espejo else []}
            f.write(json.dumps(msg, separators=(",", ":"), ensure_ascii=False) + "\n")
            n += 1
            if n % 60 == 0:
                print(f"t={t:.0f} s · {len(vehiculos)} vehículos · {n} snapshots", flush=True)
    traci.close()
    print(f"{n} snapshots -> {args.salida}")


if __name__ == "__main__":
    main()
