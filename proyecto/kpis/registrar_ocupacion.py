"""Registro de la ocupación real de cada parkingArea (la "verdad" del KPI de precisión del mapa).

Como hook del Controlador TraCI de Freddy (proyecto/traci/controlador.py):
    reg = RegistradorOcupacion("app50_s1", periodo_s=60)
    ctrl.agregar_hook(reg)          # hook(controlador, t) tras cada paso
    ...
    reg.cerrar()

Cada `periodo_s` lee, para cada parkingArea, `traci.simulation.getParameter(pa,
"parkingArea.occupancy")` y `"parkingArea.capacity"`, y escribe
kpis/salidas/ocupacion_real_<escenario>.csv con las columnas t_sim,puesto_id,ocupados,capacidad.

Comprobación contra el stop-output (en la computadora, necesita pandas):
    python -m kpis.registrar_ocupacion --comprobar kpis/salidas/ocupacion_real_app50_s1.csv \
        --stops sumo/salidas/app50_s1/stops.xml
compara la ocupación total en cada instante con la reconstruida con los intervalos del
stop-output. Debe coincidir en ±1 puesto. El hook lee la ocupación al final del paso t, así
que una parada cuenta desde el paso siguiente a `started` y todavía en el paso de `ended`: la
convención que corresponde es (started, ended]. Con [started, ended) (la de kpis.serie_ocupacion,
pensada para promedios por minuto) aparecen diferencias de 1-2 puestos y, en el warm-up, de
decenas, cuando cientos de autos de fondo estacionan en el mismo segundo.
"""
import argparse
import csv
from pathlib import Path

DIR = Path(__file__).resolve().parent
SALIDAS = DIR / "salidas"
COLUMNAS = ["t_sim", "puesto_id", "ocupados", "capacidad"]


class RegistradorOcupacion:
    """Hook `hook(controlador, t)`: escribe la ocupación de todos los puestos cada periodo."""

    def __init__(self, escenario, periodo_s=60, destino=SALIDAS):
        self.periodo_s = int(periodo_s)
        self.ruta = Path(destino) / f"ocupacion_real_{escenario}.csv"
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self._archivo = open(self.ruta, "w", newline="", encoding="utf-8")
        self._csv = csv.writer(self._archivo, lineterminator="\n")
        self._csv.writerow(COLUMNAS)
        self._puestos = None
        self._capacidad = {}
        self.registros = 0

    def __call__(self, ctrl, t):
        if int(round(t)) % self.periodo_s:
            return
        sim = ctrl.traci.simulation
        if self._puestos is None:
            self._puestos = list(ctrl.traci.parkingarea.getIDList())
            self._capacidad = {pa: int(sim.getParameter(pa, "parkingArea.capacity"))
                               for pa in self._puestos}
        for pa in self._puestos:
            self._csv.writerow([int(round(t)), pa, int(sim.getParameter(pa, "parkingArea.occupancy")),
                                self._capacidad[pa]])
        self.registros += 1

    def cerrar(self):
        if not self._archivo.closed:
            self._archivo.close()


def comprobar(ruta_csv, ruta_stops, tolerancia=1):
    """Diferencia máxima (puestos) entre el CSV y el stop-output en cada instante registrado."""
    import numpy as np
    import pandas as pd
    from kpis import lectores

    real = pd.read_csv(ruta_csv)
    total = real.groupby("t_sim")["ocupados"].sum()
    stops = lectores.leer_stops(ruta_stops)
    inicio = stops["started"].to_numpy(dtype=float)
    fin = stops["ended"].to_numpy(dtype=float)
    fin = np.where(fin < 0, np.inf, fin)  # parada sin terminar
    reconstruida = np.array([int(((inicio < t) & (t <= fin)).sum()) for t in total.index])
    dif = np.abs(total.to_numpy() - reconstruida)
    return {"instantes": int(len(dif)), "dif_max": int(dif.max()), "dif_media": round(float(dif.mean()), 3),
            "cumple": bool(dif.max() <= tolerancia)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--comprobar", required=True, help="ocupacion_real_<escenario>.csv")
    ap.add_argument("--stops", required=True, help="stops.xml de la misma corrida")
    args = ap.parse_args()
    print(comprobar(args.comprobar, args.stops))


if __name__ == "__main__":
    main()
