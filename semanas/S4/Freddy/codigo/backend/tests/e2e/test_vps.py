"""Prueba de humo de la demo en línea (`pytest -m vps`; opcional en CI).

URL por `ESERT_URL_PUBLICA` (por defecto `https://demo.e-sert.tesisucuenca.com`). Solo lee y
manda un snapshot **sin token y con cuerpo inválido**: con token configurado, el backend responde
401 antes de validar; si respondiera 422 es que la ruta está abierta (sin `ESERT_TOKEN_SIM`). En
ningún caso se escribe estado en la demo. Si la URL no
responde, las pruebas quedan omitidas con el motivo.
"""

from __future__ import annotations

import os
import time

import httpx
import pytest
from websockets.sync.client import connect

from comun import esquemas as e

pytestmark = pytest.mark.vps

URL = os.environ.get("ESERT_URL_PUBLICA", "https://demo.e-sert.tesisucuenca.com").rstrip("/")
CONTRATO = {"X-Contrato-Version": "1"}


@pytest.fixture(scope="module")
def vps():
    try:
        r = httpx.get(f"{URL}/salud", timeout=10)
    except httpx.HTTPError as err:
        pytest.skip(f"VPS no accesible en {URL}: {err!r}")
    if r.status_code >= 500 or r.status_code in (404, 502, 503):
        pytest.skip(f"VPS no accesible en {URL}: HTTP {r.status_code}")
    with httpx.Client(base_url=URL, headers=CONTRATO, timeout=10) as c:
        yield c


def test_salud(vps):
    r = vps.get("/salud")
    assert r.status_code == 200 and r.json()["ok"] is True and r.json()["contrato"] == 1, r.text
    assert vps.get("/api/v1/salud").status_code == 200


def test_puestos(vps):
    r = vps.get("/api/v1/puestos")
    assert r.status_code == 200 and r.headers["x-contrato-version"] == "1"
    puestos = r.json()
    assert puestos and all(0 <= p["ocupados"] <= p["capacidad"] for p in puestos)
    e.Puesto.model_validate(puestos[0])


def test_candidatos_espejo(vps):
    r = vps.get("/api/v1/espejo/candidatos")
    assert r.status_code == 200 and isinstance(r.json(), list), r.text


def test_ws_estado_5_s(vps):
    """La conexión WS se mantiene 5 s; todo lo que llegue (si hay simulación) es válido y sin `verdad`."""
    url_ws = URL.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    recibidos = []
    with connect(f"{url_ws}/ws/estado?rol=publico", open_timeout=10) as ws:
        fin = time.monotonic() + 5
        while (resta := fin - time.monotonic()) > 0:
            try:
                recibidos.append(e.leer_mensaje_ws(ws.recv(timeout=resta)))
            except TimeoutError:
                break
    assert all(m.tipo != "verdad" for m in recibidos)


@pytest.mark.parametrize("ruta", ["/api/v1/interno/snapshot", "/api/v1/sim/paso"])
def test_snapshot_sin_token_rechazado(vps, ruta):
    r = vps.post(ruta, json={"sonda_e2e": True})  # inválido a propósito: nunca cambia el estado
    assert r.status_code == 401, (f"{ruta} no exige token (HTTP {r.status_code}, "
                                  f"{r.json().get('error', {}).get('codigo')}): falta ESERT_TOKEN_SIM en el VPS")
    assert r.json()["error"]["codigo"] == "TOKEN_SIM_INVALIDO"
