"""Peatones que hacen diligencias: cada auto de búsqueda que estaciona genera un peatón.

`GestorPeatones` es un hook `on_paso` del `Controlador`. Al detectar una llegada a un
parkingArea (`getParkingStartingVehiclesIDList`):

1. extiende la parada del auto a 86400 s, para que no se vaya solo;
2. crea el peatón `ped_<vehId>` en el puesto y le asigna su itinerario: caminar al destino del
   auto, esperar la diligencia y volver al auto;
3. cuando el peatón desaparece de la red (llegó de vuelta), reanuda el auto.

Casos difíciles (con su valor por defecto):
- `p_regreso_corto=0.15`: vuelve al auto a buscar algo, espera un momento y sale otra vez;
- `p_espera_en_auto=0.10`: no sale; se queda en el puesto (modo `quieto`, a 0 m) durante la
  estadía, dentro del auto.

Solo se generan peatones para los autos de la clase `busca` (`<param key="clase">`). Los
autos `fondo` ya están estacionados desde el inicio y no son llegadas de la sesión.
"""

from __future__ import annotations

import csv
import math
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .controlador import parametro

PARADA_EXTENDIDA_S = 86400
ESPERA_CORTA_S = 60
MIN_DILIGENCIA_S = 60
# App web: el conductor camina hacia la ubicación que puso al buscar (su destino está cerca).
DISTANCIA_MIN_WEB_M = 40      # más cerca que esto no se notaría que se bajó: se usa un lugar cercano
DISTANCIA_MAX_WEB_M = 200     # y nunca más lejos que esto de ese punto
MAX_CAMINATA_WEB_M = 250      # caminata máxima aceptada hasta el destino (salvo 3× la línea recta)
MAX_INTENTOS_DESTINO = 20
TIMEOUT_APARICION_S = 60  # si el peatón no aparece en la red en este tiempo, se libera el auto
INTERVALO_TRAYECTORIA_S = 10

Destino = Tuple[float, float, float]  # (lat, lon, peso)


def texto_traci(valor: str) -> str:
    """Texto de TraCI a Unicode: el cliente de Python decodifica como latin-1 y `ó` llega como `Ã³`."""
    try:
        return valor.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return valor


def _camino(tr, desde: str, hasta: str) -> Optional[Tuple[List[str], float]]:
    """(aristas, tiempo en s) a pie entre dos aristas, o None si no hay camino peatonal.

    Si las dos aristas son la misma, el camino es esa arista.
    """
    if desde == hasta:
        return [desde], 0.0
    ruta = tr.simulation.findRoute(desde, hasta, vType="DEFAULT_PEDTYPE")
    if not ruta.edges:
        return None
    return list(ruta.edges), ruta.travelTime


def _camino_web(tr, desde: str, hasta: str) -> Optional[Tuple[List[str], float]]:
    """Camino a pie del peatón de la app web: primero el router intermodal (camina en ambos sentidos
    y cruza la calle), y solo si falla, `_camino` (router de vehículos, que respeta el sentido de las
    aristas y da vueltas a la manzana: 452 m frente a 125 m en un caso medido). Los experimentos
    siguen usando `_camino`, así que no cambian."""
    if desde == hasta:
        return [desde], 0.0
    try:
        etapas = tr.simulation.findIntermodalRoute(desde, hasta, modes="")
    except tr.exceptions.TraCIException:
        etapas = []
    aristas: List[str] = []
    for etapa in etapas:
        for e in etapa.edges:
            if not aristas or aristas[-1] != e:
                aristas.append(e)
    if aristas and aristas[0] == desde and aristas[-1] == hasta and not any(e.startswith(":") for e in aristas):
        return aristas, sum(e.travelTime for e in etapas)
    return _camino(tr, desde, hasta)


def aristas_peatonales_cerca(tr, x: float, y: float) -> List[Tuple[str, float]]:
    """Aristas peatonales (sin cruces internos) alrededor de (x, y), de la más cercana a la más lejana."""
    vistas, salida = set(), []
    # los anillos de siempre (hasta 50 m) y otros más amplios: el punto puede caer dentro de una
    # manzana, donde las aceras más cercanas son senderos sin salida
    amplios = [(round(r * math.cos(k * math.pi / 6), 1), round(r * math.sin(k * math.pi / 6), 1))
               for r in (75, 100, 130) for k in range(12)]
    for dx, dy in DESPLAZAMIENTOS_M + amplios:
        edge, pos = tr.simulation.convertRoad(x + dx, y + dy, vClass="pedestrian")[:2]
        if not edge.startswith(":") and edge not in vistas:
            vistas.add(edge)
            salida.append((edge, pos))
    return salida


