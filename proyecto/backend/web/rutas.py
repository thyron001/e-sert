"""Rutas de la app web (`/app/`): `/api/v1/web/*`. Ver `servicio.py`.

Sin autenticación: el `usuario_id` (`app_<uuid>`) que guarda el navegador es la llave. La
billetera es de prueba y nadie paga dinero real.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Body, Depends, Path, Request
from pydantic import BaseModel, Field

from comun import esquemas as e

from ..api import ejemplos as ej
from .servicio import ServicioWeb

router = APIRouter(prefix="/web", tags=["web"])

USUARIO = Path(..., pattern=r"^app_[0-9a-f-]{36}$", description="`app_<uuid>` que guarda el navegador")

_EJ_SESION = {
    "id": "web_1a2b3c4d", "veh_id": "sim_web_1a2b3c4d", "modo": "buscar", "estado": "activa",
    "puesto_id": "pa_337277973#1_0", "pagado_min": 60, "pagado_hasta": 4200.0, "t_inicio": 600.0,
    "t_llegada": 590.0, "motivo": None, "mensaje": None, "debitado": 0.5, "restante_s": 3000,
    "alerta": None, "puede_extender": True, "opciones_min": [30, 60, 90, 120], "eleccion_restante_s": None,
    "puesto": {"puesto_id": "pa_337277973#1_0", "codigo": "123", "calle": "Simón Bolívar",
               "lat": -2.8973, "lon": -79.0044},
    "auto": {"lat": -2.8974, "lon": -79.0043, "estado": "A_PIE", "modo": "a_pie", "ruta": []},
}
_EJ_ESTADO = {"usuario_id": "app_0b7c3f5e-1d2a-4c3b-9e8f-7a6b5c4d3e2f", "saldo": 4.5, "t_sim": 1200.0,
              "sim_activa": True, "sesion": _EJ_SESION}


def _resp(estado: int, ejemplo: Any, *codigos: str) -> Dict[int, dict]:
    return {estado: {"description": "Respuesta correcta", "content": {"application/json": {"example": ejemplo}}},
            **ej.errores(*codigos)}


class Ubicacion(BaseModel):
    lat: float = Field(..., ge=-2.91, le=-2.885, description="Latitud simulada (zona SERT)")
    lon: float = Field(..., ge=-79.02, le=-78.99, description="Longitud simulada (zona SERT)")


class CodigoPuesto(BaseModel):
    codigo: str = Field(..., pattern=r"^\s*\d{1,3}\s*$", description="Número del puesto pintado en la calle")


class Tiempo(BaseModel):
    minutos: int = Field(..., description="30, 60, 90 o 120")


class Extension(BaseModel):
    minutos: int = Field(30, description="Múltiplo de 30; el total no pasa de 120")


def web(request: Request) -> ServicioWeb:
    return request.app.state.servicios.web


@router.post("/usuarios", status_code=201, summary="Usuario nuevo con $5 de prueba",
             responses=_resp(201, {"usuario_id": _EJ_ESTADO["usuario_id"], "saldo": 5.0}))
def crear_usuario(w: ServicioWeb = Depends(web)) -> dict:
    usuario, saldo = w.crear_usuario()
    return {"usuario_id": usuario, "saldo": saldo}


@router.get("/usuarios/{usuario_id}", summary="Estado completo para la app (sondeo cada segundo)",
            responses=_resp(200, _EJ_ESTADO, "VALIDACION"))
def estado(usuario_id: str = USUARIO, w: ServicioWeb = Depends(web)) -> dict:
    return w.estado(usuario_id)


@router.post("/usuarios/{usuario_id}/buscar", status_code=202, summary="Buscar el parqueadero libre más cercano",
             responses=_resp(202, _EJ_ESTADO, "SALDO_INSUFICIENTE", "SESION_ACTIVA", "DEMO_NO_DISPONIBLE", "VALIDACION"))
def buscar(usuario_id: str = USUARIO, cuerpo: Ubicacion = Body(..., openapi_examples={
        "parque": {"summary": "Junto al Parque Calderón", "value": {"lat": -2.8975, "lon": -79.0045}}}),
        w: ServicioWeb = Depends(web)) -> dict:
    return w.buscar(usuario_id, cuerpo.lat, cuerpo.lon)


@router.post("/usuarios/{usuario_id}/estacionado", status_code=202, summary="Ya estacioné: pagar con el código",
             responses=_resp(202, _EJ_ESTADO, "PUESTO_NO_EXISTE", "PUESTO_LLENO", "SALDO_INSUFICIENTE",
                             "SESION_ACTIVA", "DEMO_NO_DISPONIBLE", "VALIDACION"))
def estacionado(usuario_id: str = USUARIO, cuerpo: CodigoPuesto = Body(..., openapi_examples={
        "codigo": {"summary": "Puesto 123", "value": {"codigo": "123"}}}),
        w: ServicioWeb = Depends(web)) -> dict:
    return w.estacionado(usuario_id, cuerpo.codigo)


@router.post("/usuarios/{usuario_id}/tiempo", summary="Elegir el tiempo al llegar (se debita ya)",
             responses=_resp(200, _EJ_ESTADO, "SALDO_INSUFICIENTE", "TRANSICION_INVALIDA", "VALIDACION"))
def tiempo(usuario_id: str = USUARIO, cuerpo: Tiempo = Body(..., openapi_examples={
        "hora": {"summary": "Una hora ($0,50)", "value": {"minutos": 60}}}),
        w: ServicioWeb = Depends(web)) -> dict:
    return w.elegir_tiempo(usuario_id, cuerpo.minutos)


@router.post("/usuarios/{usuario_id}/extender", summary="Extender el tiempo (se debita ya)",
             responses=_resp(200, _EJ_ESTADO, "SALDO_INSUFICIENTE", "TRANSICION_INVALIDA", "VALIDACION"))
def extender(usuario_id: str = USUARIO, cuerpo: Extension = Body(..., openapi_examples={
        "media": {"summary": "Media hora más ($0,25)", "value": {"minutos": 30}}}),
        w: ServicioWeb = Depends(web)) -> dict:
    return w.extender(usuario_id, cuerpo.minutos)


@router.post("/usuarios/{usuario_id}/me-voy", summary="Me voy: el conductor vuelve al auto",
             responses=_resp(200, _EJ_ESTADO, "SESION_NO_EXISTE", "TRANSICION_INVALIDA", "VALIDACION"))
def me_voy(usuario_id: str = USUARIO, w: ServicioWeb = Depends(web)) -> dict:
    return w.me_voy(usuario_id)


@router.get("/puestos", summary="Puestos con su código y la ocupación real de la simulación",
            responses=_resp(200, [{"puesto_id": "pa_337277973#1_0", "codigo": "123", "calle": "Simón Bolívar",
                                   "lat": -2.8973, "lon": -79.0044, "capacidad": 10, "ocupados": 7}]))
def puestos(w: ServicioWeb = Depends(web)) -> List[dict]:
    return w.lista_puestos()
