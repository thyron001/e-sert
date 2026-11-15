"""Adaptadores de Payphone (Botón de Pagos) y su mock.

Fuente: documentación oficial de Payphone Developers, consultada el 2026-10-27:
- https://docs.payphone.app/boton-de-pago, secciones "Preparar transacción" (Prepare) y
  "Consultar respuesta" (Confirm).
- https://docs.payphone.app/configuracion-de-ambiente-y-credenciales (pruebas/producción).
- https://docs.payphone.app/codigos-de-error (clientTransactionId ≤ 50 caracteres,
  reference ≤ 100).

Lo que se usa de esa documentación:
- Prepare: ``POST {base}/api/button/Prepare`` con ``Authorization: Bearer <token>``. Los montos
  son **enteros en centavos** y deben cumplir
  ``amount = amountWithoutTax + amountWithTax + tax + service + tip``. Una recarga de billetera
  no grava IVA, así que se envía todo en ``amountWithoutTax`` (sin ``tax``). Responde
  ``paymentId``, ``payWithPayPhone`` y ``payWithCard``.
- Confirm: ``POST {base}/api/button/V2/Confirm`` con ``{"id": <int>, "clientTxId": "..."}``.
  Responde ``statusCode`` (3 = aprobada, 2 = cancelada), ``transactionStatus``
  ("Approved"/"Canceled"), ``amount`` en centavos, ``authorizationCode``, ``transactionId`` y
  ``clientTransactionId``. Si no se confirma en 5 minutos, Payphone reversa el pago.
- Al volver, Payphone añade ``?id=<int>&clientTransactionId=<str>`` a la ``responseUrl``.
- En el ambiente de pruebas todas las transacciones se aprueban y no llegan al banco; la URL
  base es la misma que en producción.
"""

from __future__ import annotations

import logging
import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Protocol, Tuple, TypedDict
from urllib.parse import urlencode

import httpx

log = logging.getLogger("esert.pagos")

URL_BASE_PAYPHONE = "https://pay.payphonetodoesposible.com"
URL_PUBLICA_DEMO = "https://demo.e-sert.tesisucuenca.com"
PREFIJO_API = "/api/v1"
TIEMPO_ESPERA_S = 10.0
ARCHIVO_ENV = Path(__file__).with_name(".env")


class ErrorPayphone(Exception):
    """Payphone no respondió o respondió algo que no se puede usar (sin datos sensibles)."""


class PagoPreparado(TypedDict):
    payment_id: str
    pay_url: str


class PagoConfirmado(TypedDict):
    aprobado: bool
    monto_usd: float
    autorizacion: Optional[str]
    client_transaction_id: str
    transaction_id: str


def _leer_env(ruta: Path) -> Dict[str, str]:
    """Lee un .env simple (CLAVE=valor). No usa python-dotenv para no sumar dependencias."""
    valores: Dict[str, str] = {}
    if not ruta.exists():
        return valores
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        valores[clave.strip()] = valor.strip().strip('"').strip("'")
    return valores


@dataclass(frozen=True)
class ConfigPagos:
    modo: str = "mock"  # "mock" | "pruebas"
    token: str = field(default="", repr=False)  # nunca en repr ni en logs
    store_id: str = ""
    url_base: str = URL_BASE_PAYPHONE
    url_publica: str = URL_PUBLICA_DEMO
    response_url_fija: str = ""

    @property
    def response_url(self) -> str:
        """``responseUrl`` de Payphone: ``PAYPHONE_RESPONSE_URL`` o ``ESERT_URL_PUBLICA`` + ruta de retorno."""
        return self.response_url_fija or f"{self.url_publica}{PREFIJO_API}/pagos/retorno"

    def url_api(self, ruta: str) -> str:
        return f"{self.url_publica}{PREFIJO_API}{ruta}"

    @classmethod
    def desde_entorno(cls, env: Optional[Dict[str, str]] = None, archivo: Path = ARCHIVO_ENV) -> "ConfigPagos":
        """Variables de entorno; si faltan, ``backend/pagos/.env``. Lo vacío toma el valor por defecto."""
        fuente = {**_leer_env(archivo), **{k: v for k, v in (os.environ if env is None else env).items() if v}}
        modo = (fuente.get("PAYPHONE_MODO") or "mock").strip().lower()
        if modo not in ("mock", "pruebas"):
            raise ValueError(f"PAYPHONE_MODO debe ser mock o pruebas, no {modo!r}")
        return cls(
            modo=modo,
            token=fuente.get("PAYPHONE_TOKEN", ""),
            store_id=fuente.get("PAYPHONE_STORE_ID", ""),
            url_base=(fuente.get("PAYPHONE_URL_BASE") or URL_BASE_PAYPHONE).rstrip("/"),
            url_publica=(fuente.get("ESERT_URL_PUBLICA") or URL_PUBLICA_DEMO).rstrip("/"),
            response_url_fija=fuente.get("PAYPHONE_RESPONSE_URL", ""),
        )

    def faltantes(self) -> list[str]:
        """Qué falta para el modo ``pruebas`` (nombres de variables, nunca valores)."""
        if self.modo != "pruebas":
            return []
        return [n for n, v in (("PAYPHONE_TOKEN", self.token), ("PAYPHONE_STORE_ID", self.store_id)) if not v]


def centavos(monto_usd: float) -> int:
    return int(round(monto_usd * 100))


class Adaptador(Protocol):
    modo: str

    def preparar(self, monto_usd: float, client_transaction_id: str, referencia: str) -> PagoPreparado: ...

    def confirmar(self, payment_id: str, client_transaction_id: str) -> PagoConfirmado: ...


