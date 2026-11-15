"""Fixtures de pagos: app de Freddy con un Payphone falso (nunca se lee el entorno ni .env)."""

from __future__ import annotations

import json
import uuid
from typing import Callable, Optional

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.api.main import Config, crear_app
from backend.pagos.payphone import AdaptadorMock, AdaptadorPayphone, ConfigPagos
from backend.pagos.rutas import EstadoPagos

TOKEN = "tok-SECRETO-123"
URL_PUBLICA = "https://demo.ejemplo.test"
URL_PAYPHONE = "https://pay.payphonetodoesposible.com"
PAYMENT_ID = "87654321"


def config_pruebas(**cambios) -> ConfigPagos:
    """ConfigPagos explícita en modo pruebas."""
    valores = dict(modo="pruebas", token=TOKEN, store_id="store-1", url_publica=URL_PUBLICA)
    valores.update(cambios)
    return ConfigPagos(**valores)


def nuevo_usuario() -> str:
    return f"app_{uuid.uuid4()}"


class FalsoPayphone:
    """Transporte httpx que imita Prepare y V2/Confirm, y cuenta las llamadas."""

    def __init__(self) -> None:
        self.pedidos: list[httpx.Request] = []
        self.llamadas_confirm = 0
        self.monto_centavos: Optional[int] = None  # se toma del Prepare si no se fija
        self.status_code = 3
        self.transaction_status = "Approved"
        self.fallo_red_confirm = False  # True: Confirm lanza ConnectError
        self.http_status_confirm = 200
        self.ctid_respuesta: Optional[str] = None
        self.fallo_red_prepare = False  # True: Prepare lanza ConnectError

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        cuerpo = json.loads(pedido.content or b"{}")
        if pedido.url.path == "/api/button/Prepare":
            if self.fallo_red_prepare:
                raise httpx.ConnectError("sin red", request=pedido)
            if self.monto_centavos is None:
                self.monto_centavos = cuerpo["amount"]
            return httpx.Response(200, json={
                "paymentId": int(PAYMENT_ID),
                "payWithPayPhone": "https://payp.page.link/abc",
                "payWithCard": "https://pay.payphonetodoesposible.com/PayWithCard/abc",
            })
        if pedido.url.path == "/api/button/V2/Confirm":
            self.llamadas_confirm += 1
            if self.fallo_red_confirm:
                raise httpx.ConnectError("sin red", request=pedido)
            if self.http_status_confirm >= 400:
                return httpx.Response(self.http_status_confirm, json={"errorCode": 20, "message": "falla"})
            return httpx.Response(200, json={
                "statusCode": self.status_code,
                "transactionStatus": self.transaction_status,
                "amount": self.monto_centavos,
                "authorizationCode": "AUTH01",
                "transactionId": cuerpo["id"],
                "clientTransactionId": self.ctid_respuesta or cuerpo["clientTxId"],
            })
        return httpx.Response(404, json={"message": "ruta desconocida"})


@pytest.fixture
def falso() -> FalsoPayphone:
    return FalsoPayphone()


@pytest.fixture
def fabrica_cliente(tmp_path):
    """Devuelve una función que arma un TestClient con el adaptador dado."""
    abiertos = []

    def _armar(adaptador_de: Callable[[ConfigPagos], object], config: Optional[ConfigPagos] = None) -> TestClient:
        cfg = config or config_pruebas()
        app = crear_app(Config(db_url=f"sqlite:///{tmp_path}/t{len(abiertos)}.db", puestos_csv=None,
                               token_sim="secreto", visor_dir=None))
        app.state.pagos = EstadoPagos(cfg, adaptador_de(cfg))
        cliente = TestClient(app)
        cliente.__enter__()
        abiertos.append(cliente)
        return cliente

    yield _armar
    for c in abiertos:
        c.__exit__(None, None, None)


@pytest.fixture
def cliente(fabrica_cliente, falso) -> TestClient:
    """App con AdaptadorPayphone sobre el transporte falso."""
    return fabrica_cliente(lambda cfg: AdaptadorPayphone(cfg, httpx.Client(transport=httpx.MockTransport(falso))))


@pytest.fixture
def cliente_mock(fabrica_cliente) -> TestClient:
    """App con AdaptadorMock (página local de pago simulado)."""
    return fabrica_cliente(lambda cfg: AdaptadorMock(cfg), config_pruebas(modo="mock", token="", store_id=""))