@dataclass
class _Diligencia:
    """Una diligencia en curso: el peatón de un auto estacionado."""

    ped: str
    pa: str
    t_inicio: float
    caso: str
    visto: bool = False
    edge_auto: str = ""      # acera junto al auto: a donde vuelve el peatón web con «Me voy»
    pos_auto: float = 0.0


# Desplazamientos (m) que se prueban alrededor de un punto hasta encontrar una arista peatonal:
# anillos de radio creciente, 8 direcciones cada uno
DESPLAZAMIENTOS_M = [(0, 0)] + [
    (round(r * math.cos(k * math.pi / 4), 1), round(r * math.sin(k * math.pi / 4), 1))
    for r in (5, 10, 20, 35, 50) for k in range(8)
]


def arista_peatonal(tr, x: float, y: float) -> Tuple[str, float]:
    """(edge, posición) de la red para peatones junto a (x, y), sin áreas internas de cruce.

    SUMO 1.12 no admite terminar una caminata en una arista interna (su id empieza con ":"):
    si el punto cae en un cruce, se prueba un desplazamiento cercano.
    """
    for dx, dy in DESPLAZAMIENTOS_M:
        edge, pos = tr.simulation.convertRoad(x + dx, y + dy, vClass="pedestrian")[:2]
        if not edge.startswith(":"):
            return edge, pos
    raise RuntimeError(f"Sin arista peatonal cerca de ({x:.1f}, {y:.1f})")


def leer_destinos(csv_path: Path) -> Dict[str, Destino]:
    """`destinos.csv` → {nombre: (lat, lon, peso)}."""
    with csv_path.open(encoding="utf-8") as f:
        return {d["nombre"]: (float(d["lat"]), float(d["lon"]), float(d["peso"])) for d in csv.DictReader(f)}


