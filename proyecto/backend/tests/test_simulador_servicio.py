"""Servicio `sim` (`backend/simulador/servicio.py`) y su cliente en el backend (`cliente.py`).

El cliente se prueba contra el servicio real en memoria (TestClient es un `httpx.Client`), y el
backend completo contra ese cliente: visor → `/api/v1/demo/*` → cliente → servicio → gestor.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.api.main import Config, crear_app
from backend.simulador.cliente import ClienteSimulacion
from backend.simulador.gestor import Escenario, GestorSimulacion
from backend.simulador.servicio import crear_app as crear_servicio
from backend.tests.test_simulador import Lanzador, esperar, proyecto_falso

TOKEN = "token-sim"
CLAVE = "clave-de-prueba"


@pytest.fixture
def servicio(tmp_path, monkeypatch):
    monkeypatch.setenv("SUMO_HOME", "/usr/share/sumo")
    lanz = Lanzador()
    g = GestorSimulacion("http://api:8000", TOKEN, proyecto=proyecto_falso(tmp_path / "p"),
                         python="python3", dir_logs=tmp_path / "logs", lanzar=lanz)
    with TestClient(crear_servicio(g, token=TOKEN)) as c:
        yield c, g, lanz
    if g.corriendo():
        g.detener(espera_s=2)


def bearer(t=TOKEN):
    return {"Authorization": f"Bearer {t}"}


def test_salud_sin_token(servicio):
    c, _, _ = servicio
    assert c.get("/salud").json()["ok"] is True


@pytest.mark.parametrize("cab", [{}, {"Authorization": "Bearer otro"}])
def test_rutas_exigen_token(servicio, cab):
    c, _, lanz = servicio
    assert c.get("/estado", headers=cab).status_code == 401
    assert c.post("/iniciar", headers=cab).status_code == 401
    assert lanz.comandos == []


def test_iniciar_publica_en_el_backend_y_409_si_ya_corre(servicio):
    c, g, lanz = servicio
    r = c.post("/iniciar", headers=bearer(), json={"penetracion": 50, "semilla": 2, "ritmo": 1})
    assert r.status_code == 202 and r.json()["escenario"]["id"] == "p50_rf_s2"
    assert esperar(lambda: g.estado().fase == "corriendo")
    cmd = lanz.comandos[0]
    assert cmd[cmd.index("--publicar") + 1] == "http://api:8000"
    assert c.post("/iniciar", headers=bearer()).status_code == 409
    d = c.post("/detener", headers=bearer()).json()
    assert d["fase"] == "inactiva" and d["codigo_salida"] == -2


def test_parametro_desconocido_422(servicio):
    c, _, _ = servicio
    assert c.post("/iniciar", headers=bearer(), json={"color": "rojo"}).status_code == 422


def test_cliente_contra_el_servicio(servicio):
    c, g, _ = servicio
    cli = ClienteSimulacion("http://sim:8100", TOKEN, http=c)
    assert cli.estado().fase == "inactiva"
    est = cli.iniciar(Escenario(penetracion=50, ritmo=1.0))
    assert est.escenario.id == "p50_rf_s2"
    assert esperar(lambda: g.estado().fase == "corriendo")
    with pytest.raises(RuntimeError):
        cli.iniciar(Escenario())
    assert cli.detener().fase == "inactiva"


def test_cliente_sin_servicio_no_disponible():
    def caido(_req):
        raise httpx.ConnectError("no hay nadie")
    cli = ClienteSimulacion("http://sim:8100", TOKEN,
                            http=httpx.Client(base_url="http://sim:8100", transport=httpx.MockTransport(caido)))
    est = cli.estado()
    assert est.disponible is False and "no responde" in est.motivo
    with pytest.raises(LookupError):
        cli.iniciar(Escenario())


def test_backend_completo_con_servicio_remoto(servicio):
    c, g, _ = servicio
    app = crear_app(Config(db_url="sqlite:///:memory:", clave_demo=CLAVE))
    app.state.simulador = ClienteSimulacion("http://sim:8100", TOKEN, http=c)
    with TestClient(app) as api:
        assert api.get("/api/v1/demo/estado").json()["disponible"] is True
        r = api.post("/api/v1/demo/iniciar", headers={"X-Clave-Demo": CLAVE}, json={"ritmo": 1})
        assert r.status_code == 202
        assert esperar(lambda: g.estado().fase == "corriendo")
        assert api.post("/api/v1/demo/iniciar", headers={"X-Clave-Demo": CLAVE}).json()["error"]["codigo"] == "DEMO_EN_CURSO"
        d = api.post("/api/v1/demo/detener", headers={"X-Clave-Demo": CLAVE}).json()
    assert d["fase"] == "inactiva"


def test_backend_con_servicio_caido_responde_503():
    def caido(_req):
        raise httpx.ConnectError("no hay nadie")
    app = crear_app(Config(db_url="sqlite:///:memory:", clave_demo=CLAVE))
    app.state.simulador = ClienteSimulacion(
        "http://sim:8100", TOKEN, http=httpx.Client(base_url="http://sim:8100", transport=httpx.MockTransport(caido)))
    with TestClient(app) as api:
        est = api.get("/api/v1/demo/estado").json()
        r = api.post("/api/v1/demo/iniciar", headers={"X-Clave-Demo": CLAVE})
        r2 = api.post("/api/v1/demo/detener", headers={"X-Clave-Demo": CLAVE})
    assert est["disponible"] is False
    assert r.status_code == 503 and r.json()["error"]["codigo"] == "DEMO_NO_DISPONIBLE"
    assert r2.status_code == 503
