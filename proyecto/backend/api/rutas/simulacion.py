"""Entrada del controlador TraCI (🔒, contrato §4.4). Los candidatos del espejo están en `backend/espejo/rutas.py`."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, status

from comun import esquemas as e

from .. import dependencias as dep
from .. import ejemplos as ej

router = APIRouter()

_RESP_PASO = {**ej.respuesta(202, "aceptado", "Paso recibido (se difunde como mucho 1 por s simulado)"),
              **ej.errores("TOKEN_SIM_INVALIDO", "VALIDACION")}
_EJ_PASO = ej.cuerpo("sim_paso", "Un paso con un auto guiado y un peatón")


@router.post("/sim/paso", tags=["simulacion"], status_code=status.HTTP_202_ACCEPTED,
             response_model=e.RespuestaSnapshot, summary="[sim] Paso de simulación",
             dependencies=[Depends(dep.exigir_token_sim)], responses=_RESP_PASO)
def sim_paso(paso: e.PasoSimulacion = Body(..., openapi_examples=_EJ_PASO),
             s: dep.Servicios = Depends(dep.servicios)) -> e.RespuestaSnapshot:
    """Actualiza el mundo y difunde `snapshot` y `verdad` por `/ws/estado`. El bloque interno
    `espejo` queda en el registro del espejo; la respuesta dice qué autos sigue algún teléfono."""
    s.publicar_snapshot(paso)
    return s.respuesta_paso()


@router.post("/interno/snapshot", tags=["simulacion"], status_code=status.HTTP_202_ACCEPTED,
             response_model=e.RespuestaSnapshot, summary="[sim] Paso de simulación (alias para el VPS)",
             dependencies=[Depends(dep.exigir_token_sim)], responses=_RESP_PASO)
def interno_snapshot(paso: e.PasoSimulacion = Body(..., openapi_examples=_EJ_PASO),
                     s: dep.Servicios = Depends(dep.servicios)) -> e.RespuestaSnapshot:
    """Igual que `/sim/paso` (ver `comun/CONTRATO.propuesto.md`). Acepta `Authorization: Bearer`."""
    s.publicar_snapshot(paso)
    return s.respuesta_paso()


_EJ_KPI = ej.cuerpo("kpi_ws", "KPIs de sistema de la corrida")


@router.post("/sim/kpi", tags=["simulacion"], status_code=status.HTTP_202_ACCEPTED, response_model=e.Aceptado,
             summary="[sim] KPIs en vivo", dependencies=[Depends(dep.exigir_token_sim)], responses=_RESP_PASO)
def sim_kpi(kpi: e.MensajeKpi = Body(..., openapi_examples=_EJ_KPI),
            s: dep.Servicios = Depends(dep.servicios)) -> e.Aceptado:
    """Difunde `{"tipo": "kpi"}` por `/ws/estado` (S3-1: `KPIsSistema`, cada 10 s simulados)."""
    s.publicar_snapshot(kpi)
    return e.Aceptado()

