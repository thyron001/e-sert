"""Servicios del núcleo que la API inyecta con `Depends`, y el control del token de simulación.

`crear_app` arma un `Servicios` (base, billetera, sesiones, mapa, mundo y gestor WS) y lo deja
en `app.state.servicios`. Los tests crean la app con SQLite en memoria y obtienen servicios
nuevos e independientes.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Optional, Union

from fastapi import Depends, Header, Request

from comun import esquemas as e

from ..espejo.registro import RegistroEspejo
from ..espejo.ws_espejo import DifusorEspejo
from ..nucleo.billetera import Billetera
from ..nucleo.db import BaseDatos, puestos_iniciales
from ..nucleo.errores import ErrorNucleo
from ..nucleo.mundo import EstadoMundo
from ..nucleo.ocupacion import MapaOcupacion
from ..nucleo.sesiones import ServicioSesiones
from .ws import GestorConexiones


@dataclass
class Servicios:
    """Todo lo que las rutas necesitan, construido una vez por app."""

    bd: BaseDatos
    billetera: Billetera
    sesiones: ServicioSesiones
    mapa: MapaOcupacion
    mundo: EstadoMundo
    gestor: GestorConexiones
    token_sim: Optional[str] = None
    espejo: Optional[RegistroEspejo] = None
    difusor_espejo: Optional[DifusorEspejo] = None

    def __post_init__(self) -> None:
        if self.espejo is None:
            self.espejo = RegistroEspejo()
        if self.difusor_espejo is None:
            self.difusor_espejo = DifusorEspejo()
        self.espejo.al_cambiar = self.difusor_espejo.despertar

    @classmethod
    def armar(cls, db_url: str, puestos_csv: Optional[str] = None,
              token_sim: Optional[str] = None) -> "Servicios":
        bd = BaseDatos(db_url)
        bd.cargar_puestos(puestos_iniciales(puestos_csv))
        billetera = Billetera(bd)
        mapa = MapaOcupacion.desde_bd(bd)
        return cls(bd=bd, billetera=billetera, sesiones=ServicioSesiones(bd, billetera, mapa), mapa=mapa,
                   mundo=EstadoMundo(mapa), gestor=GestorConexiones(), token_sim=token_sim or None)

    def publicar_snapshot(self, mensaje: Union[e.PasoSimulacion, e.MensajeKpi]) -> bool:
        """Entrada **en proceso** del controlador TraCI.

        Un `PasoSimulacion` se convierte en `snapshot` + `verdad` (como mucho uno por segundo
        de simulación); un `MensajeKpi` se difunde tal cual. Devuelve si se difundió.
        """
        if isinstance(mensaje, e.MensajeKpi):
            self.gestor.publicar(mensaje)
            return True
        # S3-3: el bloque interno `espejo` va al registro y se quita del paso antes de seguir;
        # `snapshot` nunca lo copia, y así tampoco queda en `mundo.ultimo_paso`.
        self.mundo.espejos = set(self.espejo.aplicar(mensaje))
        mensaje.espejo = None
        difusion = self.mundo.aplicar_paso(mensaje)
        if difusion is None:
            return False
        self.gestor.publicar(difusion.snapshot)
        self.gestor.publicar(difusion.verdad)
        return True


def servicios(request: Request) -> Servicios:
    return request.app.state.servicios


def billetera(s: Servicios = Depends(servicios)) -> Billetera:
    return s.billetera


def sesiones(s: Servicios = Depends(servicios)) -> ServicioSesiones:
    return s.sesiones


def mapa(s: Servicios = Depends(servicios)) -> MapaOcupacion:
    return s.mapa


def mundo(s: Servicios = Depends(servicios)) -> EstadoMundo:
    return s.mundo


def exigir_token_sim(
    s: Servicios = Depends(servicios),
    x_sim_token: Optional[str] = Header(None, description="Token del controlador (contrato §4.1)"),
    authorization: Optional[str] = Header(None, description="Alternativa: `Bearer <token>` (DESPLIEGUE.md)"),
) -> None:
    """Rutas 🔒: si el backend tiene token, exige `X-Sim-Token` o `Authorization: Bearer`."""
    if not s.token_sim:
        return
    recibido = x_sim_token
    if recibido is None and authorization and authorization.lower().startswith("bearer "):
        recibido = authorization[7:].strip()
    if recibido is None or not hmac.compare_digest(recibido.encode(), s.token_sim.encode()):
        raise ErrorNucleo(e.CodigoError.TOKEN_SIM_INVALIDO, "Falta el token de simulación o no coincide.")
