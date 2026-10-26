"""Máquina de estados de la sesión de parqueo (contrato §3) y su control como hook del Controlador.

- `MaquinaSesion` es pura (sin TraCI): recibe cada ventana de 5 s el modo clasificado y la
  distancia al puesto, y devuelve las transiciones. Así se prueba sin SUMO.
- `ControlSesiones` es el hook de TraCI: abre una sesión por cada auto de búsqueda que
  estaciona, lleva el teléfono `sim_<veh>` con el `EmuladorGPS` (la posición del auto si está
  dentro, la del peatón si camina), clasifica con `clasificacion.py`, registra los CSV y cuenta
  las **falsas liberaciones**: cerrar la sesión mientras el auto sigue estacionado.
"""

from __future__ import annotations

import csv
from collections import Counter, namedtuple
from pathlib import Path
from typing import Dict, List, Optional

from .clasificacion import ClasificadorUsuario, haversine_m
from .gps import EmuladorGPS, modo_real_persona, modo_real_vehiculo

ESTADOS = ("BUSCANDO", "GUIADO", "ESTACIONADO", "A_PIE", "REGRESANDO", "SALIENDO", "CERRADA")
Transicion = namedtuple("Transicion", "t_sim usuario_id desde hacia modo distancia_m")
EN_AUTO = "en_auto"  # descripción de la etapa de espera del peatón que se queda dentro del auto


class MaquinaSesion:
    """Estados de una sesión (un usuario `sim_<veh>`), con los umbrales del contrato como parámetros.

    La sesión existe desde `ESTACIONADO` (contrato §3). `SALIENDO` se cierra en el mismo paso
    (`SALIENDO → CERRADA`, motivo `deteccion`): el controlador es quien cierra.
    """

    def __init__(self, usuario_id: str, dist_a_pie_m: float = 15, dist_regreso_m: float = 30,
                 dist_salida_m: float = 20, ventanas_vehiculo: int = 2):
        self.usuario_id = usuario_id
        self.dist_a_pie_m = dist_a_pie_m
        self.dist_regreso_m = dist_regreso_m
        self.dist_salida_m = dist_salida_m
        self.ventanas_vehiculo = ventanas_vehiculo
        self.estado = "ESTACIONADO"
        self._vehiculo_seguido = 0

    def actualizar(self, modo: str, distancia_m: float, t_sim: float) -> List[Transicion]:
        """Procesa una ventana. Devuelve las transiciones ocurridas (0, 1 o 2)."""
        if self.estado == "CERRADA":
            return []
        if modo == "vehiculo" and distancia_m > self.dist_salida_m:
            self._vehiculo_seguido += 1
        else:
            self._vehiculo_seguido = 0

        desde = self.estado
        nuevo = self._siguiente(modo, distancia_m)
        if nuevo is None:
            return []
        transiciones = [Transicion(t_sim, self.usuario_id, desde, nuevo, modo, round(distancia_m, 1))]
        self.estado = nuevo
        if nuevo == "SALIENDO":
            transiciones.append(Transicion(t_sim, self.usuario_id, "SALIENDO", "CERRADA", modo,
                                           round(distancia_m, 1)))
            self.estado = "CERRADA"
        return transiciones

    def _siguiente(self, modo: str, distancia_m: float) -> Optional[str]:
        """Regla de transición del contrato §3 (la primera que aplique)."""
        if self.estado in ("ESTACIONADO", "REGRESANDO") and self._vehiculo_seguido >= self.ventanas_vehiculo:
            return "SALIENDO"
        if self.estado == "ESTACIONADO" and modo == "a_pie" and distancia_m > self.dist_a_pie_m:
            return "A_PIE"
        if self.estado == "A_PIE" and modo in ("a_pie", "quieto") and distancia_m < self.dist_regreso_m:
            return "REGRESANDO"
        if self.estado == "REGRESANDO" and modo == "a_pie" and distancia_m > self.dist_regreso_m:
            return "A_PIE"  # se volvió a alejar
        return None


