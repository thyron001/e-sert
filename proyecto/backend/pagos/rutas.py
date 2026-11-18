"""Rutas de pagos (``/api/v1/pagos/*``), montadas por ``backend/api/main.py`` si este módulo existe.

Flujo: la app llama a ``POST /pagos/preparar`` → abre ``pay_url`` (``/pagos/ir/{id}``, que
salta al formulario de Payphone o a la página mock) → Payphone vuelve a ``GET /pagos/retorno``
→ se confirma y se acredita una sola vez → la página redirige al deep link de la app → la app
consulta ``GET /pagos/{client_transaction_id}``.

Estas rutas y el uso de ``RECARGA_MINIMA`` aquí no están en el contrato v1: van como pedido
a Freddy para ``CONTRATO.propuesto.md``.
"""

from __future__ import annotations

import html
import logging
from dataclasses import dataclass
from typing import Literal, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field, field_validator

from comun import esquemas as e

from ..api import dependencias as dep
from ..nucleo.errores import ErrorNucleo
from ..nucleo.tarifa import tarifa_vigente
from . import intenciones as it
from .payphone import Adaptador, AdaptadorMock, ConfigPagos, ErrorPayphone, crear_adaptador

log = logging.getLogger("esert.pagos")

router = APIRouter(prefix="/pagos", tags=["pagos"])

PATRON_USUARIO = r"^(sim_.+|app_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$"
MONTO_MAXIMO_USD = 1000.0


@dataclass
class EstadoPagos:
    config: ConfigPagos
    adaptador: Adaptador


def pagos(request: Request, servicios: dep.Servicios = Depends(dep.servicios)) -> EstadoPagos:
    """Config y adaptador, creados la primera vez (los tests pueden dejar los suyos en ``app.state.pagos``)."""
    estado: Optional[EstadoPagos] = getattr(request.app.state, "pagos", None)
    if estado is None:
        config = ConfigPagos.desde_entorno()
        estado = EstadoPagos(config, crear_adaptador(config))
        request.app.state.pagos = estado
        log.info("Pagos en modo %s · responseUrl %s", config.modo, config.response_url)
    if not getattr(request.app.state, "pagos_tabla", False):
        it.crear_tabla(servicios.bd)
        request.app.state.pagos_tabla = True
    return estado


class PedidoPago(BaseModel):
    usuario_id: str = Field(..., pattern=PATRON_USUARIO, examples=["app_3f0c2b9e-8f6a-4c1e-9d2a-5b7e1c4d8a90"])
    monto: float = Field(..., gt=0, examples=[5.0])
    url_app: Optional[str] = Field(None, description="Deep link de vuelta (esert://, exp:// o exps://)")

    @field_validator("url_app")
    @classmethod
    def _url_app(cls, valor: Optional[str]) -> Optional[str]:
        if valor is not None and not it.PATRON_URL_APP.match(valor):
            raise ValueError("url_app debe ser esert://, exp://, exps:// o la app web (https://…e-sert.tesisucuenca.com/)")
        return valor


class PagoPreparado(BaseModel):
    client_transaction_id: str
    payment_id: str
    pay_url: str
    modo: Literal["mock", "pruebas"]


class Intencion(BaseModel):
    client_transaction_id: str
    usuario_id: str
    monto: float
    estado: Literal["pendiente", "aprobado", "rechazado"]
    referencia_payphone: Optional[str] = None
    creada: str
    actualizada: str


# Ejemplos para OpenAPI (el test de Freddy exige ejemplo en toda respuesta 2xx y en los cuerpos).
_CTID = "rec_7c9e6679-7425-40de-944b-e07fc1f90ae7"
EJEMPLO_PEDIDO = {"usuario_id": "app_3f0c2b9e-8f6a-4c1e-9d2a-5b7e1c4d8a90", "monto": 10.0,
                  "url_app": "esert://pagos/retorno"}
EJEMPLO_PREPARADO = {"client_transaction_id": _CTID, "payment_id": "23178284",
                     "pay_url": f"https://demo.e-sert.tesisucuenca.com/api/v1/pagos/ir/{_CTID}", "modo": "pruebas"}
EJEMPLO_INTENCION = {"client_transaction_id": _CTID, "usuario_id": EJEMPLO_PEDIDO["usuario_id"], "monto": 10.0,
                     "estado": "aprobado", "referencia_payphone": "23178284",
                     "creada": "2026-10-27T15:45:00+00:00", "actualizada": "2026-10-27T15:45:20+00:00"}


def _ejemplo(codigo: int, ejemplo: dict, descripcion: str) -> dict:
    return {codigo: {"description": descripcion, "content": {"application/json": {"example": ejemplo}}}}