class GestorPeatones:
    """Hook de `Controlador`: un peatón por cada llegada de un auto de búsqueda."""

    def __init__(self, destinos_csv: Path, semilla: int, p_regreso_corto: float = 0.15,
                 p_espera_en_auto: float = 0.10, registrar_trayectorias: bool = False, solo_web: bool = True):
        self.rng = random.Random(semilla)
        # Desde el 2026-11-18, por defecto solo bajan del auto los conductores de la app web. Los demás
        # se quedan dentro (su teléfono va con el auto, como el caso `en_auto`) y se van al terminar
        # su estadía; la IA cierra igual (ESTACIONADO → SALIENDO). Los resultados del proyecto ya se
        # generaron con todos los peatones: `solo_web=False` (`--todos-los-peatones`) los reproduce.
        self.solo_web = solo_web
        self.destinos = leer_destinos(destinos_csv)
        self.p_regreso_corto = p_regreso_corto
        self.p_espera_en_auto = p_espera_en_auto
        self.activos: Dict[str, _Diligencia] = {}
        self._aristas: Dict[str, Optional[Tuple[str, float]]] = {}
        self.llegadas = 0
        self.vueltas = 0
        self.liberados_sin_aparecer = 0
        self.sin_destino = 0
        self.casos: Counter = Counter()
        self._volver_pendiente: set = set()   # «Me voy» que esperan a que el peatón salga de un cruce
        self._registrar = registrar_trayectorias
        self.trayectorias: List[Tuple[float, str, float, float, str]] = []

    # ------------------------------------------------------------------ hook

    def on_paso(self, ctrl, t: float) -> None:
        """Llamado tras cada paso del `Controlador`."""
        tr = ctrl.traci
        for veh in tr.simulation.getParkingStartingVehiclesIDList():
            if parametro(ctrl, veh, "clase") == "busca" and veh not in self.activos:
                if self.solo_web and tr.vehicle.getParameter(veh, "web") != "1":
                    continue
                self._llegada(ctrl, veh, t)
        for veh in list(self._volver_pendiente):
            self._volver_ya(ctrl, veh)
        self._revisar_regresos(ctrl, t)
        if self._registrar and round(t) % INTERVALO_TRAYECTORIA_S == 0:
            self._muestrear_trayectorias(ctrl, t)

    # ------------------------------------------------------------------ llegada

    def _llegada(self, ctrl, veh: str, t: float) -> None:
        tr = ctrl.traci
        parada = tr.vehicle.getStops(veh)[0]
        pa = parada.stoppingPlaceID
        t_estadia = parada.duration
        tr.vehicle.setParkingAreaStop(veh, pa, duration=PARADA_EXTENDIDA_S)

        # El peatón nace y vuelve a la acera más cercana al auto (ver _punto_peaton).
        edge_auto, pos_auto = self._punto_peaton(tr, veh, pa)
        ped = f"ped_{veh}"
        tr.person.add(ped, edge_auto, pos_auto)
        web = tr.vehicle.getParameter(veh, "web") == "1"
        if web:
            destino = self._destino_web(tr, veh, edge_auto, pos_auto)
            if destino is None:
                # Sin acera cerca de la búsqueda alcanzable sin rodeo largo: se baja y se queda junto
                # a su auto (nunca un destino al azar lejos). «Me voy» lo devuelve al auto igual.
                tr.person.appendWaitingStage(ped, PARADA_EXTENDIDA_S, "junto_al_auto")
                self.activos[veh] = _Diligencia(ped, pa, t, "web_cerca", edge_auto=edge_auto, pos_auto=pos_auto)
                self.llegadas += 1
                self.casos["web_cerca"] += 1
                return
        else:
            destino = self._destino_con_camino(tr, veh, edge_auto)
        if web and destino is not None:
            # App web: siempre se baja y camina; espera hasta que el usuario pulse «Me voy» o se
            # acabe el tiempo máximo (orden `volver`), sin casos al azar.
            (edge_dest, pos_dest), ida, t_ida, vuelta = destino
            tr.person.appendWalkingStage(ped, ida, pos_dest)
            tr.person.appendWaitingStage(ped, PARADA_EXTENDIDA_S, "diligencia")
            tr.person.appendWalkingStage(ped, vuelta, pos_auto)
            self.activos[veh] = _Diligencia(ped, pa, t, "web", edge_auto=edge_auto, pos_auto=pos_auto)
            self.llegadas += 1
            self.casos["web"] += 1
            return
        if (not web and self.rng.random() < self.p_espera_en_auto) or destino is None:
            tr.person.appendWaitingStage(ped, max(MIN_DILIGENCIA_S, t_estadia), "en_auto")
            caso = "en_auto" if destino is not None else "sin_camino"
        else:
            (edge_dest, pos_dest), ida, t_ida, vuelta = destino
            espera = max(MIN_DILIGENCIA_S, t_estadia - 2 * t_ida)
            tr.person.appendWalkingStage(ped, ida, pos_dest)
            tr.person.appendWaitingStage(ped, espera, "diligencia")
            tr.person.appendWalkingStage(ped, vuelta, pos_auto)
            caso = "diligencia"
            if self.rng.random() < self.p_regreso_corto:
                # vuelve al auto, espera un momento y sale otra vez a la diligencia
                tr.person.appendWaitingStage(ped, ESPERA_CORTA_S, "en_auto")
                tr.person.appendWalkingStage(ped, ida, pos_dest)
                tr.person.appendWaitingStage(ped, ESPERA_CORTA_S, "diligencia")
                tr.person.appendWalkingStage(ped, vuelta, pos_auto)
                caso = "regreso_corto"

        self.activos[veh] = _Diligencia(ped, pa, t, caso)
        self.llegadas += 1
        self.casos[caso] += 1

    @staticmethod
    def _punto_peaton(tr, veh: str, pa: str) -> Tuple[str, float]:
        """(edge, posición) de la red para peatones junto al auto estacionado.

        Si no hay acera a 20 m (el puesto está junto a un cruce), se usa el centro del carril del
        propio parkingArea: su arista no es interna.
        """
        x, y = tr.vehicle.getPosition(veh)
        try:
            return arista_peatonal(tr, x, y)
        except RuntimeError:
            arista = tr.lane.getEdgeID(tr.parkingarea.getLaneID(pa))
            return arista, (tr.parkingarea.getStartPos(pa) + tr.parkingarea.getEndPos(pa)) / 2

    def _destino_con_camino(self, tr, veh: str, edge_auto: str):
        """Destino del auto si tiene camino a pie de ida y vuelta; si no, otro elegido por peso.

        Devuelve ((edge, pos), ida, t_ida, vuelta), o None si ningún destino tiene camino.
        """
        # S3-3: los escenarios de Tyrone (S2) traen el nombre en `destino_nombre` y en `destino` las
        # coordenadas; la demanda de S1 traía el nombre en `destino`.
        nombre = texto_traci(tr.vehicle.getParameter(veh, "destino_nombre")) or \
            texto_traci(tr.vehicle.getParameter(veh, "destino"))
        arista = self._arista_destino(tr, nombre)
        if arista is not None:
            ida = _camino(tr, edge_auto, arista[0])
            vuelta = _camino(tr, arista[0], edge_auto)
            if ida is not None and vuelta is not None:
                return (arista, ida[0], ida[1], vuelta[0])
        self.sin_destino += 1
        for _ in range(MAX_INTENTOS_DESTINO):
            nombre, arista = self._destino_al_azar(tr)
            ida = _camino(tr, edge_auto, arista[0])
            vuelta = _camino(tr, arista[0], edge_auto)
            if ida is not None and vuelta is not None:
                return (arista, ida[0], ida[1], vuelta[0])
        return None

    def _destino_web(self, tr, veh: str, edge_auto: str, pos_auto: float):
        """Destino del conductor web: la acera junto a la ubicación de su búsqueda (`param destino`
        = "lat,lon"). Si queda a menos de 40 m del auto, el lugar de `destinos.csv` más cercano a ese
        punto (a ≤ 200 m), para que se baje y camine un poco. Mismo formato que `_destino_con_camino`.
        """
        try:
            lat, lon = (float(v) for v in texto_traci(tr.vehicle.getParameter(veh, "destino")).split(","))
        except ValueError:
            return None
        x, y = tr.simulation.convertGeo(lon, lat, fromGeo=True)
        xa, ya = tr.vehicle.getPosition(veh)
        candidatos = []
        if math.hypot(x - xa, y - ya) >= DISTANCIA_MIN_WEB_M:
            candidatos.append((x, y))
        cercanos = []
        for nombre, (dlat, dlon, _) in self.destinos.items():
            dx, dy = tr.simulation.convertGeo(dlon, dlat, fromGeo=True)
            del_punto, del_auto = math.hypot(dx - x, dy - y), math.hypot(dx - xa, dy - ya)
            if del_punto <= DISTANCIA_MAX_WEB_M and del_auto >= DISTANCIA_MIN_WEB_M:
                cercanos.append((del_punto, dx, dy))
        candidatos += [(dx, dy) for _, dx, dy in sorted(cercanos)[:5]]
        for cx, cy in candidatos:
            # la acera más cercana puede ser un sendero suelto, sin conexión: se prueban varias
            recta = math.hypot(cx - xa, cy - ya)
            for arista in aristas_peatonales_cerca(tr, cx, cy):
                ida = _camino_web(tr, edge_auto, arista[0])
                vuelta = _camino_web(tr, arista[0], edge_auto)
                if ida is None or vuelta is None:
                    continue
                # sin rodeos largos: la red peatonal de SUMO a veces solo conecta dando la vuelta
                # a varias manzanas (a ~1,3 m/s, `ida[1]` segundos son ~1,3·ida[1] metros)
                if 1.3 * ida[1] > max(MAX_CAMINATA_WEB_M, 3 * recta):
                    continue
                return (arista, ida[0], ida[1], vuelta[0])
        return None

    def _arista_destino(self, tr, nombre: str) -> Optional[Tuple[str, float]]:
        """Arista peatonal del destino (cacheada), o None si no tiene acera cerca."""
        if nombre not in self._aristas:
            if nombre in self.destinos:
                lat, lon, _ = self.destinos[nombre]
                x, y = tr.simulation.convertGeo(lon, lat, fromGeo=True)
                try:
                    self._aristas[nombre] = arista_peatonal(tr, x, y)
                except RuntimeError:
                    self._aristas[nombre] = None
            else:
                return None
        return self._aristas[nombre]

    def _destino_al_azar(self, tr) -> Tuple[str, Tuple[str, float]]:
        """Un destino con acera, elegido por peso."""
        validos = [(n, self._arista_destino(tr, n)) for n in self.destinos]
        validos = [(n, a) for n, a in validos if a is not None]
        pesos = [self.destinos[n][2] for n, _ in validos]
        return self.rng.choices(validos, weights=pesos)[0]

    # ------------------------------------------------------------------ regreso

    def volver(self, ctrl, veh: str) -> bool:
        """El conductor da media vuelta ya y camina al auto (app web: «Me voy» o tiempo máximo).

        Desde donde esté (caminando hacia su destino o esperando ahí), se le pone un tramo a pie
        directo hasta el auto y se quita todo lo demás. Al llegar, `_revisar_regresos` reanuda el
        auto y `AutosWeb` ya le dio una salida lejana: se va manejando y la IA lo ve salir.
        Si en este paso cruza una intersección (arista interna), se reintenta en el siguiente.
        """
        self._volver_pendiente.add(veh)
        return self._volver_ya(ctrl, veh)

    def _volver_ya(self, ctrl, veh: str) -> bool:
        d = self.activos.get(veh)
        tr = ctrl.traci
        if d is None or d.ped not in tr.person.getIDList():
            self._volver_pendiente.discard(veh)
            return False
        actual = tr.person.getRoadID(d.ped)
        if not actual or actual.startswith(":"):
            return False  # en un cruce: SUMO no deja empezar una caminata ahí
        camino = _camino_web(tr, actual, d.edge_auto) if d.edge_auto else None
        if camino is None:
            # sin camino directo: al menos se quita la espera (vuelve al terminar la ida)
            for i in range(tr.person.getRemainingStages(d.ped)):
                if tr.person.getStage(d.ped, i).type == tr.constants.STAGE_WAITING:
                    tr.person.removeStage(d.ped, i)
                    break
            self._volver_pendiente.discard(veh)
            return True
        restantes = tr.person.getRemainingStages(d.ped)
        tr.person.appendWalkingStage(d.ped, camino[0], d.pos_auto)   # nuevo final: directo al auto
        for _ in range(restantes - 1):
            tr.person.removeStage(d.ped, 1)                            # lo que quedaba del itinerario
        tr.person.removeStage(d.ped, 0)                                # corta la etapa actual: media vuelta
        self._volver_pendiente.discard(veh)
        return True

    def _revisar_regresos(self, ctrl, t: float) -> None:
        ids = set(ctrl.traci.person.getIDList())
        for veh, d in list(self.activos.items()):
            if d.ped in ids:
                d.visto = True
            elif d.visto:
                self._terminar(ctrl, veh, volvio=True)
            elif t - d.t_inicio > TIMEOUT_APARICION_S:
                self._terminar(ctrl, veh, volvio=False)

    def _terminar(self, ctrl, veh: str, volvio: bool) -> None:
        """El peatón ya volvió (o nunca apareció): se reanuda el auto."""
        try:
            ctrl.traci.vehicle.resume(veh)
        except ctrl.traci.exceptions.TraCIException:
            pass  # el auto ya no está parado (p. ej. lo reanudó otro hook)
        del self.activos[veh]
        if volvio:
            self.vueltas += 1
        else:
            self.liberados_sin_aparecer += 1

    # ------------------------------------------------------------------ registro

    def _muestrear_trayectorias(self, ctrl, t: float) -> None:
        tc = ctrl.traci.constants
        for ped, datos in ctrl.personas.items():
            if ped.startswith("ped_"):
                x, y = datos[tc.VAR_POSITION]
                etapa = ctrl.traci.person.getStage(ped).description
                self.trayectorias.append((round(t, 1), ped, round(x, 2), round(y, 2), etapa))

    def escribir_trayectorias(self, csv_path: Path) -> None:
        """CSV `t_sim,ped_id,x,y,etapa` con la posición de cada peatón cada 10 s."""
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["t_sim", "ped_id", "x", "y", "etapa"])
            w.writerows(self.trayectorias)

    def resumen(self) -> dict:
        """Cifras de la corrida: llegadas, vueltas y los casos difíciles."""
        return {
            "llegadas": self.llegadas,
            "vueltas": self.vueltas,
            "liberados_sin_aparecer": self.liberados_sin_aparecer,
            "pendientes": len(self.activos),
            "sin_destino": self.sin_destino,
            "casos": dict(self.casos),
        }
