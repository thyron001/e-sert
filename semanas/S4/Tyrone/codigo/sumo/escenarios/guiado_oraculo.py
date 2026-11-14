# MOCK: reemplazar por traci/guiado.py de Freddy en S3-1
"""Guiado provisional ("oráculo") para probar el flujo de los escenarios con app.

Hook `hook(controlador, t)` del Controlador TraCI de Freddy. Al insertarse un vehículo con
`param con_app == "1"`, elige el parkingArea con lugar más cercano a su destino (con la
ocupación REAL de SUMO más los autos que ya van guiados hacia cada puesto) y llama a
`traci.vehicle.rerouteParkingArea(veh, pa)`. Cada `--revisar-s` segundos revisa a los guiados
que aún no estacionan y, si su puesto se llenó, les asigna otro.

Es un oráculo: conoce la ocupación real y al instante. El guiado de Freddy usará el mapa
estimado por el backend, así que este mock da una cota optimista del beneficio de la app.
"""
import csv
import math
import os
from pathlib import Path

DIR_SUMO = Path(__file__).resolve().parent.parent
PARKING = 2  # bit de stopState: detenido en estacionamiento


class GuiadoOraculo:
    def __init__(self, refrescar_s=5, revisar_s=30):
        self.refrescar_s = refrescar_s
        self.revisar_s = revisar_s
        with open(DIR_SUMO / "parqueos" / "puestos.csv", encoding="utf-8") as f:
            filas = list(csv.DictReader(f))
        self.puestos = {p["puesto_id"]: (float(p["x"]), float(p["y"]), int(p["capacidad"]))
                        for p in filas}
        self.edge = {p["puesto_id"]: p["edge"] for p in filas}
        self.ocupacion = {}
        self._t_ocupacion = -1.0
        self.guiados = {}  # veh -> (pa, destino_xy)
        self.en_camino = {}  # pa -> autos guiados que aún no estacionan
        self.asignaciones = 0
        self.reasignaciones = 0
        # Diagnóstico opcional: ESERT_LOG_ORACULO=<ruta> anota cada reroute antes de pedirlo
        ruta_log = os.environ.get("ESERT_LOG_ORACULO")
        self._log = open(ruta_log, "w", encoding="utf-8") if ruta_log else None

    def _refrescar(self, sim, t):
        if t - self._t_ocupacion >= self.refrescar_s:
            self.ocupacion = {pa: int(sim.getParameter(pa, "parkingArea.occupancy"))
                              for pa in self.puestos}
            self._t_ocupacion = t

    def _elegir(self, destino, evitar_edge=None):
        dx, dy = destino
        mejor, mejor_d = None, math.inf
        for pa, (x, y, cap) in self.puestos.items():
            if self.edge[pa] == evitar_edge:
                continue  # un puesto en el edge actual puede quedar detrás del vehículo
            if self.ocupacion.get(pa, 0) + self.en_camino.get(pa, 0) >= cap:
                continue
            d = math.hypot(x - dx, y - dy)
            if d < mejor_d:
                mejor, mejor_d = pa, d
        return mejor

    def _asignar(self, veh, tr, destino, anterior=None):
        # SUMO 1.12 aborta (asserts en MSVehicle::enterLaneAtMove y MSBaseVehicle::replaceRoute)
        # si se reasigna en un cruce, hacia un puesto del edge actual (puede quedar detrás) o
        # cuando la nueva ruta no contiene el edge del puesto. Por eso solo se reasigna desde un
        # edge normal, que no sea el del puesto actual, nunca a un puesto del edge actual, y con
        # ruta hasta el nuevo puesto.
        via = tr.vehicle.getRoadID(veh)
        pa = self._elegir(destino, evitar_edge=via)
        if pa is None or pa == anterior:
            return
        if anterior:
            if via.startswith(":") or via == self.edge[anterior]:
                return
            if not tr.simulation.findRoute(via, self.edge[pa]).edges:
                return
        if self._log:
            self._log.write(f"{tr.simulation.getTime():.0f} {veh} via={tr.vehicle.getRoadID(veh)} "
                            f"{anterior}->{pa}\n")
            self._log.flush()
        try:
            tr.vehicle.rerouteParkingArea(veh, pa)
        except tr.exceptions.TraCIException:
            return  # p. ej. el vehículo ya está en su último edge: sigue con el rerouter
        if anterior:
            self.en_camino[anterior] -= 1
            self.reasignaciones += 1
        else:
            self.asignaciones += 1
        self.en_camino[pa] = self.en_camino.get(pa, 0) + 1
        self.guiados[veh] = (pa, destino)

    def __call__(self, ctrl, t):
        tr = ctrl.traci
        nuevos = [v for v in tr.simulation.getDepartedIDList() if v.startswith("busca_")]
        con_app = [v for v in nuevos if tr.vehicle.getParameter(v, "con_app") == "1"]
        if con_app:
            self._refrescar(tr.simulation, t)
            for veh in con_app:
                lat, lon = (float(c) for c in tr.vehicle.getParameter(veh, "destino").split(","))
                destino = tr.simulation.convertGeo(lon, lat, fromGeo=True)
                self._asignar(veh, tr, destino)
        # Los que estacionaron o salieron dejan de contar como "en camino"
        llegados = set(tr.simulation.getArrivedIDList())
        for veh in list(self.guiados):
            datos = ctrl.vehiculos.get(veh) or {}
            if veh in llegados or int(datos.get(tr.constants.VAR_STOPSTATE, 0)) & PARKING:
                pa, _ = self.guiados.pop(veh)
                self.en_camino[pa] -= 1
        if int(t) % self.revisar_s == 0 and self.guiados:
            self._refrescar(tr.simulation, t)
            for veh, (pa, destino) in list(self.guiados.items()):
                if self.ocupacion.get(pa, 0) >= self.puestos[pa][2]:
                    self._asignar(veh, tr, destino, anterior=pa)
