"""Autos de la app web (2026-11-18): el backend ordena y este hook los crea y guía en SUMO.

Cada persona que usa la app web (`/app/`) tiene un auto propio en la simulación, `web_<id>`
(`sim_web_<id>` en el contrato). Las órdenes llegan en la respuesta de `/sim/paso`
(`RespuestaSnapshot.ordenes`) por el hilo del publicador y se aplican en el hilo de la simulación:

- `buscar`: el auto nace en la calle más cercana a `lat, lon` y va por la ruta real de SUMO al
  **puesto con plazas libres más cercano**, según la ocupación real de SUMO menos las plazas
  reservadas por otros autos web que todavía van en camino. Si el puesto se llena antes de llegar,
  se reasigna al siguiente;
- `estacionado`: el auto nace ya estacionado en el puesto que el usuario indicó con su código;
- `volver`: el conductor deja la diligencia y vuelve al auto (`GestorPeatones.volver`).

Los autos web son autos de búsqueda con app (`clase=busca`, `con_app=1`, `web=1`): pasan por el
mismo GPS emulado, el clasificador (RF), la máquina de estados y el peatón que los simulados. La
`Guia` no los guía (los guía este hook) y el espejo los publica con su puesto y su ruta.

Lo que pasa con cada orden vuelve al backend en `PasoSimulacion.web` (`EventoWeb`).
"""

from __future__ import annotations

import threading
from collections import deque
from typing import Deque, Dict, List, Optional

from .puente_nucleo import distancia_m

PARADA_LARGA_S = 86400          # el auto no se va solo: vuelve cuando el conductor regresa
PERIODO_REVISION_S = 5.0
MARGEN_FRENADO_M = 15.0
CANDIDATOS = 25                  # puestos libres que se comparan por ruta al elegir
DISTANCIA_SALIDA_M = 600.0       # al irse, el auto maneja al menos esto (la IA lo ve salir)
TIPO_VEHICULO = "auto"


