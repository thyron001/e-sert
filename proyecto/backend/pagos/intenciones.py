"""Intenciones de pago (tabla ``intenciones_pago``) y el retorno idempotente.

La tabla es de pagos (Miguel) y vive en la misma base que la billetera de Freddy, pero con su
propio ``DeclarativeBase``: no toca los modelos de ``backend/nucleo``. La billetera solo se
usa a través de ``Billetera.recargar``.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, select, update
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ..nucleo.billetera import Billetera
from ..nucleo.db import UTC, BaseDatos, Movimiento, ahora_utc
from .payphone import Adaptador, ErrorPayphone, centavos

log = logging.getLogger("esert.pagos")

PENDIENTE, APROBADO, RECHAZADO = "pendiente", "aprobado", "rechazado"
URL_APP_POR_DEFECTO = "esert://pagos/retorno"
# Deep links aceptados para volver a la app: esquema propio o Expo Go (exp:// y exps://).
# Deep links de la app Expo, o la app web en los dominios del proyecto (2026-11-18)
PATRON_URL_APP = re.compile(r"^((esert|exps?)://[^\s\"'<>]{1,200}"
                            r"|https://(demo\.)?e-sert\.tesisucuenca\.com/[^\s\"'<>]{0,200})$")


class BasePagos(DeclarativeBase):
    pass


class IntencionPago(BasePagos):
    __tablename__ = "intenciones_pago"

    client_transaction_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    usuario_id: Mapped[str] = mapped_column(String, index=True)
    monto_centavos: Mapped[int] = mapped_column(Integer)
    estado: Mapped[str] = mapped_column(String(10), default=PENDIENTE)
    modo: Mapped[str] = mapped_column(String(10))
    url_app: Mapped[str] = mapped_column(String, default=URL_APP_POR_DEFECTO)
    payment_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    pay_url_proveedor: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    referencia_payphone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    autorizacion: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    movimiento_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    creada: Mapped[datetime] = mapped_column(UTC())
    actualizada: Mapped[datetime] = mapped_column(UTC())

    def como_json(self) -> dict:
        return {
            "client_transaction_id": self.client_transaction_id,
            "usuario_id": self.usuario_id,
            "monto": self.monto_centavos / 100,
            "estado": self.estado,
            "referencia_payphone": self.referencia_payphone,
            "creada": self.creada.isoformat(),
            "actualizada": self.actualizada.isoformat(),
        }


class IntencionNoExiste(Exception):
    pass


def crear_tabla(bd: BaseDatos) -> None:
    BasePagos.metadata.create_all(bd.motor)


def nuevo_client_transaction_id() -> str:
    """``rec_<uuid4>``: 40 caracteres (Payphone admite hasta 50)."""
    return f"rec_{uuid.uuid4()}"


def crear(bd: BaseDatos, usuario_id: str, monto_usd: float, modo: str, url_app: Optional[str]) -> IntencionPago:
    ahora = ahora_utc()
    intencion = IntencionPago(
        client_transaction_id=nuevo_client_transaction_id(),
        usuario_id=usuario_id,
        monto_centavos=centavos(monto_usd),
        estado=PENDIENTE,
        modo=modo,
        url_app=url_app or URL_APP_POR_DEFECTO,
        creada=ahora,
        actualizada=ahora,
    )
    with bd.transaccion() as s:
        s.add(intencion)
    return intencion


def obtener(bd: BaseDatos, client_transaction_id: str) -> IntencionPago:
    with bd.transaccion() as s:
        intencion = s.get(IntencionPago, client_transaction_id)
        if intencion is None:
            raise IntencionNoExiste(client_transaction_id)
        return intencion


def anotar_preparado(bd: BaseDatos, client_transaction_id: str, payment_id: str, pay_url: str) -> None:
    with bd.transaccion() as s:
        s.execute(update(IntencionPago)
                  .where(IntencionPago.client_transaction_id == client_transaction_id)
                  .values(payment_id=payment_id, pay_url_proveedor=pay_url, actualizada=ahora_utc()))


def rechazar(bd: BaseDatos, client_transaction_id: str) -> None:
    """Pasa a ``rechazado`` solo si seguía pendiente (nunca deshace un aprobado)."""
    with bd.transaccion() as s:
        s.execute(update(IntencionPago)
                  .where(IntencionPago.client_transaction_id == client_transaction_id,
                         IntencionPago.estado == PENDIENTE)
                  .values(estado=RECHAZADO, actualizada=ahora_utc()))


def procesar_retorno(bd: BaseDatos, billetera: Billetera, adaptador: Adaptador,
                     client_transaction_id: str, payment_id: Optional[str]) -> IntencionPago:
    """Confirma el pago y acredita la billetera **una sola vez** por ``clientTransactionId``.

    Si la intención ya no está pendiente, no se vuelve a llamar a Payphone ni a la billetera.
    El paso a ``aprobado`` es un UPDATE condicionado a ``estado = 'pendiente'`` dentro de la
    misma transacción que la recarga: si dos retornos llegan a la vez, solo uno lo consigue.
    """
    intencion = obtener(bd, client_transaction_id)
    if intencion.estado != PENDIENTE:
        return intencion
    if not payment_id:
        # cancellationUrl: el usuario cerró el formulario de Payphone sin pagar.
        rechazar(bd, client_transaction_id)
        return obtener(bd, client_transaction_id)

    try:
        confirmado = adaptador.confirmar(payment_id, client_transaction_id)
    except ErrorPayphone as ex:
        # Se deja pendiente: un retorno posterior (o la app) puede volver a intentarlo.
        log.warning("No se pudo confirmar %s: %s", client_transaction_id, ex)
        return intencion

    coincide = (confirmado["client_transaction_id"] == client_transaction_id
                and centavos(confirmado["monto_usd"]) == intencion.monto_centavos)
    if not (confirmado["aprobado"] and coincide):
        if confirmado["aprobado"]:
            log.warning("Pago %s aprobado pero no coincide con la intención: no se acredita", client_transaction_id)
        rechazar(bd, client_transaction_id)
        return obtener(bd, client_transaction_id)

    with bd.transaccion() as s:
        ganado = s.execute(
            update(IntencionPago)
            .where(IntencionPago.client_transaction_id == client_transaction_id,
                   IntencionPago.estado == PENDIENTE)
            .values(estado=APROBADO, payment_id=payment_id, referencia_payphone=payment_id,
                    autorizacion=confirmado["autorizacion"], actualizada=ahora_utc())
        ).rowcount == 1
        ya_asentada = s.scalar(select(Movimiento.id).where(Movimiento.referencia_payphone == payment_id))
        if ganado and ya_asentada is None:
            movimiento = billetera.recargar(intencion.usuario_id, intencion.monto_centavos / 100,
                                            referencia_payphone=payment_id, s=s)
            s.execute(update(IntencionPago)
                      .where(IntencionPago.client_transaction_id == client_transaction_id)
                      .values(movimiento_id=movimiento))
            log.info("Recarga acreditada: %s (%d centavos)", client_transaction_id, intencion.monto_centavos)
    return obtener(bd, client_transaction_id)
