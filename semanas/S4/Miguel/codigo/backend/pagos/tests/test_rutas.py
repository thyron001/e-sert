"""Pruebas de las rutas /api/v1/pagos/* sobre la app de Freddy, sin Payphone real."""

from __future__ import annotations

import logging
import re
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select

from backend.pagos.intenciones import IntencionPago

from .conftest import TOKEN, nuevo_usuario

API = "/api/v1"
PATRON_CTID = re.compile(r"^rec_[0-9a-f-]{36}$")


def preparar(cliente, usuario, monto, **extra):
    return cliente.post(f"{API}/pagos/preparar", json={"usuario_id": usuario, "monto": monto, **extra})


def billetera(cliente, usuario):
    r = cliente.get(f"{API}/billetera/{usuario}")
    assert r.status_code == 200, r.text
    return r.json()


def retorno(cliente, ctid, pid=None):
    params = {"clientTransactionId": ctid}
    if pid is not None:
        params["id"] = pid
    return cliente.get(f"{API}/pagos/retorno", params=params)


def estado_de(cliente, ctid):
    r = cliente.get(f"{API}/pagos/{ctid}")
    assert r.status_code == 200, r.text
    return r.json()


def intenciones_guardadas(cliente):
    """Filas de la tabla intenciones_pago (lectura directa de la base de la app)."""
    with cliente.app.state.servicios.bd.transaccion() as s:
        return list(s.scalars(select(IntencionPago)).all())


def recargas(datos):
    return [m for m in datos["movimientos"] if m["tipo"] == "recarga"]


# ------------------------------------------------------------------ preparar

def test_recarga_menor_al_minimo_da_422_sin_intencion_ni_credito(cliente, falso):
    u = nuevo_usuario()
    r = preparar(cliente, u, 4.99)
    assert r.status_code == 422
    assert r.json()["error"]["codigo"] == "RECARGA_MINIMA"
    assert falso.pedidos == []  # ni siquiera se llamó a Payphone
    assert intenciones_guardadas(cliente) == []
    assert billetera(cliente, u)["saldo"] == 0
    assert recargas(billetera(cliente, u)) == []


def test_preparar_5_usd_crea_intencion_pendiente(cliente):
    r = preparar(cliente, nuevo_usuario(), 5)
    assert r.status_code == 201, r.text
    datos = r.json()
    ctid = datos["client_transaction_id"]
    assert PATRON_CTID.match(ctid)
    assert datos["pay_url"] == f"https://demo.ejemplo.test/api/v1/pagos/ir/{ctid}"
    assert datos["modo"] == "pruebas"
    assert estado_de(cliente, ctid)["estado"] == "pendiente"


def test_url_app_invalida_da_422(cliente):
    r = preparar(cliente, nuevo_usuario(), 5, url_app="https://evil.test")
    assert r.status_code == 422


# ------------------------------------------------------------------ idempotencia

def test_retorno_repetido_acredita_una_sola_vez(cliente, falso):
    u = nuevo_usuario()
    datos = preparar(cliente, u, 7.5).json()
    ctid, pid = datos["client_transaction_id"], datos["payment_id"]

    for _ in range(3):
        assert retorno(cliente, ctid, pid).status_code == 200

    b = billetera(cliente, u)
    assert b["saldo"] == 7.5
    rec = recargas(b)
    assert len(rec) == 1
    assert rec[0]["referencia_payphone"] == pid
    assert estado_de(cliente, ctid)["estado"] == "aprobado"
    assert falso.llamadas_confirm == 1


def test_idempotencia_con_adaptador_mock(cliente_mock):
    u = nuevo_usuario()
    datos = preparar(cliente_mock, u, 6).json()
    ctid, pid = datos["client_transaction_id"], datos["payment_id"]
    assert datos["modo"] == "mock"

    for _ in range(3):
        r = cliente_mock.get(f"{API}/pagos/mock/decidir",
                             params={"id": pid, "clientTransactionId": ctid, "decision": "aprobar"},
                             follow_redirects=True)
        assert r.status_code == 200
        assert "Pago confirmado" in r.text

    b = billetera(cliente_mock, u)
    assert b["saldo"] == 6.0
    assert len(recargas(b)) == 1
    assert estado_de(cliente_mock, ctid)["estado"] == "aprobado"


# ------------------------------------------------------------------ rechazos y fallos

def test_pago_rechazado_no_acredita_ni_despues(cliente, falso):
    u = nuevo_usuario()
    datos = preparar(cliente, u, 5).json()
    ctid, pid = datos["client_transaction_id"], datos["payment_id"]
    falso.status_code, falso.transaction_status = 2, "Canceled"
    assert "Pago no realizado" in retorno(cliente, ctid, pid).text
    assert estado_de(cliente, ctid)["estado"] == "rechazado"

    # Aunque Payphone ahora dijera "aprobado", la intención ya está cerrada.
    falso.status_code, falso.transaction_status = 3, "Approved"
    retorno(cliente, ctid, pid)
    assert estado_de(cliente, ctid)["estado"] == "rechazado"
    assert billetera(cliente, u)["saldo"] == 0
    assert falso.llamadas_confirm == 1


def test_cancelacion_sin_id_rechaza(cliente, falso):
    u = nuevo_usuario()
    ctid = preparar(cliente, u, 5).json()["client_transaction_id"]
    assert retorno(cliente, ctid).status_code == 200
    assert estado_de(cliente, ctid)["estado"] == "rechazado"
    assert falso.llamadas_confirm == 0
    assert billetera(cliente, u)["saldo"] == 0


