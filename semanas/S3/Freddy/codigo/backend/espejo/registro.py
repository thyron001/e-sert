"""`RegistroEspejo`: lo que el backend sabe del modo espejo (S3-3, contrato §7, v1.2).

El controlador TraCI manda en cada snapshot un bloque **interno** `espejo` (candidatos y detalle de
los autos que algún teléfono sigue). El registro:

- guarda los últimos `candidatos` y el último `detalle` por vehículo, con su `t_sim` y la hora de
  recepción; el bloque nunca se difunde por `/ws/estado` (la ruta lo quita antes);
- cuenta los suscriptores por `veh_id` (pantallas conectadas a `/ws/espejo/{veh_id}`): esa lista es
  `espejos`, que va en cada snapshot del visor y en la respuesta al controlador;
- guarda cada recibo **una vez por `sesion_id`** (aunque el snapshot se repita) durante
  `conservar_recibo_s` (60 s), para las pantallas que se reconecten;
- sabe qué vehículos salieron de la simulación (ya no están en `vehiculos`) y si la corrida terminó.

Es seguro entre hilos: las rutas síncronas lo escriben desde el *threadpool* y los WebSocket lo
leen desde el bucle de eventos. `al_cambiar` (lo pone `ws_espejo`) despierta a los WebSocket.
"""

from __future__ import annotations

import threading
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Set, Tuple

from comun import esquemas as e

CONSERVAR_RECIBO_S = 60.0
INACTIVIDAD_S = 30.0  # sin snapshots durante este tiempo real: la corrida se da por terminada


