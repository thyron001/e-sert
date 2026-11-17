"""Ciclo de vida de la sesión de parqueo y reglas de cobro (contrato §3 y §5; CONTEXTO.md).

Reglas de cobro de `docs/CONTEXTO.md` y dónde se aplican:

1. Al buscar o iniciar, si el disponible no alcanza el bloque mínimo → `SALDO_INSUFICIENTE`;
   la recarga mínima es $5 (`Billetera.recargar` → `RECARGA_MINIMA`).
2. Al confirmar la llegada se retiene el bloque mínimo (`iniciar`).
3. Al detectar la salida se debita el tiempo real, en fracciones con mínimo, y se libera la
   retención (`cerrar`).
4. Se permite saldo negativo; mientras dure, la billetera queda bloqueada
   (`SESIONES_BLOQUEADAS`). Aviso cuando el saldo cubre menos de 10 min (`avisos`).
5. Tope de tiempo SERT con aviso previo (`avisos`).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from comun import esquemas as e

from . import tarifa as tar
from .billetera import Billetera, asegurar_usuario
from .db import BaseDatos, SesionParqueo, ahora_utc
from .errores import ErrorNucleo
from .ocupacion import MapaOcupacion

E = e.EstadoSesion
C = e.CodigoError
A = e.Aviso


class ServicioSesiones:
    """Inicia, transiciona y cierra sesiones; mantiene billetera y mapa coherentes."""

    def __init__(self, bd: BaseDatos, billetera: Optional[Billetera] = None,
                 mapa: Optional[MapaOcupacion] = None):
        self.bd = bd
        self.billetera = billetera or Billetera(bd)
        self.mapa = mapa or MapaOcupacion.desde_bd(bd)

    # ------------------------------------------------------------------ iniciar

    def iniciar(self, usuario: str, placa: str, puesto: str, ts: Optional[datetime] = None,
                t_sim: Optional[float] = None) -> e.SesionCreada:
        """Llegada confirmada: valida y retiene el bloque mínimo. La sesión nace en ESTACIONADO."""
        try:
            e.NuevaSesion(usuario_id=usuario, placa=placa, puesto_id=puesto, ts=ts, t_sim=t_sim)
        except ValidationError as err:
            raise ErrorNucleo(C.VALIDACION, "Datos de sesión inválidos.",
                              {"errores": err.errors(include_url=False, include_context=False)}) from err
        if not self.mapa.existe(puesto):
            raise ErrorNucleo(C.PUESTO_NO_EXISTE, f"No existe el puesto {puesto}.")
        retencion = tar.centavos(tar.retencion())
        capacidad = self.mapa.puestos[puesto].capacidad
        try:
            return self._iniciar(usuario, placa, puesto, ts, t_sim, retencion, capacidad)
        except IntegrityError as err:  # otro proceso abrió una sesión del usuario a la vez
            raise ErrorNucleo(C.SESION_ACTIVA, "El usuario ya tiene una sesión abierta.") from err

    def _iniciar(self, usuario, placa, puesto, ts, t_sim, retencion, capacidad) -> e.SesionCreada:
        with self.bd.transaccion() as s:
            if self._abierta_de(usuario, s) is not None:
                raise ErrorNucleo(C.SESION_ACTIVA, "El usuario ya tiene una sesión abierta.")
            estado = self.billetera.estado_centavos(usuario, s)
            if estado["saldo"] < 0:
                raise ErrorNucleo(C.SESIONES_BLOQUEADAS, "Saldo negativo: recarga para iniciar otra sesión.",
                                  {"saldo": tar.usd(estado["saldo"])})
            if estado["disponible"] < retencion:
                raise ErrorNucleo(
                    C.SALDO_INSUFICIENTE,
                    f"El disponible (${tar.usd(estado['disponible']):.2f}) no cubre la retención "
                    f"del bloque mínimo (${tar.usd(retencion):.2f}).",
                    {"disponible": tar.usd(estado["disponible"]), "retencion": tar.usd(retencion)},
                )
            # La base manda (puede haber otro proceso con su propio mapa); el mapa se sincroniza.
            ocupados = self._abiertas_en(puesto, s)
            if ocupados >= capacidad:
                self.mapa.fijar(puesto, capacidad)
                raise ErrorNucleo(C.PUESTO_LLENO, f"El puesto {puesto} no tiene plazas libres.")
            asegurar_usuario(s, usuario)
            sesion_id = f"ses_{uuid.uuid4()}"
            inicio = ts or ahora_utc()
            s.add(SesionParqueo(id=sesion_id, usuario_id=usuario, placa=placa, puesto_id=puesto,
                                estado=E.ESTACIONADO.value, inicio=inicio, t_sim_inicio=t_sim,
                                retenido=retencion))
            s.flush()
            self.billetera.retener(usuario, retencion, sesion_id, inicio, s)
            ocupados = self._abiertas_en(puesto, s)
        self.mapa.fijar(puesto, ocupados)
        return e.SesionCreada(sesion_id=sesion_id, estado=E.ESTACIONADO, retenido=tar.usd(retencion))

    # ------------------------------------------------------------------ transición

    def transicion(self, sesion_id: str, estado: e.EstadoSesion, ts: Optional[datetime] = None,
                   t_sim: Optional[float] = None) -> e.EstadoActualSesion:
        """Cambio de estado informado por el controlador; solo transiciones legales (§3)."""
        estado = E(estado)
        with self.bd.transaccion() as s:
            ses = self._cargar(sesion_id, s)
            actual = E(ses.estado)
            if actual is E.CERRADA:
                raise ErrorNucleo(C.SESION_YA_CERRADA, "La sesión ya está cerrada.")
            if (actual, estado) not in e.TRANSICIONES_LEGALES:
                raise ErrorNucleo(C.TRANSICION_INVALIDA, f"{actual.value} → {estado.value} no es legal.",
                                  {"desde": actual.value, "hacia": estado.value})
            ses.estado = estado.value
        return e.EstadoActualSesion(sesion_id=sesion_id, estado=estado)

    # ------------------------------------------------------------------ cerrar

    def cerrar(self, sesion_id: str, ts: Optional[datetime] = None,
               motivo: e.MotivoCierre = e.MotivoCierre.manual,
               t_sim: Optional[float] = None) -> e.SesionCerrada:
        """Salida: debita el tiempo real (fracciones + mínimo), libera la retención y libera el puesto.

        El débito se aplica completo aunque deje el saldo negativo; en ese caso la billetera
        queda bloqueada (se deriva de `saldo < 0`, no se guarda una marca aparte).
        """
        motivo = e.MotivoCierre(motivo)
        fin = ts or ahora_utc()
        with self.bd.transaccion() as s:
            ses = self._cargar(sesion_id, s)
            actual = E(ses.estado)
            if actual is E.CERRADA:
                raise ErrorNucleo(C.SESION_YA_CERRADA, "La sesión ya está cerrada.")
            if motivo is e.MotivoCierre.deteccion and actual is not E.SALIENDO:
                raise ErrorNucleo(C.TRANSICION_INVALIDA, "Un cierre por detección solo se acepta desde SALIENDO.",
                                  {"desde": actual.value, "hacia": E.CERRADA.value})
            minutos = _minutos(ses.inicio, fin, ses.t_sim_inicio, t_sim)
            if minutos < 0:
                raise ErrorNucleo(C.VALIDACION, "El cierre es anterior al inicio de la sesión.")
            cobrados = tar.minutos_cobrables(minutos)
            debito = tar.centavos(tar.costo(minutos))
            self.billetera.debitar(ses.usuario_id, debito, sesion_id, fin, s)
            pendiente = self.billetera.retenido_de_sesion(sesion_id, s)
            if pendiente > 0:
                self.billetera.liberar(ses.usuario_id, pendiente, sesion_id, fin, s)
            ses.estado = E.CERRADA.value
            ses.fin, ses.t_sim_fin = fin, t_sim
            ses.minutos_reales, ses.minutos_cobrados, ses.debitado = minutos, cobrados, debito
            ses.motivo_cierre = motivo.value
            saldo = self.billetera.estado_centavos(ses.usuario_id, s)["saldo"]
            puesto = ses.puesto_id
            s.flush()
            ocupados = self._abiertas_en(puesto, s)
        self.mapa.fijar(puesto, ocupados)
        return e.SesionCerrada(sesion_id=sesion_id, minutos_reales=round(minutos, 4),
                               minutos_cobrados=cobrados, debitado=tar.usd(debito), saldo=tar.usd(saldo))

    # ------------------------------------------------------------------ consultas

    def obtener(self, sesion_id: str) -> e.Sesion:
        """`GET /sesiones/{id}` con el modelo del contrato."""
        with self.bd.transaccion() as s:
            ses = self._cargar(sesion_id, s)
            return e.Sesion(
                sesion_id=ses.id, usuario_id=ses.usuario_id, placa=ses.placa, puesto_id=ses.puesto_id,
                estado=E(ses.estado), inicio=ses.inicio, fin=ses.fin, t_sim_inicio=ses.t_sim_inicio,
                t_sim_fin=ses.t_sim_fin, retenido=tar.usd(ses.retenido),
                minutos_reales=None if ses.minutos_reales is None else round(ses.minutos_reales, 4),
                minutos_cobrados=ses.minutos_cobrados,
                debitado=None if ses.debitado is None else tar.usd(ses.debitado),
            )

    def sesion_abierta(self, usuario: str) -> Optional[str]:
        """`sesion_id` abierta del usuario, o None."""
        with self.bd.transaccion() as s:
            return self._abierta_de(usuario, s)

    def recibo(self, sesion_id: str) -> e.Recibo:
        """Recibo de una sesión cerrada, comparado con la tarjeta SERT."""
        ses = self.obtener(sesion_id)
        if ses.estado is not E.CERRADA:
            raise ValueError("La sesión todavía no está cerrada")
        tarjeta = tar.costo_tarjeta_sert(ses.minutos_reales)
        return e.Recibo(minutos_reales=ses.minutos_reales, minutos_cobrados=ses.minutos_cobrados,
                        cobrado_usd=ses.debitado, tarjeta_sert_usd=tarjeta,
                        ahorro_usd=round(tarjeta - ses.debitado, 2))

    def avisos(self, sesion_id: str, ahora: Optional[datetime] = None,
               t_sim: Optional[float] = None) -> List[e.Aviso]:
        """Avisos para el espejo (§5): saldo bajo o agotado, tope de tiempo y bloqueo.

        Con la sesión cerrada se devuelven los avisos del usuario (`avisos_usuario`). Si la
        sesión empezó con `t_sim` y no se pasa `t_sim`, se usa la hora UTC `ahora`.
        """
        t = tar.tarifa_vigente()
        with self.bd.transaccion() as s:
            ses = self._cargar(sesion_id, s)
            saldo = self.billetera.estado_centavos(ses.usuario_id, s)["saldo"]
            abierta = E(ses.estado) is not E.CERRADA
            inicio, t_sim_inicio, usuario = ses.inicio, ses.t_sim_inicio, ses.usuario_id
        if not abierta:
            return self.avisos_usuario(usuario)
        avisos: List[e.Aviso] = []
        minutos = max(0.0, _minutos(inicio, ahora or ahora_utc(), t_sim_inicio, t_sim))
        en_curso = tar.centavos(tar.costo_en_curso(minutos))
        if saldo - en_curso < tar.centavos(tar.costo_en_curso(t.aviso_saldo_min)):
            avisos.append(A.saldo_bajo)
        if en_curso >= saldo + tar.centavos(t.saldo_negativo_max_usd):
            avisos.append(A.saldo_agotado)
        if minutos > t.tiempo_maximo_min:
            avisos.append(A.tiempo_maximo_superado)
        elif minutos >= t.tiempo_maximo_min - t.aviso_tiempo_min:
            avisos.append(A.tiempo_maximo_cerca)
        if saldo < 0:
            avisos.append(A.sesiones_bloqueadas)
        return avisos

    def avisos_usuario(self, usuario: str) -> List[e.Aviso]:
        """Avisos fuera de una sesión: `saldo_bajo` según el disponible, y el bloqueo."""
        est = self.billetera.estado_centavos(usuario)
        umbral = tar.centavos(tar.costo_en_curso(tar.tarifa_vigente().aviso_saldo_min))
        avisos: List[e.Aviso] = []
        if est["disponible"] < umbral:
            avisos.append(A.saldo_bajo)
        if est["saldo"] < 0:
            avisos.append(A.sesiones_bloqueadas)
        return avisos

    # ------------------------------------------------------------------ internos

    @staticmethod
    def _abiertas_en(puesto: str, s: Session) -> int:
        return int(s.scalar(select(func.count()).select_from(SesionParqueo).where(
            SesionParqueo.puesto_id == puesto, SesionParqueo.estado != E.CERRADA.value)))

    def _cargar(self, sesion_id: str, s: Session) -> SesionParqueo:
        ses = s.get(SesionParqueo, sesion_id)
        if ses is None:
            raise ErrorNucleo(C.SESION_NO_EXISTE, f"No existe la sesión {sesion_id}.")
        return ses

    @staticmethod
    def _abierta_de(usuario: str, s: Session) -> Optional[str]:
        return s.scalar(select(SesionParqueo.id).where(
            SesionParqueo.usuario_id == usuario, SesionParqueo.estado != E.CERRADA.value))


def _minutos(inicio: datetime, fin: datetime, t_sim_inicio: Optional[float], t_sim_fin: Optional[float]) -> float:
    """Duración en minutos: con `t_sim` si hay inicio y fin simulados; si no, con las horas UTC."""
    if t_sim_inicio is not None and t_sim_fin is not None:
        return (t_sim_fin - t_sim_inicio) / 60
    return (fin - inicio).total_seconds() / 60