def test_error_de_red_en_confirm_deja_pendiente_y_luego_acredita(cliente, falso):
    u = nuevo_usuario()
    datos = preparar(cliente, u, 5).json()
    ctid, pid = datos["client_transaction_id"], datos["payment_id"]

    falso.fallo_red_confirm = True
    r = retorno(cliente, ctid, pid)
    assert r.status_code == 200 and "Pago en revisión" in r.text
    assert estado_de(cliente, ctid)["estado"] == "pendiente"
    assert billetera(cliente, u)["saldo"] == 0

    falso.fallo_red_confirm = False
    retorno(cliente, ctid, pid)
    retorno(cliente, ctid, pid)
    assert estado_de(cliente, ctid)["estado"] == "aprobado"
    b = billetera(cliente, u)
    assert b["saldo"] == 5.0 and len(recargas(b)) == 1
    assert falso.llamadas_confirm == 2  # el fallido y el que aprobó


def test_aprobado_con_monto_distinto_no_acredita(cliente, falso):
    u = nuevo_usuario()
    datos = preparar(cliente, u, 5).json()
    falso.monto_centavos = 100  # Payphone dice que cobró $1.00
    retorno(cliente, datos["client_transaction_id"], datos["payment_id"])
    assert estado_de(cliente, datos["client_transaction_id"])["estado"] == "rechazado"
    assert billetera(cliente, u)["saldo"] == 0


def test_aprobado_con_otro_client_transaction_id_no_acredita(cliente, falso):
    u = nuevo_usuario()
    datos = preparar(cliente, u, 5).json()
    falso.ctid_respuesta = "rec_de-otra-persona"
    retorno(cliente, datos["client_transaction_id"], datos["payment_id"])
    assert billetera(cliente, u)["saldo"] == 0


def test_preparar_con_payphone_caido_da_error_y_rechaza(cliente, falso):
    falso.fallo_red_prepare = True
    r = preparar(cliente, nuevo_usuario(), 5)
    assert r.status_code >= 500
    assert r.json()["error"]["codigo"] == "ERROR_INTERNO"
    assert [i.estado for i in intenciones_guardadas(cliente)] == ["rechazado"]


# ------------------------------------------------------------------ token fuera de los logs

def test_token_nunca_aparece_en_logs(cliente, falso, caplog):
    caplog.set_level(logging.DEBUG)
    u = nuevo_usuario()
    datos = preparar(cliente, u, 5).json()
    retorno(cliente, datos["client_transaction_id"], datos["payment_id"])
    # Camino de error: Confirm responde 4xx con cuerpo.
    datos2 = preparar(cliente, u, 5).json()
    falso.http_status_confirm = 400
    retorno(cliente, datos2["client_transaction_id"], datos2["payment_id"])

    assert caplog.records, "se esperaban registros de log"
    assert any("respondió 400" in r.getMessage() for r in caplog.records)
    assert TOKEN not in caplog.text
    for registro in caplog.records:
        assert TOKEN not in registro.getMessage()
        assert TOKEN not in str(registro.args)


# ------------------------------------------------------------------ saldo cuadra con Freddy

def test_saldo_cuadra_tras_recarga_de_10(cliente):
    u = nuevo_usuario()
    datos = preparar(cliente, u, 10).json()
    retorno(cliente, datos["client_transaction_id"], datos["payment_id"])
    b = billetera(cliente, u)
    assert b["saldo"] == 10.0
    assert b["disponible"] == 10.0
    assert b["retenido"] == 0
    assert b["bloqueada"] is False
    suma = (sum(m["monto"] for m in b["movimientos"] if m["tipo"] == "recarga")
            - sum(m["monto"] for m in b["movimientos"] if m["tipo"] == "debito"))
    assert b["saldo"] == pytest.approx(suma)


# ------------------------------------------------------------------ desconocidos y HTML de retorno

def test_retorno_de_ctid_desconocido_muestra_pagina(cliente):
    r = retorno(cliente, "rec_no-existe", "123")
    assert r.status_code == 200
    assert "Pago no encontrado" in r.text


def test_consultar_ctid_desconocido_da_404(cliente):
    assert cliente.get(f"{API}/pagos/rec_nope").status_code == 404


def test_html_de_retorno_aprobado_redirige_a_la_app(cliente):
    url_app = "exp://192.168.3.168:8081/--/pagos/retorno"
    datos = preparar(cliente, nuevo_usuario(), 5, url_app=url_app).json()
    ctid = datos["client_transaction_id"]
    r = retorno(cliente, ctid, datos["payment_id"])
    assert "Pago confirmado" in r.text
    href = re.search(r'id="volver" href="([^"]+)"', r.text).group(1).replace("&amp;", "&")
    assert href.startswith(url_app + "?")
    q = parse_qs(urlparse(href).query)
    assert q["clientTransactionId"] == [ctid]
    assert q["estado"] == ["aprobado"]


def test_html_de_retorno_en_android_usa_intent(cliente):
    """Chrome/Brave en Android no abren exp:// desde un enlace: se ofrece intent://."""
    url_app = "exp://100.85.244.14:8081/--/pagos/retorno"
    datos = preparar(cliente, nuevo_usuario(), 5, url_app=url_app).json()
    ctid = datos["client_transaction_id"]
    r = cliente.get(f"{API}/pagos/retorno", params={"id": datos["payment_id"], "clientTransactionId": ctid},
                    headers={"User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/130 Mobile"})
    href = re.search(r'id="volver" href="([^"]+)"', r.text).group(1).replace("&amp;", "&")
    assert href.startswith("intent://100.85.244.14:8081/--/pagos/retorno?")
    assert href.endswith("#Intent;scheme=exp;end")
    assert f"clientTransactionId={ctid}" in href
