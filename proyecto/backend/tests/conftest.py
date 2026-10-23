"""Fixtures comunes: base en memoria con puestos mock y helpers de tiempo."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.nucleo.billetera import Billetera
from backend.nucleo.db import BaseDatos, PuestoTabla, puestos_mock
from backend.nucleo.ocupacion import MapaOcupacion
from backend.nucleo.sesiones import ServicioSesiones

T0 = datetime(2026, 10, 20, 14, 0, 0, tzinfo=timezone.utc)


def en(minutos: float) -> datetime:
    """Hora T0 + `minutos`."""
    return T0 + timedelta(minutes=minutos)


def armar(puestos=None):
    """Base en memoria + billetera + servicio de sesiones sobre los puestos dados."""
    bd = BaseDatos()
    bd.cargar_puestos(puestos if puestos is not None else puestos_mock())
    bil = Billetera(bd)
    srv = ServicioSesiones(bd, bil, MapaOcupacion.desde_bd(bd))
    return bd, bil, srv


@pytest.fixture
def sistema():
    return armar()


@pytest.fixture
def chico():
    """Dos puestos de capacidad 1 (para probar PUESTO_LLENO)."""
    return armar([
        PuestoTabla(id="pa_a_0", lat=-2.8970, lon=-79.0040, calle="A", capacidad=1),
        PuestoTabla(id="pa_b_0", lat=-2.8990, lon=-79.0060, calle="B", capacidad=1),
    ])
