"""Estado del mundo simulado que el backend conoce (contrato §4.4, §6 y §7), sin HTTP.

- Último evento de ubicación y de modo de cada usuario (`POST /eventos/*`).
- Último paso de simulación (`POST /sim/paso`), del que salen el `snapshot`, la `verdad`
  y los candidatos del espejo.
- Límite de **1 paso por segundo de simulación**: un paso con `t_sim` a menos de 1 s del
  último aceptado se descarta (no se difunde).

`snapshot.puestos` sale del `MapaOcupacion` (lo que estima el sistema con las sesiones), nunca
de `verdad`, que solo se reenvía al visor.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from comun import esquemas as e

from .ocupacion import MapaOcupacion

INTERVALO_MIN_S = 1.0
"""Separación mínima, en segundos de simulación, entre dos pasos difundidos."""

ESTADOS_SIN_ESTACIONAR = {None, e.EstadoSesion.BUSCANDO, e.EstadoSesion.GUIADO}
"""Estados del vehículo que lo hacen candidato del espejo (aún no estaciona)."""


@dataclass
class UltimoEstado:
    """Lo último que se sabe de un usuario por sus eventos."""

    ubicacion: Optional[e.EventoUbicacion] = None
    modo: Optional[e.EventoModo] = None


@dataclass(frozen=True)
class Difusion:
    """Mensajes que produce un paso aceptado: el `snapshot` y la `verdad` para el visor."""

    snapshot: e.MensajeSnapshot
    verdad: e.MensajeVerdad


class EstadoMundo:
    """Memoria del backend sobre la simulación. Seguro para usar desde varios hilos."""

    def __init__(self, mapa: MapaOcupacion, intervalo_min_s: float = INTERVALO_MIN_S):
        self.mapa = mapa
        self.intervalo_min_s = intervalo_min_s
        self.usuarios: Dict[str, UltimoEstado] = {}
        self.ultimo_paso: Optional[e.PasoSimulacion] = None
        self.espejos: Set[str] = set()
        self._t_difundido: Optional[float] = None
        self._candado = threading.Lock()

    # ------------------------------------------------------------------ eventos

    def registrar_ubicacion(self, ev: e.EventoUbicacion) -> None:
        """Guarda la última ubicación del usuario (la más reciente por `ts`)."""
        with self._candado:
            u = self.usuarios.setdefault(ev.usuario_id, UltimoEstado())
            if u.ubicacion is None or ev.ts >= u.ubicacion.ts:
                u.ubicacion = ev

    def registrar_modo(self, ev: e.EventoModo) -> None:
        """Guarda el último modo clasificado del usuario (el más reciente por `ts`)."""
        with self._candado:
            u = self.usuarios.setdefault(ev.usuario_id, UltimoEstado())
            if u.modo is None or ev.ts >= u.modo.ts:
                u.modo = ev

    def ultimo(self, usuario_id: str) -> Optional[UltimoEstado]:
        return self.usuarios.get(usuario_id)

    # ------------------------------------------------------------------ simulación

    @property
    def t_sim(self) -> Optional[float]:
        """`t_sim` del último paso recibido (None si todavía no hay simulación)."""
        return None if self.ultimo_paso is None else self.ultimo_paso.t_sim

    def aplicar_paso(self, paso: e.PasoSimulacion) -> Optional[Difusion]:
        """Registra el paso. Devuelve qué difundir, o None si viola el límite de 1 por segundo.

        Un `t_sim` menor que el último difundido se toma como una corrida nueva (se reinicia
        el reloj), para que relanzar SUMO no deje el visor congelado.
        """
        with self._candado:
            previo = self._t_difundido
            if previo is not None and previo <= paso.t_sim < previo + self.intervalo_min_s:
                return None
            self._t_difundido = paso.t_sim
            self.ultimo_paso = paso
            espejos = sorted(v for v in self.espejos if any(x.id == v for x in paso.vehiculos))
        snapshot = e.MensajeSnapshot(
            t_sim=paso.t_sim, ts=paso.ts,
            vehiculos=[e.VehiculoSnapshot(id=v.id, lat=v.lat, lon=v.lon, estado=v.estado, con_app=v.con_app)
                       for v in paso.vehiculos],
            peatones=paso.peatones,
            puestos=self.mapa.ocupacion(),
            espejos=espejos,
        )
        verdad = e.MensajeVerdad(t_sim=paso.t_sim, ts=paso.ts, puestos=paso.verdad.puestos,
                                 estacionados=paso.verdad.estacionados,
                                 falsas_liberaciones=paso.verdad.falsas_liberaciones)
        return Difusion(snapshot, verdad)

    def candidatos_espejo(self) -> List[e.CandidatoEspejo]:
        """Vehículos con app del último paso que todavía no estacionan (§7)."""
        paso = self.ultimo_paso
        if paso is None:
            return []
        return [
            e.CandidatoEspejo(id=v.id, destino_nombre=v.destino.nombre if v.destino else "",
                              estado=v.estado, t_sim=paso.t_sim)
            for v in paso.vehiculos
            if v.con_app and v.estado in ESTADOS_SIN_ESTACIONAR
        ]

    def salud(self) -> e.Salud:
        """Respuesta de `GET /salud`."""
        ahora = datetime.now(timezone.utc)
        return e.Salud(ok=True, contrato=int(e.CONTRATO_VERSION), t_sim=self.t_sim,
                       ts=ahora.replace(microsecond=ahora.microsecond // 1000 * 1000))