class AutosWeb:
    """Hook `on_paso` del `Controlador` para los autos de la app web."""

    def __init__(self, guia, peatones, max_autos: int = 30):
        self.guia = guia
        self.peatones = peatones
        self.max_autos = max_autos
        self._ordenes: Deque[dict] = deque()
        self._eventos: List[dict] = []
        self._cerrojo = threading.Lock()
        self.reservas: Dict[str, str] = {}      # veh SUMO → puesto (autos web aún en camino)
        self.autos: Dict[str, str] = {}         # veh SUMO → modo ('buscar' | 'estacionado')
        self._ultima_revision = 0.0

    # ------------------------------------------------------------------ hilo del publicador

    def recibir(self, ordenes) -> None:
        """Encola las órdenes de la respuesta del backend (se llama desde otro hilo)."""
        if not ordenes:
            return
        with self._cerrojo:
            self._ordenes.extend(ordenes)

    def eventos(self) -> List[dict]:
        """Eventos pendientes para el próximo `/sim/paso` (y los vacía)."""
        with self._cerrojo:
            salida, self._eventos = self._eventos, []
        return salida

    def _evento(self, tipo: str, veh: str, puesto: Optional[str] = None, detalle: Optional[str] = None) -> None:
        with self._cerrojo:
            self._eventos.append({"tipo": tipo, "veh_id": f"sim_{veh}", "puesto_id": puesto, "detalle": detalle})

    # ------------------------------------------------------------------ hook

    def on_paso(self, ctrl, t: float) -> None:
        with self._cerrojo:
            pendientes = list(self._ordenes)
            self._ordenes.clear()
        for orden in pendientes:
            veh = str(orden.get("veh_id", ""))[len("sim_"):]
            if not veh.startswith("web_"):
                continue
            try:
                if orden.get("tipo") == "buscar":
                    self._buscar(ctrl, veh, float(orden["lat"]), float(orden["lon"]), t)
                elif orden.get("tipo") == "estacionado":
                    self._estacionado(ctrl, veh, str(orden["puesto_id"]), t)
                elif orden.get("tipo") == "volver":
                    self._salida(ctrl, veh)
                    self.peatones.volver(ctrl, veh)
            except ctrl.traci.exceptions.TraCIException as exc:
                self._evento("error", veh, detalle=str(exc)[:200])
        tr = ctrl.traci
        for veh in tr.simulation.getParkingStartingVehiclesIDList():
            if self.reservas.pop(veh, None) is not None:
                self.guia.estado[veh] = "ESTACIONADO"
        for veh in tr.simulation.getArrivedIDList():
            self.reservas.pop(veh, None)
            self.autos.pop(veh, None)
        if self.reservas and t - self._ultima_revision >= PERIODO_REVISION_S:
            self._ultima_revision = t
            self._revisar(ctrl, t)

    # ------------------------------------------------------------------ órdenes

    def _buscar(self, ctrl, veh: str, lat: float, lon: float, t: float) -> None:
        tr = ctrl.traci
        if veh in self.autos:
            return
        if len(self.autos) >= self.max_autos:
            self._evento("error", veh, detalle="demasiados autos web en la simulación")
            return
        arista, pos, carril = tr.simulation.convertRoad(lon, lat, isGeo=True, vClass="passenger")
        largo = tr.lane.getLength(f"{arista}_{carril}")
        pos = min(max(pos, 1.0), largo - 1.0)
        pid, ruta, costo = self._elegir(ctrl, (lat, lon), arista, pos, con_costo=True)
        # En una calle de doble sentido, el auto puede arrancar en el carril contrario si así llega antes.
        contraria = arista[1:] if arista.startswith("-") else f"-{arista}"
        if contraria in self._aristas(tr):
            pos_c = min(max(tr.lane.getLength(f"{contraria}_0") - pos, 1.0), tr.lane.getLength(f"{contraria}_0") - 1.0)
            pid_c, ruta_c, costo_c = self._elegir(ctrl, (lat, lon), contraria, pos_c, con_costo=True)
            if pid_c is not None and costo_c < costo:
                pid, ruta, pos = pid_c, ruta_c, pos_c
        if pid is None:
            self._evento("sin_puesto", veh, detalle="no hay puestos libres alcanzables")
            return
        tr.route.add(f"r_{veh}", ruta)
        tr.vehicle.add(veh, f"r_{veh}", typeID=self._tipo(tr), departPos=str(pos), departLane="best",
                       departSpeed="0")
        self._marcar(ctrl, veh, f"{lat},{lon}")
        tr.vehicle.setParkingAreaStop(veh, pid, duration=PARADA_LARGA_S)
        self.autos[veh] = "buscar"
        self.reservas[veh] = pid
        self._asignar(ctrl, veh, pid, t)

    def _estacionado(self, ctrl, veh: str, pid: str, t: float) -> None:
        tr = ctrl.traci
        if veh in self.autos:
            return
        if pid not in self.guia.puestos:
            self._evento("error", veh, pid, "el puesto no existe")
            return
        if self._libres(ctrl, pid) <= 0:
            self._evento("puesto_lleno", veh, pid, "el puesto no tiene plazas libres")
            return
        arista = tr.lane.getEdgeID(tr.parkingarea.getLaneID(pid))
        tr.route.add(f"r_{veh}", [arista])
        tr.vehicle.add(veh, f"r_{veh}", typeID=self._tipo(tr), departPos=str(tr.parkingarea.getStartPos(pid)),
                       departLane="best", departSpeed="0")
        lat, lon, _ = self.guia.puestos[pid]
        self._marcar(ctrl, veh, f"{lat},{lon}")
        tr.vehicle.setParkingAreaStop(veh, pid, duration=PARADA_LARGA_S)
        self.autos[veh] = "estacionado"
        self.reservas[veh] = pid
        self._asignar(ctrl, veh, pid, t)

    # ------------------------------------------------------------------ elegir y revisar

    def _libres(self, ctrl, pid: str, sin: Optional[str] = None) -> int:
        """Plazas libres reales menos las reservadas por otros autos web en camino."""
        reservadas = sum(1 for v, p in self.reservas.items() if p == pid and v != sin)
        return self.guia.puestos[pid][2] - ctrl.traci.parkingarea.getVehicleCount(pid) - reservadas

    def _elegir(self, ctrl, punto, arista: str, pos: float, sin: Optional[str] = None, excluir=(),
                con_costo: bool = False):
        """(puesto, ruta) del puesto libre con la **ruta de manejo más corta**, o (None, None).

        Antes se tomaba el más cercano en línea recta, pero en el Centro Histórico (calles de un solo
        sentido) ese puesto puede quedar a varias cuadras de vuelta. Ahora se miran los
        `CANDIDATOS` libres más cercanos en línea recta y se elige el de menor distancia por ruta.
        """
        tr = ctrl.traci
        orden = sorted(self.guia.puestos.items(), key=lambda kv: distancia_m(punto[0], punto[1], kv[1][0], kv[1][1]))
        mejor = (None, None, float("inf"))
        vistos = 0
        for pid, (plat, plon, _) in orden:
            if vistos >= CANDIDATOS or (mejor[0] and distancia_m(punto[0], punto[1], plat, plon) > mejor[2]):
                break  # la línea recta ya supera la mejor ruta: ninguno más lejano puede ganar
            if pid in excluir or self._libres(ctrl, pid, sin) <= 0:
                continue
            destino = tr.lane.getEdgeID(tr.parkingarea.getLaneID(pid))
            inicio = tr.parkingarea.getStartPos(pid)
            if destino == arista and inicio > pos + MARGEN_FRENADO_M:
                costo, ruta = inicio - pos, [arista]
            else:
                if destino == arista:
                    continue  # está detrás del auto: habría que dar la vuelta a la manzana
                etapa = tr.simulation.findRoute(arista, destino)
                if not etapa.edges:
                    continue
                largo_destino = tr.lane.getLength(tr.parkingarea.getLaneID(pid))
                costo = etapa.length - pos - (largo_destino - inicio)
                ruta = list(etapa.edges)
            vistos += 1
            if costo < mejor[2]:
                mejor = (pid, ruta, costo)
        return mejor if con_costo else (mejor[0], mejor[1])

    def _revisar(self, ctrl, t: float) -> None:
        """Si el puesto de un auto en camino se llenó, lo reasigna al siguiente libre."""
        tr = ctrl.traci
        for veh, pid in list(self.reservas.items()):
            if self.autos.get(veh) != "buscar" or veh not in tr.vehicle.getIDList():
                continue
            if self._libres(ctrl, pid, sin=veh) > 0:
                continue
            arista = tr.vehicle.getRoadID(veh)
            if not arista or arista.startswith(":"):
                continue
            lat, lon = ctrl.a_geo(*tr.vehicle.getPosition(veh))
            nuevo, _ = self._elegir(ctrl, (lat, lon), arista, tr.vehicle.getLanePosition(veh), sin=veh, excluir=(pid,))
            if nuevo is None:
                continue
            tr.vehicle.rerouteParkingArea(veh, nuevo)
            self.reservas[veh] = nuevo
            self._asignar(ctrl, veh, nuevo, t)

    def _salida(self, ctrl, veh: str) -> None:
        """Al irse, el auto sigue hasta una calle a más de `DISTANCIA_SALIDA_M`.

        Su ruta terminaba en el puesto: al reanudar saldría de la red en un instante, sin dar tiempo
        a que la IA vea que va manejando (`SALIENDO` necesita dos ventanas en vehículo).
        """
        tr = ctrl.traci
        if veh not in tr.vehicle.getIDList():
            return
        actual = tr.vehicle.getRoadID(veh)
        if not actual or actual.startswith(":"):
            return
        x, y = tr.vehicle.getPosition(veh)
        lat, lon = ctrl.a_geo(x, y)
        lejos = sorted(self.guia.puestos.items(),
                       key=lambda kv: -distancia_m(lat, lon, kv[1][0], kv[1][1]))
        for pid, (plat, plon, _) in lejos[:40]:
            if distancia_m(lat, lon, plat, plon) < DISTANCIA_SALIDA_M:
                break
            destino = tr.lane.getEdgeID(tr.parkingarea.getLaneID(pid))
            if destino != actual and tr.simulation.findRoute(actual, destino).edges:
                tr.vehicle.changeTarget(veh, destino)
                return

    # ------------------------------------------------------------------ auxiliares

    def _aristas(self, tr) -> set:
        if not hasattr(self, "_cache_aristas"):
            self._cache_aristas = set(tr.edge.getIDList())
        return self._cache_aristas

    @staticmethod
    def _tipo(tr) -> str:
        return TIPO_VEHICULO if TIPO_VEHICULO in tr.vehicletype.getIDList() else "DEFAULT_VEHTYPE"

    @staticmethod
    def _marcar(ctrl, veh: str, destino: str) -> None:
        tr = ctrl.traci
        for clave, valor in (("clase", "busca"), ("con_app", "1"), ("web", "1"), ("destino", destino)):
            tr.vehicle.setParameter(veh, clave, valor)

    def _asignar(self, ctrl, veh: str, pid: str, t: float) -> None:
        """La guía y el espejo lo ven como un auto guiado a `pid`; el backend recibe el puesto."""
        self.guia.web.add(veh)
        self.guia.puente.registrar(f"sim_{veh}")
        self.guia.puesto[veh] = pid
        self.guia.estado[veh] = "GUIADO"
        self._evento("asignado", veh, pid)
