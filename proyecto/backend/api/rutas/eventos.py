"""`POST /eventos/ubicacion` y `POST /eventos/modo` (202): último estado conocido del usuario.

S3-2: son `async def`. Solo guardan el último evento bajo un candado (microsegundos), así que no
necesitan el *threadpool* de FastAPI; con 200 usuarios a 1 Hz ese salto de hilo pesaba en el p95.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, status

from comun import esquemas as e

from ...nucleo.mundo import EstadoMundo
from .. import dependencias as dep
from .. import ejemplos as ej

router = APIRouter(prefix="/eventos", tags=["eventos"])

_ACEPTADO = {**ej.respuesta(202, "aceptado", "Evento registrado"), **ej.errores("VALIDACION")}


@router.post("/ubicacion", status_code=status.HTTP_202_ACCEPTED, response_model=e.Aceptado,
             summary="Registrar una posición GPS", responses=_ACEPTADO)
async def ubicacion(
    ev: e.EventoUbicacion = Body(..., openapi_examples=ej.cuerpo("ubicacion", "GPS con ruido de un auto con app")),
    mundo: EstadoMundo = Depends(dep.mundo),
) -> e.Aceptado:
    """Guarda la última ubicación del usuario. La ocupación del mapa la deciden las sesiones."""
    mundo.registrar_ubicacion(ev)
    return e.Aceptado()


@router.post("/modo", status_code=status.HTTP_202_ACCEPTED, response_model=e.Aceptado,
             summary="Registrar el modo que clasificó la IA", responses=_ACEPTADO)
async def modo(
    ev: e.EventoModo = Body(..., openapi_examples=ej.cuerpo("modo", "Resultado del clasificador")),
    mundo: EstadoMundo = Depends(dep.mundo),
) -> e.Aceptado:
    """Guarda el último modo (`a_pie`, `quieto`, `vehiculo`) del usuario."""
    mundo.registrar_modo(ev)
    return e.Aceptado()