class ControlSesiones:
    """Hook `on_paso` de `Controlador`: sesiones de parqueo con GPS emulado y clasificación."""

    def __init__(self, gps: EmuladorGPS, salidas: Path, escenario: str,
                 clasificador: Optional[ClasificadorUsuario] = None):
        self.gps = gps
        self.clasificador = clasificador or ClasificadorUsuario()
        self.maquinas: Dict[str, MaquinaSesion] = {}
        # Puesto = punto donde el auto se estacionó (lat, lon); un parkingArea mide ~100 m y su
        # centro quedaría a más de 30 m de cualquier auto.
        self.puesto_ll: Dict[str, tuple] = {}
        self.puesto_de: Dict[str, str] = {}
        self._ultima_fila: Dict[str, dict] = {}
        self.llegadas = 0
        self.cerradas = 0
        self.falsas_liberaciones = 0
        self.fuentes: Counter = Counter()

        salidas.mkdir(parents=True, exist_ok=True)
        self._archivos = {
            "transiciones": (salidas / f"transiciones_{escenario}.csv").open("w", newline="", encoding="utf-8"),
            "ventanas": (salidas / f"ventanas_{escenario}.csv").open("w", newline="", encoding="utf-8"),
            "falsas": (salidas / f"falsas_liberaciones_{escenario}.csv").open("w", newline="", encoding="utf-8"),
        }
        cabeceras = {
            "transiciones": ["t_sim", "usuario_id", "desde", "hacia", "modo", "distancia_m"],
            "ventanas": ["t_sim", "usuario_id", "estado", "modo_clasificado", "confianza", "fuente",
                         "distancia_m", "modo_real"],
            "falsas": ["t_sim", "usuario_id", "puesto_id", "distancia_m"],
        }
        self._escritores = {}
        for clave, archivo in self._archivos.items():
            self._escritores[clave] = csv.writer(archivo)
            self._escritores[clave].writerow(cabeceras[clave])

    # ------------------------------------------------------------------ hook

    def on_paso(self, ctrl, t: float) -> None:
        """Llamado tras cada paso del `Controlador`."""
        tr = ctrl.traci
        for veh in tr.simulation.getParkingStartingVehiclesIDList():
            if tr.vehicle.getParameter(veh, "clase") == "busca" and veh not in self.maquinas:
                self.maquinas[veh] = MaquinaSesion(f"sim_{veh}")
                self.puesto_de[veh] = tr.vehicle.getStops(veh)[0].stoppingPlaceID
                x, y = tr.vehicle.getPosition(veh)
                self.puesto_ll[veh] = ctrl.a_geo(x, y)
                self.llegadas += 1

        for veh in list(self.maquinas):
            usuario = f"sim_{veh}"
            if veh not in ctrl.vehiculos:
                del self.maquinas[veh]
                del self.puesto_ll[veh]
                continue
            self._muestrear(ctrl, veh, t)
            resultado = self.clasificador.evaluar(usuario, t)
            if resultado is None or usuario not in self._ultima_fila:
                continue
            self._procesar_ventana(ctrl, veh, t, resultado)

    def _muestrear(self, ctrl, veh: str, t: float) -> None:
        """Una muestra del teléfono: el peatón si camina, el auto si está dentro."""
        usuario = f"sim_{veh}"
        if not self.gps.toca_muestra(usuario, t):
            return
        datos = ctrl.vehiculos[veh]
        ped = f"ped_{veh}"
        tc = ctrl.traci.constants
        if ped in ctrl.personas and ctrl.traci.person.getStage(ped).description != EN_AUTO:
            x, y = ctrl.personas[ped][tc.VAR_POSITION]
            modo = modo_real_persona(ctrl.traci.person.getStage(ped).type)
        else:
            x, y = datos[tc.VAR_POSITION]
            modo = modo_real_vehiculo(ctrl.estacionado(datos))
        fila = self.gps.observar(usuario, t, x, y, modo, ctrl.a_geo)
        if fila is not None:
            self._ultima_fila[usuario] = fila
            self.clasificador.observar(usuario, fila)

    def _procesar_ventana(self, ctrl, veh: str, t: float, resultado: dict) -> None:
        usuario = f"sim_{veh}"
        maquina = self.maquinas[veh]
        fila = self._ultima_fila[usuario]
        puesto = self.puesto_ll[veh]
        distancia = haversine_m(fila["lat"], fila["lon"], puesto[0], puesto[1])
        self.fuentes[resultado["fuente"]] += 1
        self._escritores["ventanas"].writerow([
            round(t, 1), usuario, maquina.estado, resultado["modo"], round(resultado["confianza"], 3),
            resultado["fuente"], round(distancia, 1), fila["modo_real"],
        ])
        for trans in maquina.actualizar(resultado["modo"], distancia, t):
            self._escritores["transiciones"].writerow(list(trans))
            if trans.hacia == "CERRADA":
                self._cerrar(ctrl, veh, trans, distancia)
        if maquina.estado == "CERRADA":
            del self.maquinas[veh]
            del self.puesto_ll[veh]

    def _cerrar(self, ctrl, veh: str, trans: Transicion, distancia: float) -> None:
        """Al cerrar, comprueba en SUMO si el auto sigue estacionado: eso es una falsa liberación."""
        self.cerradas += 1
        if ctrl.traci.vehicle.isStoppedParking(veh):
            self.falsas_liberaciones += 1
            self._escritores["falsas"].writerow([trans.t_sim, trans.usuario_id, self.puesto_de[veh],
                                                 round(distancia, 1)])

    # ------------------------------------------------------------------ cierre y resumen

    def cerrar(self) -> None:
        """Cierra los CSV (idempotente)."""
        for archivo in self._archivos.values():
            if not archivo.closed:
                archivo.close()

    def resumen(self) -> dict:
        """Cifras de la corrida: sesiones, falsas liberaciones y el clasificador usado."""
        por_100 = round(100 * self.falsas_liberaciones / self.llegadas, 2) if self.llegadas else None
        return {
            "sesiones": self.llegadas,
            "cerradas": self.cerradas,
            "abiertas_al_final": len(self.maquinas),
            "falsas_liberaciones": self.falsas_liberaciones,
            "falsas_por_100_sesiones": por_100,
            "clasificador": self.clasificador.origen,
            "ventanas_por_fuente": dict(self.fuentes),
        }