def _pagina(titulo: str, cuerpo: str, cabeza: str = "") -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">{cabeza}
<title>{html.escape(titulo)}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:420px;margin:40px auto;padding:0 16px;color:#212121}}
h1{{color:#C62828;font-size:1.5rem}}.b{{display:block;text-align:center;padding:14px;border-radius:8px;
margin:12px 0;font-weight:700;text-decoration:none;color:#fff;background:#C62828}}.g{{background:#757575}}
.m{{font-size:2.2rem;font-weight:800}}</style></head><body>{cuerpo}</body></html>""",
        headers={"Referrer-Policy": "origin", "Cache-Control": "no-store"},
    )


def enlace_app(deep_link: str, user_agent: str) -> str:
    """En Android, ``intent://...#Intent;scheme=<esquema>;end``: Chrome y los navegadores
    basados en Chromium (Brave, Edge) no abren un esquema propio (``exp://``, ``esert://``)
    desde un enlace o un ``location.href``, pero sí un intent. En iOS se deja el deep link."""
    if "android" not in user_agent.lower() or "://" not in deep_link or deep_link.startswith("https://"):
        return deep_link  # la app web (https) se abre como cualquier enlace
    esquema, resto = deep_link.split("://", 1)
    return f"intent://{resto}#Intent;scheme={esquema};end"


@router.post("/preparar", status_code=status.HTTP_201_CREATED, response_model=PagoPreparado,
             summary="Preparar una recarga con Payphone",
             responses=_ejemplo(201, EJEMPLO_PREPARADO, "Pago preparado: abrir pay_url"))
def preparar(pedido: PedidoPago = Body(..., openapi_examples={"recarga": {"summary": "Recarga de $10",
                                                                           "value": EJEMPLO_PEDIDO}}),
             servicios: dep.Servicios = Depends(dep.servicios),
             estado: EstadoPagos = Depends(pagos)) -> PagoPreparado:
    minimo = tarifa_vigente().recarga_minima_usd
    if round(pedido.monto * 100) < round(minimo * 100):
        raise ErrorNucleo(e.CodigoError.RECARGA_MINIMA, f"La recarga mínima es ${minimo:.2f}.",
                          {"monto": pedido.monto, "minimo": minimo})
    if pedido.monto > MONTO_MAXIMO_USD or round(pedido.monto * 100) != round(pedido.monto * 100, 6):
        raise ErrorNucleo(e.CodigoError.VALIDACION, f"El monto debe tener hasta 2 decimales y no pasar de ${MONTO_MAXIMO_USD:.0f}.",
                          {"monto": pedido.monto})
    faltan = estado.config.faltantes()
    if faltan:
        raise ErrorNucleo(e.CodigoError.ERROR_INTERNO, "Los pagos no están configurados en el servidor.",
                          {"faltan": faltan})

    intencion = it.crear(servicios.bd, pedido.usuario_id, pedido.monto, estado.adaptador.modo, pedido.url_app)
    ctid = intencion.client_transaction_id
    try:
        preparado = estado.adaptador.preparar(pedido.monto, ctid, f"Recarga e-sert {pedido.monto:.2f} USD")
    except ErrorPayphone:
        # El motivo (errorCode de Payphone) ya quedó en el log; a la app solo el mensaje genérico.
        it.rechazar(servicios.bd, ctid)
        raise ErrorNucleo(e.CodigoError.ERROR_INTERNO, "No se pudo preparar el pago con Payphone.") from None
    it.anotar_preparado(servicios.bd, ctid, preparado["payment_id"], preparado["pay_url"])
    return PagoPreparado(client_transaction_id=ctid, payment_id=preparado["payment_id"],
                         pay_url=estado.config.url_api(f"/pagos/ir/{ctid}"), modo=estado.adaptador.modo)


@router.get("/ir/{client_transaction_id}", response_class=HTMLResponse, include_in_schema=False)
def ir(client_transaction_id: str, servicios: dep.Servicios = Depends(dep.servicios),
       _: EstadoPagos = Depends(pagos)) -> HTMLResponse:
    """Salto al formulario desde nuestro dominio: Payphone exige un Referer del dominio registrado."""
    try:
        intencion = it.obtener(servicios.bd, client_transaction_id)
    except it.IntencionNoExiste:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pago no encontrado") from None
    if intencion.estado != it.PENDIENTE or not intencion.pay_url_proveedor:
        return _pagina("Pago cerrado", "<h1>Este pago ya no está pendiente</h1><p>Vuelve a la app.</p>")
    destino = html.escape(intencion.pay_url_proveedor, quote=True)
    return _pagina(
        "Abriendo Payphone",
        f"""<h1>Abriendo el pago…</h1><p>Recarga de <b>${intencion.monto_centavos / 100:.2f}</b>.</p>
<a class="b" id="ir" href="{destino}">Continuar al pago</a>
<script>setTimeout(function(){{document.getElementById('ir').click()}},300)</script>""",
        '<meta name="referrer" content="origin">',
    )


@router.get("/mock", response_class=HTMLResponse, include_in_schema=False)
def pagina_mock(id: str = Query(...), clientTransactionId: str = Query(...),
                estado: EstadoPagos = Depends(pagos)) -> HTMLResponse:
    """Formulario de pago simulado (solo con ``PAYPHONE_MODO=mock``)."""
    if not isinstance(estado.adaptador, AdaptadorMock) or id not in estado.adaptador.pagos:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pago mock no encontrado")
    _, monto, _ = estado.adaptador.pagos[id]
    q = lambda d: html.escape(urlencode({"id": id, "clientTransactionId": clientTransactionId, "decision": d}), quote=True)  # noqa: E731
    return _pagina(
        "Pago simulado",
        f"""<h1>Payphone (mock)</h1><p>Pago simulado: no se usa ninguna tarjeta.</p>
<p class="m">${monto / 100:.2f}</p>
<a class="b" href="mock/decidir?{q('aprobar')}">Aprobar</a>
<a class="b g" href="mock/decidir?{q('rechazar')}">Rechazar</a>""",
    )


@router.get("/mock/decidir", include_in_schema=False)
def decidir_mock(id: str, clientTransactionId: str, decision: Literal["aprobar", "rechazar"],
                 estado: EstadoPagos = Depends(pagos)) -> RedirectResponse:
    if not isinstance(estado.adaptador, AdaptadorMock):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Modo mock desactivado")
    try:
        estado.adaptador.decidir(id, decision)
    except ErrorPayphone:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pago mock no encontrado") from None
    # Igual que Payphone: vuelve a la responseUrl con id y clientTransactionId (ruta relativa
    # al servidor para que funcione aunque ESERT_URL_PUBLICA no apunte a esta máquina).
    q = urlencode({"id": id, "clientTransactionId": clientTransactionId})
    return RedirectResponse(f"/api/v1/pagos/retorno?{q}", status_code=status.HTTP_303_SEE_OTHER)


# Página HTML para el navegador (no es API JSON): fuera de OpenAPI.
@router.get("/retorno", response_class=HTMLResponse, include_in_schema=False)
def retorno(request: Request, clientTransactionId: str = Query(..., max_length=50),
            id: Optional[str] = Query(None, max_length=32), servicios: dep.Servicios = Depends(dep.servicios), bil=Depends(dep.billetera),
            estado: EstadoPagos = Depends(pagos)) -> HTMLResponse:
    """Confirma con Payphone y acredita una sola vez; luego devuelve al usuario a la app."""
    try:
        intencion = it.procesar_retorno(servicios.bd, bil, estado.adaptador, clientTransactionId, id)
    except it.IntencionNoExiste:
        return _pagina("Pago no encontrado", "<h1>Pago no encontrado</h1><p>Vuelve a la app.</p>")
    textos = {
        it.APROBADO: ("Pago confirmado", "Pago confirmado, vuelve a la app."),
        it.RECHAZADO: ("Pago no realizado", "El pago fue rechazado o cancelado. No se cobró nada."),
        it.PENDIENTE: ("Pago en revisión", "Aún no se pudo confirmar el pago. La app lo seguirá consultando."),
    }
    titulo, mensaje = textos[intencion.estado]
    separador = "&" if "?" in intencion.url_app else "?"
    volver = intencion.url_app + separador + urlencode({"clientTransactionId": clientTransactionId,
                                                         "estado": intencion.estado})
    volver_html = html.escape(enlace_app(volver, request.headers.get("user-agent", "")), quote=True)
    return _pagina(
        titulo,
        f"""<h1>{titulo}</h1><p>{mensaje}</p><p class="m">${intencion.monto_centavos / 100:.2f}</p>
<a class="b" id="volver" href="{volver_html}">Volver a e-sert</a>
<script>setTimeout(function(){{location.href=document.getElementById('volver').href}},800)</script>""",
    )


@router.get("/{client_transaction_id}", response_model=Intencion, summary="Estado de una recarga",
            responses=_ejemplo(200, EJEMPLO_INTENCION, "Estado de la intención de pago"))
def consultar(client_transaction_id: str, servicios: dep.Servicios = Depends(dep.servicios),
              _: EstadoPagos = Depends(pagos)) -> Intencion:
    try:
        return Intencion(**it.obtener(servicios.bd, client_transaction_id).como_json())
    except it.IntencionNoExiste:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pago no encontrado") from None
