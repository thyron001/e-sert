"""Billetera como libro de movimientos (contrato §5).

- `saldo = Σ recargas − Σ débitos` y `retenido = Σ retenciones − Σ liberaciones`. Ninguno se
  guarda: siempre se calculan del libro.
- `disponible = saldo − retenido` y `bloqueada = saldo < 0`.
- Cada operación es atómica. Si se pasa `s` (una sesión SQLAlchemy abierta), la operación
  entra en esa transacción; así `ServicioSesiones` combina varias en un todo-o-nada.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import case, func, literal_column, select
from sqlalchemy.orm import Session

from comun import esquemas as e

from . import tarifa as tar
from .db import BaseDatos, Movimiento, SesionParqueo, Usuario, ahora_utc
from .errores import ErrorNucleo

TM = e.TipoMovimiento


class Billetera:
    """Operaciones sobre el libro: recargar, retener, debitar, liberar y consultar."""

    def __init__(self, bd: BaseDatos):
        self.bd = bd

    # ------------------------------------------------------------------ escrituras

    def recargar(
        self,
        usuario: str,
        monto: float,
        referencia_payphone: Optional[str] = None,
        ts: Optional[datetime] = None,
        s: Optional[Session] = None,
    ) -> str:
        """Suma `monto` USD al saldo. Exige al menos `recarga_minima_usd`."""
        minimo = tar.tarifa_vigente().recarga_minima_usd
        if not isinstance(monto, (int, float)) or not math.isfinite(monto):
            raise ErrorNucleo(e.CodigoError.VALIDACION, "El monto de la recarga no es un número válido.")
        if tar.centavos(monto) < tar.centavos(minimo):
            raise ErrorNucleo(
                e.CodigoError.RECARGA_MINIMA,
                f"La recarga mínima es ${minimo:.2f}.",
                {"monto": monto, "minimo": minimo},
            )
        return self._asentar(usuario, TM.recarga, tar.centavos(monto), None, ts, referencia_payphone, s)

    def retener(self, usuario: str, centavos: int, sesion_id: str, ts: Optional[datetime] = None,
                s: Optional[Session] = None) -> str:
        """Aparta `centavos` del disponible para una sesión del usuario (no cambia el saldo)."""
        with self.bd.transaccion(s) as tx:
            _verificar_duenio(tx, usuario, sesion_id)
            disponible = self.estado_centavos(usuario, tx)["disponible"]
            if centavos > disponible:
                raise ErrorNucleo(e.CodigoError.SALDO_INSUFICIENTE,
                                  f"El disponible (${tar.usd(disponible):.2f}) no cubre la retención.",
                                  {"disponible": tar.usd(disponible), "retencion": tar.usd(centavos)})
            return self._asentar(usuario, TM.retencion, centavos, sesion_id, ts, None, tx)

    def debitar(self, usuario: str, centavos: int, sesion_id: str, ts: Optional[datetime] = None,
                s: Optional[Session] = None) -> str:
        """Resta `centavos` del saldo. Puede dejarlo negativo (la regla de bloqueo es aparte)."""
        with self.bd.transaccion(s) as tx:
            _verificar_duenio(tx, usuario, sesion_id)
            return self._asentar(usuario, TM.debito, centavos, sesion_id, ts, None, tx)

    def liberar(self, usuario: str, centavos: int, sesion_id: str, ts: Optional[datetime] = None,
                s: Optional[Session] = None) -> str:
        """Devuelve al disponible lo retenido para `sesion_id` (nunca más de lo retenido)."""
        with self.bd.transaccion(s) as tx:
            _verificar_duenio(tx, usuario, sesion_id)
            pendiente = self.retenido_de_sesion(sesion_id, tx)
            if centavos > pendiente:
                raise ValueError(f"Se quieren liberar {centavos} c y solo hay {pendiente} c retenidos")
            return self._asentar(usuario, TM.liberacion, centavos, sesion_id, ts, None, tx)

    def _asentar(self, usuario: str, tipo: e.TipoMovimiento, centavos: int, sesion_id: Optional[str],
                 ts: Optional[datetime], referencia: Optional[str], s: Optional[Session]) -> str:
        if centavos <= 0:
            raise ValueError("El monto de un movimiento debe ser positivo")
        with self.bd.transaccion(s) as tx:
            asegurar_usuario(tx, usuario)
            mov_id = f"mov_{uuid.uuid4()}"
            tx.add(Movimiento(id=mov_id, usuario_id=usuario, tipo=tipo.value, monto=centavos,
                              sesion_id=sesion_id, ts=ts or ahora_utc(), referencia_payphone=referencia))
            tx.flush()
            return mov_id

    # ------------------------------------------------------------------ lecturas

    def sumas(self, usuario: str, s: Optional[Session] = None) -> Dict[e.TipoMovimiento, int]:
        """Total en centavos por tipo de movimiento."""
        with self.bd.transaccion(s) as tx:
            filas = tx.execute(
                select(Movimiento.tipo, func.coalesce(func.sum(Movimiento.monto), 0))
                .where(Movimiento.usuario_id == usuario)
                .group_by(Movimiento.tipo)
            ).all()
        totales = {t: 0 for t in TM}
        for tipo, total in filas:
            totales[TM(tipo)] = int(total)
        return totales

    def estado_centavos(self, usuario: str, s: Optional[Session] = None) -> Dict[str, int]:
        """`{saldo, retenido, disponible}` en centavos, calculados del libro."""
        t = self.sumas(usuario, s)
        saldo = t[TM.recarga] - t[TM.debito]
        retenido = t[TM.retencion] - t[TM.liberacion]
        return {"saldo": saldo, "retenido": retenido, "disponible": saldo - retenido}

    def estado(self, usuario: str, s: Optional[Session] = None) -> Dict[str, object]:
        """`{saldo, retenido, disponible, bloqueada}` en USD."""
        c = self.estado_centavos(usuario, s)
        return {
            "saldo": tar.usd(c["saldo"]),
            "retenido": tar.usd(c["retenido"]),
            "disponible": tar.usd(c["disponible"]),
            "bloqueada": c["saldo"] < 0,
        }

    def bloqueada(self, usuario: str, s: Optional[Session] = None) -> bool:
        """Saldo negativo: no se permiten sesiones nuevas hasta recargar."""
        return self.estado_centavos(usuario, s)["saldo"] < 0

    def retenido_de_sesion(self, sesion_id: str, s: Optional[Session] = None) -> int:
        """Centavos aún retenidos para una sesión."""
        signo = case((Movimiento.tipo == TM.retencion.value, Movimiento.monto),
                     (Movimiento.tipo == TM.liberacion.value, -Movimiento.monto), else_=0)
        with self.bd.transaccion(s) as tx:
            total = tx.scalar(select(func.coalesce(func.sum(signo), 0)).where(Movimiento.sesion_id == sesion_id))
        return int(total)

    def movimientos(self, usuario: str, s: Optional[Session] = None) -> List[e.Movimiento]:
        """Movimientos del usuario en orden de registro, con el modelo del contrato."""
        with self.bd.transaccion(s) as tx:
            filas = tx.scalars(
                select(Movimiento).where(Movimiento.usuario_id == usuario).order_by(Movimiento.ts, literal_column("movimientos.rowid"))
            ).all()
            return [
                e.Movimiento(movimiento_id=m.id, tipo=TM(m.tipo), monto=tar.usd(m.monto), ts=m.ts,
                             sesion_id=m.sesion_id, referencia_payphone=m.referencia_payphone)
                for m in filas
            ]

    def como_contrato(self, usuario: str) -> e.Billetera:
        """Respuesta de `GET /billetera/{usuario_id}`."""
        est = self.estado(usuario)
        return e.Billetera(movimientos=self.movimientos(usuario), **est)


def _verificar_duenio(s: Session, usuario: str, sesion_id: str) -> None:
    """La sesión debe existir y ser del usuario (retención, débito y liberación van ligados a ella)."""
    duenio = s.scalar(select(SesionParqueo.usuario_id).where(SesionParqueo.id == sesion_id))
    if duenio != usuario:
        raise ValueError(f"La sesión {sesion_id} no es de {usuario}")


def asegurar_usuario(s: Session, usuario: str) -> None:
    """Crea el usuario si no existe (billetera implícita con saldo 0)."""
    if s.get(Usuario, usuario) is None:
        s.add(Usuario(id=usuario))
        s.flush()
