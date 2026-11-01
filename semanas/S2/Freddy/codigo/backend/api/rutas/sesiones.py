"""Sesiones de parqueo: crear, consultar, transicionar y cerrar (contrato §3 y §4.3)."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Path, status

from comun import esquemas as e

from ...nucleo.sesiones import ServicioSesiones
from .. import dependencias as dep
from .. import ejemplos as ej

router = APIRouter(prefix="/sesiones", tags=["sesiones"])

SesionIdRuta = Path(..., pattern=r"^ses_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                    description="ses_<uuid4>", examples=[ej.cargar("sesion")["sesion_id"]])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=e.SesionCreada,
             summary="Iniciar sesión (llegada confirmada)",
             responses={**ej.respuesta(201, "sesion_creada", "Sesión creada en ESTACIONADO"),
                        **ej.errores("SALDO_INSUFICIENTE", "SESIONES_BLOQUEADAS", "PUESTO_NO_EXISTE",
                                     "PUESTO_LLENO", "SESION_ACTIVA", "VALIDACION")})
def crear(
    nueva: e.NuevaSesion = Body(..., openapi_examples=ej.cuerpo("sesion_crear", "Auto simulado que estaciona")),
    srv: ServicioSesiones = Depends(dep.sesiones),
) -> e.SesionCreada:
    """Crea la sesión en `ESTACIONADO` y retiene el bloque mínimo."""
    return srv.iniciar(nueva.usuario_id, nueva.placa, nueva.puesto_id, nueva.ts, nueva.t_sim)


@router.get("/{sesion_id}", response_model=e.Sesion, summary="Consultar una sesión",
            responses={**ej.respuesta(200, "sesion"), **ej.errores("SESION_NO_EXISTE", "VALIDACION")})
def obtener(sesion_id: str = SesionIdRuta, srv: ServicioSesiones = Depends(dep.sesiones)) -> e.Sesion:
    """Sesión completa; los campos de cierre son null hasta cerrarla."""
    return srv.obtener(sesion_id)


@router.post("/{sesion_id}/transicion", response_model=e.EstadoActualSesion,
             summary="[sim] Cambiar de estado (controlador TraCI)",
             dependencies=[Depends(dep.exigir_token_sim)],
             responses={**ej.respuesta(200, "sesion_estado"),
                        **ej.errores("TOKEN_SIM_INVALIDO", "SESION_NO_EXISTE", "SESION_YA_CERRADA",
                                     "TRANSICION_INVALIDA", "VALIDACION")})
def transicion(
    sesion_id: str = SesionIdRuta,
    cuerpo: e.TransicionSesion = Body(..., openapi_examples=ej.cuerpo("sesion_transicion", "El conductor se bajó")),
    srv: ServicioSesiones = Depends(dep.sesiones),
) -> e.EstadoActualSesion:
    """Solo transiciones legales (§3); `CERRADA` va por `/cerrar`."""
    return srv.transicion(sesion_id, cuerpo.estado, cuerpo.ts, cuerpo.t_sim)


@router.post("/{sesion_id}/cerrar", response_model=e.SesionCerrada, summary="Cerrar y cobrar",
             responses={**ej.respuesta(200, "sesion_cerrada"),
                        **ej.errores("SESION_NO_EXISTE", "SESION_YA_CERRADA", "TRANSICION_INVALIDA", "VALIDACION")})
def cerrar(
    sesion_id: str = SesionIdRuta,
    cuerpo: e.CierreSesion = Body(..., openapi_examples=ej.cuerpo("sesion_cerrar", "Salida detectada")),
    srv: ServicioSesiones = Depends(dep.sesiones),
) -> e.SesionCerrada:
    """Debita el tiempo real (fracciones y mínimo), libera la retención y el puesto."""
    return srv.cerrar(sesion_id, cuerpo.ts, cuerpo.motivo, cuerpo.t_sim)
