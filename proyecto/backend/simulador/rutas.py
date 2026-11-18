"""Rutas de la demo en el VPS: el visor arranca y detiene la simulación con una clave.

- `GET  /api/v1/demo/estado`   público: si hay simulación, en qué fase y con qué escenario.
- `POST /api/v1/demo/iniciar`  con `X-Clave-Demo`: arranca SUMO + controlador (una corrida a la vez).
- `POST /api/v1/demo/detener`  con `X-Clave-Demo`: la detiene como un Ctrl+C.

Sin `ESERT_CLAVE_DEMO` configurada, iniciar y detener responden `DEMO_NO_DISPONIBLE`.
"""

from __future__ import annotations

import hmac
from typing import List, Literal, Optional

from fastapi import APIRouter, Body, Depends, Header, Request
from pydantic import BaseModel, Field

from comun import esquemas as e

from ..nucleo.errores import ErrorNucleo
from .gestor import Escenario, GestorSimulacion

router = APIRouter(prefix="/demo", tags=["demo"])

_EJ_ESTADO = {"disponible": True, "motivo": None, "corriendo": True, "fase": "corriendo",
              "escenario": {"id": "p50_rf_s2", "penetracion": 50, "semilla": 2, "ritmo": 2.0, "hasta_s": 3600,
                            "clasificador": "rf"},
              "inicio": "2026-11-18T00:13:59Z", "fin": None, "codigo_salida": None,
              "ultimas_lineas": ["Simulation version 1.12.0 started with time: 0.00"]}
_EJ_INACTIVA = {**_EJ_ESTADO, "corriendo": False, "fase": "inactiva", "escenario": None, "inicio": None,
                "ultimas_lineas": []}


def _resp(estado: int, ejemplo: dict, *codigos: str) -> dict:
    from ..api import ejemplos as ej
    return {estado: {"description": "Estado de la simulación", "content": {"application/json": {"example": ejemplo}}},
            **ej.errores(*codigos)}


_EJ_CUERPO = {"demo": {"summary": "La demo de la exposición, en vivo", "value": {"penetracion": 50, "ritmo": 1}}}


class ParametrosDemo(BaseModel):
    """Escenario de la demo. Por defecto, el de `demo/config_demo.yaml` (`p50_rf_s2`, ritmo 2)."""

    penetracion: Literal[20, 50, 80] = Field(50, description="% de vehículos con app")
    semilla: int = Field(2, ge=1, le=5)
    ritmo: float = Field(2.0, ge=0.5, le=10, description="Veces el tiempo real (1 = en vivo)")
    hasta_s: int = Field(3600, ge=300, le=4500, description="Segundo de simulación final")
    clasificador: Literal["rf", "umbral"] = "rf"


class EscenarioDemo(BaseModel):
    id: str
    penetracion: int
    semilla: int
    ritmo: float
    hasta_s: int
    clasificador: str


class EstadoDemo(BaseModel):
    disponible: bool = Field(description="El servidor puede correr SUMO y tiene la clave configurada")
    motivo: Optional[str] = Field(None, description="Por qué no está disponible")
    corriendo: bool
    fase: Literal["inactiva", "preparando", "corriendo", "deteniendo"]
    escenario: Optional[EscenarioDemo] = None
    inicio: Optional[str] = None
    fin: Optional[str] = None
    codigo_salida: Optional[int] = None
    ultimas_lineas: List[str] = Field(default_factory=list, description="Final del log de la corrida")


def gestor(request: Request) -> GestorSimulacion:
    return request.app.state.simulador


def _clave_configurada(request: Request) -> Optional[str]:
    return getattr(request.app.state.config, "clave_demo", None)


def exigir_clave(request: Request,
                 x_clave_demo: Optional[str] = Header(None, description="Clave de la demo (ESERT_CLAVE_DEMO)")) -> None:
    clave = _clave_configurada(request)
    if not clave:
        raise ErrorNucleo(e.CodigoError.DEMO_NO_DISPONIBLE, "El servidor no tiene ESERT_CLAVE_DEMO configurada.")
    if not x_clave_demo or not hmac.compare_digest(x_clave_demo.encode(), clave.encode()):
        raise ErrorNucleo(e.CodigoError.CLAVE_DEMO_INVALIDA, "Falta la clave de la demo o no coincide.")


def _a_respuesta(request: Request, g: GestorSimulacion) -> EstadoDemo:
    est = g.estado()
    motivo = est.motivo or (None if _clave_configurada(request) else "falta ESERT_CLAVE_DEMO en el servidor")
    esc = est.escenario
    return EstadoDemo(
        disponible=motivo is None, motivo=motivo, corriendo=est.corriendo, fase=est.fase,
        escenario=EscenarioDemo(id=esc.id, penetracion=esc.penetracion, semilla=esc.semilla, ritmo=esc.ritmo,
                                hasta_s=esc.hasta_s, clasificador=esc.clasificador) if esc else None,
        inicio=est.inicio, fin=est.fin, codigo_salida=est.codigo_salida, ultimas_lineas=est.ultimas_lineas)


@router.get("/estado", response_model=EstadoDemo, summary="Estado de la simulación de la demo",
            responses=_resp(200, _EJ_INACTIVA))
def estado(request: Request, g: GestorSimulacion = Depends(gestor)) -> EstadoDemo:
    return _a_respuesta(request, g)


@router.post("/iniciar", response_model=EstadoDemo, status_code=202, summary="Arranca la simulación (🔑)",
             dependencies=[Depends(exigir_clave)],
             responses=_resp(202, _EJ_ESTADO, "CLAVE_DEMO_INVALIDA", "DEMO_EN_CURSO", "DEMO_NO_DISPONIBLE", "VALIDACION"))
def iniciar(request: Request, params: Optional[ParametrosDemo] = Body(None, openapi_examples=_EJ_CUERPO),
            g: GestorSimulacion = Depends(gestor)) -> EstadoDemo:
    p = params or ParametrosDemo()
    try:
        g.iniciar(Escenario(penetracion=p.penetracion, semilla=p.semilla, ritmo=p.ritmo, hasta_s=p.hasta_s,
                            clasificador=p.clasificador))
    except LookupError as exc:
        raise ErrorNucleo(e.CodigoError.DEMO_NO_DISPONIBLE, str(exc)) from exc
    except RuntimeError as exc:
        raise ErrorNucleo(e.CodigoError.DEMO_EN_CURSO, str(exc)) from exc
    return _a_respuesta(request, g)


@router.post("/detener", response_model=EstadoDemo, summary="Detiene la simulación (🔑)",
             dependencies=[Depends(exigir_clave)],
             responses=_resp(200, _EJ_INACTIVA, "CLAVE_DEMO_INVALIDA", "DEMO_NO_DISPONIBLE"))
def detener(request: Request, g: GestorSimulacion = Depends(gestor)) -> EstadoDemo:
    try:
        g.detener()
    except LookupError as exc:
        raise ErrorNucleo(e.CodigoError.DEMO_NO_DISPONIBLE, str(exc)) from exc
    return _a_respuesta(request, g)
