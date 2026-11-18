"""Distancia de manejo al puesto que elige la app: línea recta (antes) frente a ruta (ahora).

300 puntos al azar junto a los puestos del Centro, con ~85 % de las áreas llenas (semilla 1).
Escribe `informe_ieee/datos/rutas.csv` (una fila por punto). Uso, en el contenedor van3twin:
    python3 informe_ieee/comparar_rutas.py
"""
import random, statistics, sys, types, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from traci.sumo import cargar_libsumo
ls = cargar_libsumo()

from traci import autos_web as aw
from traci.puente_nucleo import distancia_m
ls.start(["sumo", "-c", "sumo/centro_parqueos.sumocfg", "--no-warnings", "--no-step-log"])
ls.simulationStep()
rng = random.Random(1)
puestos = {}
for pid in ls.parkingarea.getIDList():
    lane = ls.parkingarea.getLaneID(pid); s = (ls.parkingarea.getStartPos(pid) + ls.parkingarea.getEndPos(pid)) / 2
    x, y = ls.simulation.convert2D(ls.lane.getEdgeID(lane), s, 0)
    lon, lat = ls.simulation.convertGeo(x, y)
    puestos[pid] = (lat, lon, 1 if rng.random() < 0.15 else 0)   # ~85 % llenos
guia = types.SimpleNamespace(puestos=puestos)
ctrl = types.SimpleNamespace(traci=ls)
w = aw.AutosWeb.__new__(aw.AutosWeb); w.guia = guia; w.reservas = {}
def viejo(punto, arista, pos):
    for pid, _ in sorted(puestos.items(), key=lambda kv: distancia_m(punto[0], punto[1], kv[1][0], kv[1][1])):
        if w._libres(ctrl, pid) <= 0: continue
        d = ls.lane.getEdgeID(ls.parkingarea.getLaneID(pid))
        if d == arista:
            if ls.parkingarea.getStartPos(pid) <= pos + 15: continue
            return pid
        if ls.simulation.findRoute(arista, d).edges: return pid
def largo(arista, pos, pid):
    d = ls.lane.getEdgeID(ls.parkingarea.getLaneID(pid)); ini = ls.parkingarea.getStartPos(pid)
    if d == arista: return ini - pos
    e = ls.simulation.findRoute(arista, d)
    return e.length - pos - (ls.lane.getLength(ls.parkingarea.getLaneID(pid)) - ini)
xs = [puestos[p][:2] for p in puestos]
A, B = [], []
for i in range(300):
    lat, lon = rng.choice(xs); lat += rng.uniform(-4e-4, 4e-4); lon += rng.uniform(-4e-4, 4e-4)
    arista, pos, carril = ls.simulation.convertRoad(lon, lat, True, "passenger")
    L = ls.lane.getLength(f"{arista}_{carril}"); pos = min(max(pos, 1), L - 1)
    p0 = viejo((lat, lon), arista, pos)
    p1, r1, c1 = w._elegir(ctrl, (lat, lon), arista, pos, con_costo=True)
    contraria = arista[1:] if arista.startswith("-") else f"-{arista}"
    if contraria in w._aristas(ls):
        pc = min(max(ls.lane.getLength(f"{contraria}_0") - pos, 1), ls.lane.getLength(f"{contraria}_0") - 1)
        q = w._elegir(ctrl, (lat, lon), contraria, pc, con_costo=True)
        if q[0] and q[2] < c1: c1 = q[2]
    if p0 and p1:
        A.append(largo(arista, pos, p0)); B.append(c1)
q = lambda v, k: sorted(v)[int(k * (len(v) - 1))]
print(f"n={len(A)}")
print(f"antes (línea recta): media {statistics.mean(A):.0f} m, mediana {q(A,.5):.0f}, p90 {q(A,.9):.0f}, máx {max(A):.0f}")
print(f"ahora (ruta):        media {statistics.mean(B):.0f} m, mediana {q(B,.5):.0f}, p90 {q(B,.9):.0f}, máx {max(B):.0f}")
print(f"casos con > 500 m: antes {sum(a>500 for a in A)}, ahora {sum(b>500 for b in B)}")
salida = pathlib.Path(__file__).resolve().parent / "datos" / "rutas.csv"
salida.write_text("linea_recta_m,ruta_m\n" + "".join(f"{a:.1f},{b:.1f}\n" for a, b in zip(A, B)))
ls.close()
