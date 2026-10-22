"""Base de datos del núcleo: SQLAlchemy 2 + SQLite.

La URL se configura: `sqlite:///:memory:` en los experimentos (rápido y reproducible) y un
archivo en la demo (`sqlite:///esert.db`). El dinero se guarda en **centavos enteros** y las
horas en UTC.

Tablas: `usuarios`, `movimientos`, `sesiones` y `puestos`. El saldo **no** se guarda en
ninguna parte: se calcula del libro `movimientos` (ver `billetera.py`).
"""

from __future__ import annotations

import csv
import math
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional, Union

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    TypeDecorator,
    create_engine,
    text,
    event,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

URL_MEMORIA = "sqlite:///:memory:"


class UTC(TypeDecorator):
    """Fecha con zona: se guarda como UTC sin zona (SQLite no la conserva) y se lee con UTC."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, valor, dialecto):
        if valor is None:
            return None
        if valor.tzinfo is None:
            raise ValueError("Las horas deben tener zona (UTC)")
        return valor.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, valor, dialecto):
        return None if valor is None else valor.replace(tzinfo=timezone.utc)


def ahora_utc() -> datetime:
    """Hora actual en UTC (con zona)."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base declarativa de las tablas del núcleo."""


class Usuario(Base):
    """Usuario simulado (`sim_<vehId>`) o de la app (`app_<uuid>`). Se crea implícitamente."""

    __tablename__ = "usuarios"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    creado: Mapped[datetime] = mapped_column(UTC, default=ahora_utc)


class Movimiento(Base):
    """Un asiento del libro de la billetera. `monto` en centavos, siempre positivo."""

    __tablename__ = "movimientos"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id"), index=True)
    tipo: Mapped[str] = mapped_column(String)  # recarga | retencion | debito | liberacion
    monto: Mapped[int] = mapped_column(Integer)  # centavos
    sesion_id: Mapped[Optional[str]] = mapped_column(ForeignKey("sesiones.id"), nullable=True)
    ts: Mapped[datetime] = mapped_column(UTC)
    referencia_payphone: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class SesionParqueo(Base):
    """Sesión de parqueo: nace en ESTACIONADO y termina en CERRADA."""

    __tablename__ = "sesiones"
    __table_args__ = (
        Index("ix_sesiones_abiertas", "usuario_id", "estado"),
        # Como mucho una sesión abierta por usuario, aunque haya varios procesos sobre la base.
        Index("ux_una_abierta_por_usuario", "usuario_id", unique=True,
              sqlite_where=text("estado != 'CERRADA'")),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id"))
    placa: Mapped[str] = mapped_column(String)
    puesto_id: Mapped[str] = mapped_column(ForeignKey("puestos.id"), index=True)
    estado: Mapped[str] = mapped_column(String)
    inicio: Mapped[datetime] = mapped_column(UTC)
    fin: Mapped[Optional[datetime]] = mapped_column(UTC, nullable=True)
    t_sim_inicio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    t_sim_fin: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    retenido: Mapped[int] = mapped_column(Integer)  # centavos
    minutos_reales: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    minutos_cobrados: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    debitado: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # centavos
    motivo_cierre: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class PuestoTabla(Base):
    """Un puesto (`parkingArea`) con su capacidad, cargado de `puestos.csv`."""

    __tablename__ = "puestos"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    calle: Mapped[str] = mapped_column(String)
    capacidad: Mapped[int] = mapped_column(Integer)


class BaseDatos:
    """Motor y fábrica de sesiones SQLAlchemy. `transaccion()` abre una transacción atómica."""

    def __init__(self, url: str = URL_MEMORIA, eco: bool = False):
        opciones = {}
        if url == URL_MEMORIA:
            # Una sola conexión compartida: si no, cada conexión vería otra base vacía.
            opciones = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
        self.motor = create_engine(url, echo=eco, future=True, **opciones)
        if url.startswith("sqlite"):
            event.listen(self.motor, "connect", _activar_claves_foraneas)
        Base.metadata.create_all(self.motor)
        self.fabrica = sessionmaker(self.motor, expire_on_commit=False, future=True)

    @contextmanager
    def transaccion(self, s: Optional[Session] = None) -> Iterator[Session]:
        """Abre una transacción, o reutiliza `s` si ya estamos dentro de una (todo o nada)."""
        if s is not None:
            yield s
            return
        with self.fabrica.begin() as nueva:
            yield nueva

    def cargar_puestos(self, puestos: List[PuestoTabla]) -> int:
        """Inserta o reemplaza puestos. Devuelve cuántos hay en total."""
        with self.transaccion() as s:
            for p in puestos:
                s.merge(p)
        with self.fabrica() as s:
            return len(s.scalars(select(PuestoTabla.id)).all())


def _activar_claves_foraneas(conexion, _registro):
    cursor = conexion.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def leer_puestos_csv(ruta: Union[str, Path]) -> List[PuestoTabla]:
    """Lee el `puestos.csv` de Tyrone (`puesto_id,edge,lane,calle,capacidad,lat,lon,x,y`)."""
    with Path(ruta).open(encoding="utf-8", newline="") as f:
        return [
            PuestoTabla(
                id=fila["puesto_id"],
                lat=float(fila["lat"]),
                lon=float(fila["lon"]),
                calle=fila.get("calle") or "",
                capacidad=int(fila["capacidad"]),
            )
            for fila in csv.DictReader(f)
        ]


# MOCK: reemplazar cuando proyecto/sumo/parqueos/puestos.csv (Tyrone) esté unificado.
def puestos_mock(n: int = 20) -> List[PuestoTabla]:
    """20 puestos ficticios en una cuadrícula alrededor del Parque Calderón."""
    calles = ["Simón Bolívar", "Gran Colombia", "Presidente Córdova", "Benigno Malo", "Luis Cordero"]
    puestos = []
    for i in range(n):
        fila, col = divmod(i, 5)
        puestos.append(
            PuestoTabla(
                id=f"pa_mock{i}_0",
                lat=round(-2.8955 - 0.0012 * fila, 6),
                lon=round(-79.0070 + 0.0012 * col, 6),
                calle=calles[col],
                capacidad=3 + (i % 4) * 2,
            )
        )
    return puestos


def ruta_puestos_proyecto() -> Path:
    """Ruta esperada de `puestos.csv` en `proyecto/` tras la unificación."""
    raiz = Path(__file__).resolve()
    for padre in raiz.parents:
        if (padre / "proyecto").is_dir():
            return padre / "proyecto" / "sumo" / "parqueos" / "puestos.csv"
    return Path("proyecto/sumo/parqueos/puestos.csv")


def puestos_iniciales(ruta: Optional[Union[str, Path]] = None) -> List[PuestoTabla]:
    """Puestos del CSV dado, o del de `proyecto/` si existe, o el mock de 20."""
    candidata = Path(ruta) if ruta else ruta_puestos_proyecto()
    if candidata.is_file():
        return leer_puestos_csv(candidata)
    return puestos_mock()


def distancia_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia haversine en metros."""
    r = 6_371_000.0
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df, dl = f2 - f1, math.radians(lon2 - lon1)
    a = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
