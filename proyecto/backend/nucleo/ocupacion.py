"""Mapa de ocupación **según los eventos de la app** (no la ocupación real de SUMO).

Cada sesión abierta ocupa una plaza de su puesto. Los autos sin app no se ven: esa diferencia
con el mensaje `verdad` es justamente el KPI de precisión del mapa.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from sqlalchemy import func, select

from comun import esquemas as e

from .db import BaseDatos, PuestoTabla, SesionParqueo, distancia_m
from .errores import ErrorNucleo


@dataclass(frozen=True)
class InfoPuesto:
    """Datos fijos de un puesto."""

    puesto_id: str
    lat: float
    lon: float
    calle: str
    capacidad: int


@dataclass(frozen=True)
class PuestoCercano:
    """Un puesto con plazas libres y su distancia al punto consultado."""

    puesto_id: str
    lat: float
    lon: float
    libres: int
    distancia_m: float


class MapaOcupacion:
    """Ocupación en memoria por puesto, alimentada por las sesiones (iniciar/cerrar)."""

    def __init__(self, puestos: Iterable[InfoPuesto]):
        self.puestos: Dict[str, InfoPuesto] = {p.puesto_id: p for p in puestos}
        self._ocupados: Dict[str, int] = {pid: 0 for pid in self.puestos}

    @classmethod
    def desde_bd(cls, bd: BaseDatos) -> "MapaOcupacion":
        """Construye el mapa con los puestos de la base y las sesiones que siguen abiertas."""
        with bd.fabrica() as s:
            puestos = [InfoPuesto(p.id, p.lat, p.lon, p.calle, p.capacidad)
                       for p in s.scalars(select(PuestoTabla)).all()]
            abiertas = s.execute(
                select(SesionParqueo.puesto_id, func.count())
                .where(SesionParqueo.estado != e.EstadoSesion.CERRADA.value)
                .group_by(SesionParqueo.puesto_id)
            ).all()
        mapa = cls(puestos)
        for pid, n in abiertas:
            mapa._ocupados[pid] = int(n)
        return mapa

    # ------------------------------------------------------------------ eventos

    def existe(self, puesto_id: str) -> bool:
        return puesto_id in self.puestos

    def ocupados(self, puesto_id: str) -> int:
        return self._ocupados[puesto_id]

    def libres(self, puesto_id: str) -> int:
        return self.puestos[puesto_id].capacidad - self._ocupados[puesto_id]

    def hay_lugar(self, puesto_id: str) -> bool:
        return self.libres(puesto_id) > 0

    def fijar(self, puesto_id: str, ocupados: int) -> None:
        """Sincroniza un puesto con el conteo de sesiones abiertas de la base."""
        if not 0 <= ocupados <= self.puestos[puesto_id].capacidad:
            raise ValueError(f"{puesto_id}: {ocupados} ocupados fuera de rango")
        self._ocupados[puesto_id] = ocupados

    def ocupar(self, puesto_id: str) -> None:
        """Una sesión empezó en el puesto."""
        if not self.hay_lugar(puesto_id):
            raise ValueError(f"{puesto_id} ya está lleno según el mapa")
        self._ocupados[puesto_id] += 1

    def liberar(self, puesto_id: str) -> None:
        """Una sesión de ese puesto se cerró."""
        if self._ocupados[puesto_id] <= 0:
            raise ValueError(f"{puesto_id} no tiene plazas ocupadas que liberar")
        self._ocupados[puesto_id] -= 1

    # ------------------------------------------------------------------ consultas

    def libres_cerca(self, lat: float, lon: float, radio_m: float) -> List[PuestoCercano]:
        """Puestos con al menos una plaza libre a `radio_m` o menos, del más cercano al más lejano."""
        cercanos = []
        for p in self.puestos.values():
            libres = self.libres(p.puesto_id)
            if libres <= 0:
                continue
            d = distancia_m(lat, lon, p.lat, p.lon)
            if d <= radio_m:
                cercanos.append(PuestoCercano(p.puesto_id, p.lat, p.lon, libres, d))
        return sorted(cercanos, key=lambda c: (c.distancia_m, c.puesto_id))

    def recomendar(self, destino_lat: float, destino_lon: float,
                   excluir: Iterable[str] = ()) -> Optional[PuestoCercano]:
        """El puesto libre más cercano al destino (haversine). None si todo está lleno."""
        excluidos = set(excluir)
        mejor: Optional[PuestoCercano] = None
        for p in self.puestos.values():
            libres = self.libres(p.puesto_id)
            if libres <= 0 or p.puesto_id in excluidos:
                continue
            d = distancia_m(destino_lat, destino_lon, p.lat, p.lon)
            if mejor is None or (d, p.puesto_id) < (mejor.distancia_m, mejor.puesto_id):
                mejor = PuestoCercano(p.puesto_id, p.lat, p.lon, libres, d)
        return mejor

    def guiar(self, consulta: e.ConsultaGuia) -> e.Guia:
        """`GET /guia`: el puesto libre más cercano al destino. `distancia_m` es hasta el destino.

        Nunca devuelve un puesto lleno; si no queda ninguno libre, `SIN_PUESTOS_LIBRES`.
        """
        mejor = self.recomendar(consulta.destino_lat, consulta.destino_lon)
        if mejor is None:
            raise ErrorNucleo(e.CodigoError.SIN_PUESTOS_LIBRES, "No hay puestos con plazas libres.")
        return e.Guia(puesto_id=mejor.puesto_id, lat=mejor.lat, lon=mejor.lon,
                      distancia_m=round(mejor.distancia_m, 1))

    def como_contrato(self) -> List[e.Puesto]:
        """Respuesta de `GET /puestos`."""
        return [e.Puesto(puesto_id=p.puesto_id, lat=p.lat, lon=p.lon, calle=p.calle,
                         capacidad=p.capacidad, ocupados=self._ocupados[p.puesto_id])
                for p in self.puestos.values()]

    def ocupacion(self) -> List[e.OcupacionPuesto]:
        """`snapshot.puestos`: ocupación estimada por el sistema."""
        return [e.OcupacionPuesto(puesto_id=pid, ocupados=n, capacidad=self.puestos[pid].capacidad)
                for pid, n in self._ocupados.items()]
