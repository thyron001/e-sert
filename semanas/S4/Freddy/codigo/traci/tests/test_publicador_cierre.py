"""Regresión S4-3: al cerrar el `Publicador`, el hilo no usa el cliente HTTP ya cerrado.

En la prueba en línea contra el VPS (S3-3, 1 500 s a ritmo 1) el último POST cayó con
`RuntimeError: Cannot send a request, as the client has been closed.` en el hilo `publicador`.
"""
from __future__ import annotations

import threading
import time

import httpx

from traci.puente_nucleo import Publicador


def _lento(request):
    time.sleep(0.3)
    return httpx.Response(202, json={"aceptado": True})


def test_cerrar_espera_el_envio_en_curso_y_no_rompe_el_hilo(monkeypatch):
    errores = []
    monkeypatch.setattr(threading, "excepthook", lambda a: errores.append(a.exc_value))
    pub = Publicador("http://backend.invalido", reintentos=1, backoff_s=0.01)
    pub._cliente = httpx.Client(base_url="http://backend.invalido", transport=httpx.MockTransport(_lento))
    for i in range(5):
        pub.publicar({"t_sim": float(i)})
        time.sleep(0.05)
    pub.cerrar(espera_s=2.0)
    assert not pub._hilo.is_alive()
    assert errores == []
    assert pub.enviados >= 1
    assert pub.enviados + pub.descartados + pub.fallidos <= 5


def test_cerrar_con_backend_caido_no_cuelga():
    pub = Publicador("http://127.0.0.1:9", reintentos=2, backoff_s=0.01, timeout_s=0.2)
    pub.publicar({"t_sim": 1.0})
    t0 = time.monotonic()
    pub.cerrar(espera_s=0.5)
    assert time.monotonic() - t0 < 2.5
    assert not pub._hilo.is_alive()
