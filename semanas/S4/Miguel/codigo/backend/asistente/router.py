"""Router del asistente: POST /asistente/interpretar.

Freddy lo monta en la app principal con el prefijo /api/v1 (como backend.pagos.rutas). Mientras
tanto, app_dev.py lo sirve solo para probarlo.
"""

from __future__ import annotations

from fastapi import APIRouter, Body

from .interprete import interpretar
from .modelos import PedidoInterpretar, RespuestaInterpretar

router = APIRouter(prefix="/asistente", tags=["asistente"])

_EJEMPLO = {"destino": {"nombre": "Catedral Nueva", "lat": -2.897443, "lon": -79.005237},
            "duracion_min": 60, "fuente": "llm", "confianza": 1.0, "avisos": []}


@router.post(
    "/interpretar",
    response_model=RespuestaInterpretar,
    summary="Destino y duración a partir de una frase",
    responses={200: {"description": "Interpretación", "content": {"application/json": {"example": _EJEMPLO}}}},
)
def interpretar_texto(
    pedido: PedidoInterpretar = Body(..., openapi_examples={"catedral": {"summary": "Frase típica",
                                                                         "value": {"texto": "cerca de la Catedral Nueva una hora"}}}),
) -> RespuestaInterpretar:
    """Con LLM si hay clave; si no (o si falla), por reglas. Si falta algo, la app usa el formulario."""
    return interpretar(pedido.texto).salida()