class AdaptadorPayphone:
    """Cliente del Botón de Pagos de Payphone (Prepare y V2/Confirm)."""

    modo = "pruebas"

    def __init__(self, config: ConfigPagos, cliente_http: Optional[httpx.Client] = None):
        self.config = config
        self.http = cliente_http or httpx.Client(timeout=TIEMPO_ESPERA_S)

    def _cabeceras(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.config.token}", "Content-Type": "application/json"}

    def _post(self, ruta: str, cuerpo: dict) -> dict:
        try:
            r = self.http.post(f"{self.config.url_base}{ruta}", json=cuerpo, headers=self._cabeceras(),
                               timeout=TIEMPO_ESPERA_S)
        except httpx.HTTPError as ex:
            log.warning("Payphone %s sin respuesta: %s", ruta, type(ex).__name__)
            raise ErrorPayphone(f"Payphone no respondió ({type(ex).__name__})") from None
        if r.status_code >= 400:
            try:
                datos = r.json()
                detalle = f"errorCode={datos.get('errorCode')} {datos.get('message', '')}".strip()
            except ValueError:
                detalle = "sin cuerpo JSON"
            log.warning("Payphone %s respondió %s: %s", ruta, r.status_code, detalle)
            raise ErrorPayphone(f"Payphone respondió {r.status_code}: {detalle}")
        try:
            return r.json()
        except ValueError:
            raise ErrorPayphone("Payphone respondió algo que no es JSON") from None

    def preparar(self, monto_usd: float, client_transaction_id: str, referencia: str) -> PagoPreparado:
        monto = centavos(monto_usd)
        cuerpo = {
            "amount": monto,
            "amountWithoutTax": monto,  # recarga de billetera: sin IVA, amount = amountWithoutTax
            "currency": "USD",
            "clientTransactionId": client_transaction_id,
            "storeId": self.config.store_id,
            "reference": referencia[:100],
            "responseUrl": self.config.response_url,
            # Si cierra el formulario con la X, vuelve al retorno sin id: se marca rechazado.
            "cancellationUrl": f"{self.config.response_url}?{urlencode({'clientTransactionId': client_transaction_id})}",
            "lang": "es",
            "timeZone": -5,
        }
        datos = self._post("/api/button/Prepare", cuerpo)
        payment_id, pay_url = datos.get("paymentId"), datos.get("payWithCard") or datos.get("payWithPayPhone")
        if not payment_id or not pay_url:
            raise ErrorPayphone("Prepare no devolvió paymentId ni enlace de pago")
        log.info("Payphone Prepare ok: %s por %d centavos", client_transaction_id, monto)
        return {"payment_id": str(payment_id), "pay_url": pay_url}

    def confirmar(self, payment_id: str, client_transaction_id: str) -> PagoConfirmado:
        try:
            id_numerico = int(payment_id)
        except ValueError:
            raise ErrorPayphone("El id de Payphone no es un número") from None
        datos = self._post("/api/button/V2/Confirm", {"id": id_numerico, "clientTxId": client_transaction_id})
        aprobado = datos.get("statusCode") == 3 and datos.get("transactionStatus") == "Approved"
        log.info("Payphone Confirm %s: statusCode=%s", client_transaction_id, datos.get("statusCode"))
        return {
            "aprobado": aprobado,
            "monto_usd": int(datos.get("amount") or 0) / 100,
            "autorizacion": datos.get("authorizationCode"),
            "client_transaction_id": str(datos.get("clientTransactionId") or ""),
            "transaction_id": str(datos.get("transactionId") or payment_id),
        }


class AdaptadorMock:
    """Misma interfaz sin Payphone: el pago se decide en la página local ``/api/v1/pagos/mock``."""

    modo = "mock"

    def __init__(self, config: ConfigPagos):
        self.config = config
        # payment_id -> (client_transaction_id, centavos, decisión: None | "aprobar" | "rechazar")
        self.pagos: Dict[str, Tuple[str, int, Optional[str]]] = {}

    def preparar(self, monto_usd: float, client_transaction_id: str, referencia: str) -> PagoPreparado:
        payment_id = str(random.randint(10_000_000, 99_999_999))
        self.pagos[payment_id] = (client_transaction_id, centavos(monto_usd), None)
        q = urlencode({"id": payment_id, "clientTransactionId": client_transaction_id})
        return {"payment_id": payment_id, "pay_url": self.config.url_api(f"/pagos/mock?{q}")}

    def decidir(self, payment_id: str, decision: str) -> None:
        if payment_id not in self.pagos or decision not in ("aprobar", "rechazar"):
            raise ErrorPayphone("Pago mock desconocido")
        ctid, monto, _ = self.pagos[payment_id]
        self.pagos[payment_id] = (ctid, monto, decision)

    def confirmar(self, payment_id: str, client_transaction_id: str) -> PagoConfirmado:
        if payment_id not in self.pagos:
            raise ErrorPayphone("La transacción no existe")
        ctid, monto, decision = self.pagos[payment_id]
        if ctid != client_transaction_id:
            raise ErrorPayphone("La transacción no existe")
        return {
            "aprobado": decision == "aprobar",
            "monto_usd": monto / 100,
            "autorizacion": f"MOCK{payment_id[-6:]}" if decision == "aprobar" else None,
            "client_transaction_id": ctid,
            "transaction_id": payment_id,
        }


def crear_adaptador(config: ConfigPagos, cliente_http: Optional[httpx.Client] = None) -> Adaptador:
    return AdaptadorPayphone(config, cliente_http) if config.modo == "pruebas" else AdaptadorMock(config)
