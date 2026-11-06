"""Guiado de autos con app al puesto libre más cercano a su destino (S2-3).

`Guia` es un hook `on_paso` del `Controlador`:

- al salir un auto con `con_app=1`, lo guía con `traci.vehicle.rerouteParkingArea` al puesto
  libre más cercano a su destino (`param destino` de la demanda) → estado `GUIADO`;
- cada `periodo_revision_s` revisa si el puesto asignado se llenó antes de llegar y reasigna;
  como máximo `max_reasignaciones` veces. Después, el auto queda en búsqueda a ciegas, con los
  *rerouters* de Tyrone;
- `fuente_ocupacion="mapa"`: lo que sabe el sistema (sesiones abiertas de la app, `MapaOcupacion`).
  `"verdad"`: la ocupación real de SUMO (`parkingarea.getVehicleCount`). Solo sirve de oráculo.

`RegistroBusqueda` mide el tiempo de búsqueda (salida → estacionamiento) de **todos** los autos
de búsqueda, con y sin app, para comparar en la misma corrida.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Tuple

from .controlador import parametro
from .peatones import leer_destinos, texto_traci
from .puente_nucleo import distancia_m

FUENTES = ("mapa", "verdad")
Puesto = Tuple[float, float, int]  # (lat, lon, capacidad)


def destino_de(ctrl, veh: str, destinos: Dict[str, Tuple[float, float, float]]) -> Optional[Tuple[str, float, float]]:
    """`(nombre, lat, lon)` del destino de `veh`, o None.

    S3-3: los escenarios unificados de Tyrone (S2) traen `param destino_nombre` (el nombre de
    `destinos.csv`) y `param destino` con las coordenadas `"lat,lon"`; la demanda de S1 traía el
    nombre en `destino`. Se aceptan los tres casos.
    """
    nombre = texto_traci(parametro(ctrl, veh, "destino_nombre") or "")
    crudo = texto_traci(parametro(ctrl, veh, "destino") or "")
    if not nombre and crudo in destinos:
        nombre = crudo
    if nombre in destinos:
        lat, lon = destinos[nombre][:2]
        return nombre, lat, lon
    try:
        lat, lon = (float(x) for x in crudo.split(","))
    except ValueError:
        return None
    return (nombre or crudo), lat, lon


def recomendar(destino: Tuple[float, float], puestos: Dict[str, Puesto],
               libres: Callable[[str], int], excluir: Iterable[str] = ()) -> Optional[str]:
    """Puesto con plazas libres más cercano al destino (haversine). None si todos están llenos."""
    excluidos = set(excluir)
    mejor: Optional[Tuple[float, str]] = None
    for pid, (lat, lon, _) in puestos.items():
        if pid in excluidos or libres(pid) <= 0:
            continue
        d = distancia_m(destino[0], destino[1], lat, lon)
        if mejor is None or (d, pid) < mejor:
            mejor = (d, pid)
    return None if mejor is None else mejor[1]


class Guia:
    """Hook de `Controlador`: guía a los autos con app y revisa que el puesto siga libre."""

    def __init__(self, puente, destinos_csv: Path, fuente_ocupacion: str = "mapa",
                 max_reasignaciones: int = 3, periodo_revision_s: float = 10.0):
        if fuente_ocupacion not in FUENTES:
            raise ValueError(f"fuente_ocupacion debe ser {FUENTES}")
        self.puente = puente
        self.fuente = fuente_ocupacion
        self.max_reasignaciones = max_reasignaciones
        self.periodo_s = periodo_revision_s
        self.destinos = leer_destinos(destinos_csv)
        self.puestos: Dict[str, Puesto] = {
            pid: (p.lat, p.lon, p.capacidad) for pid, p in puente.mapa.puestos.items()
        }
        self.estado: Dict[str, str] = {}
        self.puesto: Dict[str, str] = {}
        self.reasignaciones: Counter = Counter()
        self._ultima_revision: Dict[str, float] = {}
        self.contadores: Counter = Counter()

    # ------------------------------------------------------------------ hook

    def on_paso(self, ctrl, t: float) -> None:
        tr = ctrl.traci
        for veh in tr.simulation.getDepartedIDList():
            if parametro(ctrl, veh, "clase") != "busca" or parametro(ctrl, veh, "con_app") != "1":
                continue
            self.puente.registrar(f"sim_{veh}")
            self.estado[veh] = "BUSCANDO"
            self._guiar(ctrl, veh, t, excluir=())
        for veh in tr.simulation.getParkingStartingVehiclesIDList():
            if veh in self.estado:
                self.estado[veh] = "ESTACIONADO"
        for veh, est in list(self.estado.items()):
            if est == "GUIADO" and t - self._ultima_revision[veh] >= self.periodo_s:
                self._revisar(ctrl, veh, t)

    # ------------------------------------------------------------------ decisiones

    def _libres(self, ctrl, pid: str) -> int:
        if self.fuente == "mapa":
            return self.puente.mapa.libres(pid)
        ocupados = ctrl.traci.parkingarea.getVehicleCount(pid)
        return self.puestos[pid][2] - ocupados

    def _guiar(self, ctrl, veh: str, t: float, excluir: Iterable[str]) -> None:
        destino = destino_de(ctrl, veh, self.destinos)
        if destino is None:
            self.contadores["sin_destino"] += 1
            self.estado[veh] = "A_CIEGAS"
            return
        _, lat, lon = destino
        excluidos = list(excluir)
        while True:
            pid = recomendar((lat, lon), self.puestos, lambda p: self._libres(ctrl, p), excluidos)
            if pid is None:
                self.contadores["sin_puesto_libre"] += 1
                self.estado[veh] = "A_CIEGAS"
                return
            if self._alcanzable(ctrl, veh, pid):
                break
            self.contadores["inalcanzables"] += 1
            excluidos.append(pid)
        ctrl.traci.vehicle.rerouteParkingArea(veh, pid)
        self.puesto[veh] = pid
        self.estado[veh] = "GUIADO"
        self._ultima_revision[veh] = t
        self.contadores["guiados"] += 1

    @staticmethod
    def _alcanzable(ctrl, veh: str, pid: str) -> bool:
        """Hay ruta desde la arista actual del auto hasta la del puesto. Si no, SUMO aborta (aserción)."""
        tr = ctrl.traci
        origen = tr.vehicle.getRoadID(veh)
        destino = tr.lane.getEdgeID(tr.parkingarea.getLaneID(pid))
        if origen.startswith(":"):
            return False
        return bool(tr.simulation.findRoute(origen, destino).edges)

    def _revisar(self, ctrl, veh: str, t: float) -> None:
        self._ultima_revision[veh] = t
        pid = self.puesto[veh]
        if self._libres(ctrl, pid) > 0:
            return
        if self.reasignaciones[veh] >= self.max_reasignaciones:
            self.estado[veh] = "A_CIEGAS"
            self.contadores["a_ciegas_por_agotar_reasignaciones"] += 1
            return
        self.reasignaciones[veh] += 1
        self.contadores["reasignaciones"] += 1
        self._guiar(ctrl, veh, t, excluir=(pid,))

    def resumen(self) -> dict:
        return {"fuente": self.fuente, "max_reasignaciones": self.max_reasignaciones,
                "periodo_revision_s": self.periodo_s, **dict(self.contadores)}


class RegistroBusqueda:
    """Tiempo de búsqueda (salida → estacionamiento) de todos los autos de búsqueda."""

    def __init__(self):
        self.salida: Dict[str, float] = {}
        self.con_app: Dict[str, bool] = {}
        self.llegada: Dict[str, float] = {}
        self.puesto: Dict[str, str] = {}

    def on_paso(self, ctrl, t: float) -> None:
        tr = ctrl.traci
        for veh in tr.simulation.getDepartedIDList():
            if parametro(ctrl, veh, "clase") == "busca":
                self.salida[veh] = t
                self.con_app[veh] = parametro(ctrl, veh, "con_app") == "1"
        for veh in tr.simulation.getParkingStartingVehiclesIDList():
            if veh in self.salida and veh not in self.llegada:
                self.llegada[veh] = t
                self.puesto[veh] = tr.vehicle.getStops(veh)[0].stoppingPlaceID

    def guardar(self, ruta: Path, guia: Optional[Guia] = None) -> None:
        with ruta.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["veh_id", "con_app", "t_salida", "t_estacionado", "tiempo_busqueda_s",
                        "puesto_id", "reasignaciones", "estado_guia"])
            for veh, t_sal in self.salida.items():
                t_lle = self.llegada.get(veh)
                w.writerow([
                    veh, int(self.con_app[veh]), t_sal,
                    "" if t_lle is None else t_lle,
                    "" if t_lle is None else round(t_lle - t_sal, 1),
                    self.puesto.get(veh, ""),
                    guia.reasignaciones[veh] if guia else 0,
                    guia.estado.get(veh, "") if guia else "",
                ])
