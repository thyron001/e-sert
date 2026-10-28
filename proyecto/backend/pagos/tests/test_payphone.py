"""Pruebas de ConfigPagos y del adaptador de Payphone (sin red: httpx.MockTransport)."""

from __future__ import annotations

import json

import httpx
import pytest

from backend.pagos.payphone import AdaptadorPayphone, ConfigPagos, ErrorPayphone, centavos

from .conftest import PAYMENT_ID, TOKEN, URL_PAYPHONE, FalsoPayphone, config_pruebas


def _adaptador(handler) -> AdaptadorPayphone:
    return AdaptadorPayphone(config_pruebas(), httpx.Client(transport=httpx.MockTransport(handler)))


# ------------------------------------------------------------------ ConfigPagos

def test_response_url_desde_url_publica_sin_barra_final(tmp_path):
    cfg = ConfigPagos.desde_entorno(env={"ESERT_URL_PUBLICA": "https://demo.ejemplo.test/"},
                                    archivo=tmp_path / "no-existe.env")
    assert cfg.response_url == "https://demo.ejemplo.test/api/v1/pagos/retorno"


def test_payphone_response_url_tiene_prioridad(tmp_path):
    cfg = ConfigPagos.desde_entorno(env={"ESERT_URL_PUBLICA": "https://demo.ejemplo.test",
                                         "PAYPHONE_RESPONSE_URL": "https://otra.test/vuelta"},
                                    archivo=tmp_path / "no-existe.env")
    assert cfg.response_url == "https://otra.test/vuelta"


def test_modo_invalido_lanza_value_error(tmp_path):
    with pytest.raises(ValueError):
        ConfigPagos.desde_entorno(env={"PAYPHONE_MODO": "produccion"}, archivo=tmp_path / "no-existe.env")


def test_faltantes_en_modo_pruebas(tmp_path):
    cfg = ConfigPagos.desde_entorno(env={"PAYPHONE_MODO": "pruebas"}, archivo=tmp_path / "no-existe.env")
    assert cfg.faltantes() == ["PAYPHONE_TOKEN", "PAYPHONE_STORE_ID"]
    cfg2 = ConfigPagos.desde_entorno(env={"PAYPHONE_MODO": "pruebas", "PAYPHONE_TOKEN": "x"},
                                     archivo=tmp_path / "no-existe.env")
    assert cfg2.faltantes() == ["PAYPHONE_STORE_ID"]
    assert config_pruebas().faltantes() == []
    assert ConfigPagos(modo="mock").faltantes() == []


def test_repr_de_config_no_muestra_el_token():
    assert TOKEN not in repr(config_pruebas())


def test_centavos_redondea():
    assert centavos(7.5) == 750
    assert centavos(0.29) == 29  # 0.29 * 100 = 28.999… en binario


# ------------------------------------------------------------------ Prepare

def test_prepare_envia_cuerpo_y_cabeceras_correctas():
    falso = FalsoPayphone()
    resultado = _adaptador(falso).preparar(7.50, "rec_abc", "Recarga e-sert 7.50 USD")

    pedido = falso.pedidos[0]
    assert pedido.method == "POST"
    assert str(pedido.url) == f"{URL_PAYPHONE}/api/button/Prepare"
    assert pedido.headers["Authorization"] == f"Bearer {TOKEN}"
    cuerpo = json.loads(pedido.content)
    assert cuerpo["amount"] == 750
    assert cuerpo["amountWithoutTax"] == cuerpo["amount"]
    assert cuerpo["currency"] == "USD"
    assert cuerpo["clientTransactionId"] == "rec_abc"
    assert cuerpo["storeId"] == "store-1"
    assert cuerpo["responseUrl"] == "https://demo.ejemplo.test/api/v1/pagos/retorno"
    assert resultado == {"payment_id": PAYMENT_ID,
                         "pay_url": "https://pay.payphonetodoesposible.com/PayWithCard/abc"}


def test_prepare_sin_payment_id_es_error():
    adaptador = _adaptador(lambda r: httpx.Response(200, json={"payWithCard": "x"}))
    with pytest.raises(ErrorPayphone):
        adaptador.preparar(5, "rec_x", "ref")


# ------------------------------------------------------------------ Confirm

def test_confirm_aprobado():
    falso = FalsoPayphone()
    falso.monto_centavos = 750
    confirmado = _adaptador(falso).confirmar("123", "rec_abc")

    pedido = falso.pedidos[0]
    assert str(pedido.url) == f"{URL_PAYPHONE}/api/button/V2/Confirm"
    assert json.loads(pedido.content) == {"id": 123, "clientTxId": "rec_abc"}
    assert confirmado["aprobado"] is True
    assert confirmado["monto_usd"] == 7.5
    assert confirmado["client_transaction_id"] == "rec_abc"


def test_confirm_cancelado():
    falso = FalsoPayphone()
    falso.monto_centavos, falso.status_code, falso.transaction_status = 750, 2, "Canceled"
    assert _adaptador(falso).confirmar("123", "rec_abc")["aprobado"] is False


def test_confirm_http_4xx_es_error_payphone():
    adaptador = _adaptador(lambda r: httpx.Response(401, json={"errorCode": 401, "message": "No autorizado"}))
    with pytest.raises(ErrorPayphone, match="401"):
        adaptador.confirmar("123", "rec_abc")


def test_confirm_error_de_red_es_error_payphone():
    def sin_red(pedido):
        raise httpx.ConnectError("sin red", request=pedido)

    with pytest.raises(ErrorPayphone):
        _adaptador(sin_red).confirmar("123", "rec_abc")


def test_confirm_id_no_numerico_es_error():
    with pytest.raises(ErrorPayphone):
        _adaptador(FalsoPayphone()).confirmar("abc", "rec_abc")
