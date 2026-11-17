"""Billetera: consulta y recarga (contrato §4.3 y §5)."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Path, status

from comun import esquemas as e

from ...nucleo.billetera import Billetera
from .. import dependencias as dep
from .. import ejemplos as ej

router = APIRouter(prefix="/billetera", tags=["billetera"])

UsuarioRuta = Path(..., pattern=r"^(sim_.+|app_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$",
                   description="sim_<vehId> o app_<uuid4>", examples=["sim_veh42"])


@router.get("/{usuario_id}", response_model=e.Billetera, summary="Saldo y movimientos",
            responses={**ej.respuesta(200, "billetera"), **ej.errores("VALIDACION")})
def consultar(usuario_id: str = UsuarioRuta, bil: Billetera = Depends(dep.billetera)) -> e.Billetera:
    """Un usuario sin movimientos tiene saldo 0 (billetera implícita, sin 404)."""
    return bil.como_contrato(usuario_id)


@router.post("/{usuario_id}/recarga", status_code=status.HTTP_201_CREATED, response_model=e.RecargaHecha,
             summary="Recargar saldo",
             responses={**ej.respuesta(201, "recarga_hecha", "Recarga asentada"),
                        **ej.errores("RECARGA_MINIMA", "VALIDACION")})
def recargar(
    usuario_id: str = UsuarioRuta,
    recarga: e.Recarga = Body(..., openapi_examples=ej.cuerpo("recarga", "Recarga de $5")),
    bil: Billetera = Depends(dep.billetera),
) -> e.RecargaHecha:
    """Asienta una recarga (los autos simulados no envían `referencia_payphone`)."""
    mov = bil.recargar(usuario_id, recarga.monto, recarga.referencia_payphone)
    return e.RecargaHecha(movimiento_id=mov, saldo=bil.estado(usuario_id)["saldo"])
