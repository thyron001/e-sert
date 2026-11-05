"""`GET /salud` y `GET /tarifa`."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from comun import esquemas as e

from ...nucleo import tarifa as tar
from ...nucleo.mundo import EstadoMundo
from .. import dependencias as dep
from .. import ejemplos as ej

router = APIRouter(tags=["sistema"])


@router.get("/salud", response_model=e.Salud, summary="Estado del backend",
            responses=ej.respuesta(200, "salud"))
def salud(mundo: EstadoMundo = Depends(dep.mundo)) -> e.Salud:
    """`ok`, versión del contrato y `t_sim` del último paso recibido (null sin simulación)."""
    return mundo.salud()


@router.get("/tarifa", response_model=e.Tarifa, summary="Tarifa vigente (tarifa.json)",
            responses={200: {"description": "Contenido de `comun/tarifa.json`",
                             "content": {"application/json": {"example": tar.tarifa_vigente().a_json()}}}})
def tarifa() -> e.Tarifa:
    """Parámetros de cobro de `comun/tarifa.json` (contrato §5)."""
    return tar.tarifa_vigente()