def ahora_utc() -> datetime:
    """Hora UTC con milisegundos (el `ts` de los mensajes espejo)."""
    t = datetime.now(timezone.utc)
    return t.replace(microsecond=t.microsecond // 1000 * 1000)


@dataclass
class Entrada:
    """Último detalle de un vehículo seguido."""

    detalle: e.DetalleEspejo
    ts_controlador: datetime  # `ts` del snapshot (hora del controlador)
    recibido: float           # reloj monótono del backend al recibirlo
    version: int


@dataclass
class ReciboGuardado:
    veh_id: str
    recibo: e.Recibo
    recibido: float


class RegistroEspejo:
    """Estado del modo espejo entre el controlador (snapshots) y las pantallas (WebSocket)."""

    def __init__(self, conservar_recibo_s: float = CONSERVAR_RECIBO_S,
                 reloj: Callable[[], float] = time.monotonic, inactividad_s: float = INACTIVIDAD_S):
        self.conservar_recibo_s = conservar_recibo_s
        self.inactividad_s = inactividad_s
        self.corrida = 0  # sube cada vez que SUMO se relanza (t_sim vuelve atrás)
        self.ultimo_snapshot: Optional[float] = None
        self.recibos_vistos: Set[str] = set()  # sesion_id ya registrados en esta corrida (no se repiten)
        self.reloj = reloj
        self.candidatos: Optional[List[e.CandidatoEspejo]] = None  # None: el controlador no manda espejo
        self.detalles: Dict[str, Entrada] = {}
        self.basicos: Dict[str, Tuple[float, e.VehiculoSim]] = {}  # veh → (t_sim, vehículo del snapshot)
        self.presentes: Set[str] = set()
        self.vistos: Set[str] = set()  # vehículos que estuvieron en algún snapshot de esta corrida
        self.recibos: Dict[str, ReciboGuardado] = {}  # sesion_id → recibo
        self.suscriptores: Counter = Counter()
        self.fin_corrida = False
        self.t_sim: Optional[float] = None
        self.snapshots = 0
        self.recibos_recibidos = 0  # recibos distintos (por sesion_id)
        self.al_cambiar: Optional[Callable[[], None]] = None
        self._version = 0
        self._candado = threading.Lock()

    # ------------------------------------------------------------------ entrada del controlador

    def aplicar(self, paso: e.PasoSimulacion) -> List[str]:
        """Registra el snapshot (con o sin bloque `espejo`). Devuelve `espejos`."""
        ahora = self.reloj()
        with self._candado:
            if self.t_sim is not None and paso.t_sim < self.t_sim - 1:
                self._nueva_corrida()
            self.t_sim = paso.t_sim
            self.ultimo_snapshot = ahora
            self.snapshots += 1
            self.presentes = {v.id for v in paso.vehiculos}
            self.vistos |= self.presentes
            self.basicos = {v.id: (paso.t_sim, v) for v in paso.vehiculos}
            bloque = paso.espejo
            if bloque is not None:
                self.fin_corrida = self.fin_corrida or bloque.fin
                self.candidatos = [] if self.fin_corrida else list(bloque.candidatos)
                for veh, det in bloque.detalle.items():
                    self._version += 1
                    self.detalles[veh] = Entrada(det, paso.ts, ahora, self._version)
                    if det.recibo is not None and det.recibo.sesion_id not in self.recibos_vistos:
                        datos = det.recibo.model_dump(exclude={"sesion_id"})
                        self.recibos[det.recibo.sesion_id] = ReciboGuardado(veh, e.Recibo(**datos), ahora)
                        self.recibos_vistos.add(det.recibo.sesion_id)
                        self.recibos_recibidos += 1
            for sid in [s for s, r in self.recibos.items() if ahora - r.recibido > self.conservar_recibo_s]:
                del self.recibos[sid]
            for veh in [v for v in self.detalles if v not in self.presentes and not self.suscriptores[v]]:
                del self.detalles[veh]
            espejos = self._espejos()
        if self.al_cambiar is not None:
            self.al_cambiar()
        return espejos

    def _nueva_corrida(self) -> None:
        """`t_sim` volvió atrás: SUMO se relanzó. Se olvida lo de la corrida anterior."""
        self.candidatos = None
        self.detalles.clear()
        self.recibos.clear()
        self.recibos_vistos.clear()
        self.vistos.clear()
        self.fin_corrida = False
        self.corrida += 1  # las pantallas de la corrida anterior reciben fin_simulacion

    # ------------------------------------------------------------------ suscriptores

    def suscribir(self, veh_id: str) -> None:
        with self._candado:
            self.suscriptores[veh_id] += 1

    def liberar(self, veh_id: str) -> None:
        with self._candado:
            self.suscriptores[veh_id] -= 1
            if self.suscriptores[veh_id] <= 0:
                del self.suscriptores[veh_id]

    def _espejos(self) -> List[str]:
        return sorted(v for v, n in self.suscriptores.items() if n > 0)

    def espejos(self) -> List[str]:
        """Vehículos que algún teléfono sigue (campo `espejos` del snapshot)."""
        with self._candado:
            return self._espejos()

    # ------------------------------------------------------------------ lectura (WebSocket y rutas)

    def existe(self, veh_id: str) -> bool:
        with self._candado:
            return veh_id in self.presentes and not self.fin_corrida

    def lista_candidatos(self) -> Optional[List[e.CandidatoEspejo]]:
        """Últimos candidatos del controlador que siguen en la red (None si nunca mandó el bloque)."""
        with self._candado:
            if self.candidatos is None:
                return None
            return [c for c in self.candidatos if c.id in self.presentes]

    def version(self, veh_id: str) -> int:
        """Cambia cada vez que llega un detalle nuevo de `veh_id` (o un snapshot, si aún no hay detalle)."""
        with self._candado:
            entrada = self.detalles.get(veh_id)
            if entrada is not None:
                return entrada.version
            return -self.snapshots if veh_id in self.basicos else 0

    def mensaje(self, veh_id: str, recibo: Optional[e.Recibo] = None) -> Optional[e.MensajeEspejo]:
        """`{"tipo": "espejo"}` con lo último conocido de `veh_id` (validado con el esquema)."""
        with self._candado:
            entrada = self.detalles.get(veh_id)
            basico = self.basicos.get(veh_id)
        if entrada is not None:
            d = entrada.detalle
            return e.MensajeEspejo(
                veh_id=veh_id, t_sim=d.t_sim, ts=ahora_utc(), estado=d.estado, lat=d.lat, lon=d.lon,
                modo=d.modo, destino=d.destino, puesto=d.puesto, ruta=d.ruta, sesion=d.sesion,
                billetera=d.billetera, avisos=d.avisos, recibo=recibo)
        if basico is not None:
            # Aún no llega el detalle (el controlador se entera de `espejos` en la respuesta
            # siguiente): se manda lo que dice el snapshot.
            t_sim, v = basico
            return e.MensajeEspejo(veh_id=veh_id, t_sim=t_sim, ts=ahora_utc(), estado=v.estado,
                                   lat=v.lat, lon=v.lon, modo=v.modo, destino=v.destino, ruta=v.ruta,
                                   recibo=recibo)
        return None

    def recibo_pendiente(self, veh_id: str, enviados: Set[str]) -> Optional[Tuple[str, e.Recibo]]:
        """Recibo de `veh_id` que esta pantalla todavía no recibió (dentro de los 60 s)."""
        ahora = self.reloj()
        with self._candado:
            for sid, r in self.recibos.items():
                if r.veh_id == veh_id and sid not in enviados and ahora - r.recibido <= self.conservar_recibo_s:
                    return sid, r.recibo
        return None

    def fin(self, veh_id: str, corrida: Optional[int] = None) -> Optional[e.MotivoFinEspejo]:
        """Por qué termina el seguimiento de `veh_id`, o None si sigue.

        `fin_simulacion` si el controlador lo avisó, si SUMO se relanzó desde que la pantalla se
        conectó (`corrida` distinta) o si no llegan snapshots hace `inactividad_s` (el controlador
        murió sin avisar: sin esto, la pantalla recibiría latidos con datos viejos para siempre).
        """
        with self._candado:
            sin_datos = self.ultimo_snapshot is not None and self.reloj() - self.ultimo_snapshot > self.inactividad_s
            if self.fin_corrida or sin_datos or (corrida is not None and corrida != self.corrida):
                return e.MotivoFinEspejo.fin_simulacion
            if veh_id not in self.presentes:
                return e.MotivoFinEspejo.salio_simulacion
        return None

    def ts_controlador(self, veh_id: str) -> Optional[datetime]:
        with self._candado:
            entrada = self.detalles.get(veh_id)
            return None if entrada is None else entrada.ts_controlador
