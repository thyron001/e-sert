"""`GET /api/v1/espejo/candidatos` (S3-3, contrato §7).

Devuelve los últimos candidatos que mandó el controlador en el bloque interno `espejo` (autos con
app en `BUSCANDO` o `GUIADO` que siguen en la red). Si el controlador todavía no manda ese bloque
(versión anterior a S3-3), se calculan del último snapshot como antes. Lista vacía si no hay
simulación. Siempre con `Cache-Control: no-store`: los candidatos cambian cada segundo.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Response

from comun import esquemas as e

from ..api import dependencias as dep
from ..api import ejemplos as ej

router = APIRouter()


@router.get("/espejo/candidatos", response_model=List[e.CandidatoEspejo], tags=["espejo"],
            summary="Autos con app que se pueden seguir", responses=ej.respuesta(200, "candidatos_espejo"))
def candidatos(response: Response, s: dep.Servicios = Depends(dep.servicios)) -> List[e.CandidatoEspejo]:
    """Vehículos con app que todavía no estacionan (`BUSCANDO` o `GUIADO`)."""
    response.headers["Cache-Control"] = "no-store"
    lista = s.espejo.lista_candidatos()
    return s.mundo.candidatos_espejo() if lista is None else lista
