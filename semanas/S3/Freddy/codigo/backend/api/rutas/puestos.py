"""`GET /puestos`: puestos con la ocupación que estima el sistema."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends

from comun import esquemas as e

from ...nucleo.ocupacion import MapaOcupacion
from .. import dependencias as dep
from .. import ejemplos as ej

router = APIRouter(tags=["puestos"])


@router.get("/puestos", response_model=List[e.Puesto], summary="Puestos y ocupación estimada",
            responses=ej.respuesta(200, "puestos"))
def listar(mapa: MapaOcupacion = Depends(dep.mapa)) -> List[e.Puesto]:
    """Cada `parkingArea` con su capacidad y las plazas ocupadas según las sesiones abiertas."""
    return mapa.como_contrato()
