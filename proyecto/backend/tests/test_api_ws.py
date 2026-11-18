"""WebSocket `/ws/estado`, cola de publicación y rutas 🔒 del controlador TraCI.

`receive_json` bloquea: cada test termina leyendo hasta un mensaje centinela (un paso o un
KPI publicado al final), así un mensaje de más se detecta y uno de menos no cuelga el test
más que hasta el centinela.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.main import Config, crear_app
from backend.api.ws import GestorConexiones
from comun import esquemas as e

EJEMPLO = json.loads((Path(__file__).resolve().parents[2] / "comun" / "ejemplos" / "sim_paso.json")
                     .read_text(encoding="utf-8"))
TOKEN = "secreto"


def paso(t_sim: float) -> dict:
    """El paso de ejemplo con otro `t_sim`."""
    return {**EJEMPLO, "t_sim": t_sim}


def kpi(t_sim: float = 999.0) -> e.MensajeKpi:
    return e.MensajeKpi(t_sim=t_sim, ts="2026-10-20T14:03:05Z", valores={"precision_mapa": 0.9})


def esperar(cond, timeout: float = 2.0) -> None:
    """Espera activa a que `cond()` sea verdadera (el registro del WS es asíncrono)."""
    fin = time.monotonic() + timeout
    while not cond():
        assert time.monotonic() < fin, "tiempo agotado esperando la condición"
        time.sleep(0.01)


def leer_hasta(ws, es_centinela, maximo: int = 50) -> list:
    """Lee mensajes validados hasta el centinela (incluido)."""
    recibidos = []
    for _ in range(maximo):
        m = e.leer_mensaje_ws(ws.receive_text())
        recibidos.append(m)
        if es_centinela(m):
            return recibidos
    pytest.fail(f"sin centinela tras {maximo} mensajes")


@pytest.fixture
def app():
    return crear_app(Config(db_url="sqlite:///:memory:"))


@pytest.fixture
def app_token():
    return crear_app(Config(db_url="sqlite:///:memory:", token_sim=TOKEN))


def conectar(c, app, ruta="/ws/estado", n=1):
    """Abre el WS y espera a que el gestor lo tenga registrado."""
    ws = c.websocket_connect(ruta)
    ws.__enter__()
    esperar(lambda: len(app.state.servicios.gestor.clientes) >= n)
    return ws


# ---------------------------------------------------------------------------- difusión


def test_snapshot_y_verdad_tras_paso(app):
    with TestClient(app) as c:
        ws = conectar(c, app)
        try:
            assert c.post("/api/v1/sim/paso", json=EJEMPLO).status_code == 202
            snap = e.leer_mensaje_ws(ws.receive_text())
            verdad = e.leer_mensaje_ws(ws.receive_text())
        finally:
            ws.__exit__(None, None, None)
    assert isinstance(snap, e.MensajeSnapshot) and isinstance(verdad, e.MensajeVerdad)
    assert snap.t_sim == verdad.t_sim == 1234.0
    assert [v.id for v in snap.vehiculos] == ["sim_veh42", "sim_veh7"]
    # snapshot.puestos sale del mapa del sistema (nada ocupado al inicio), no de la verdad
    mapa = app.state.servicios.mapa
    assert len(snap.puestos) == len(mapa.puestos) > 2
    assert all(p.ocupados == 0 for p in snap.puestos)
    assert {p.puesto_id: p.ocupados for p in verdad.puestos} == {"pa_-106945247#0_0": 9, "pa_-118367899_0": 7}
    assert verdad.estacionados == ["sim_veh7"]


def test_limite_un_paso_por_segundo(app):
    with TestClient(app) as c:
        ws = conectar(c, app, "/ws/estado?rol=publico")
        try:
            for t in (100.0, 100.4, 100.9, 101.0, 200.0, 50.0):  # 50 < 200: corrida nueva
                assert c.post("/api/v1/sim/paso", json=paso(t)).status_code == 202
            msgs = leer_hasta(ws, lambda m: m.t_sim == 50.0)
        finally:
            ws.__exit__(None, None, None)
    assert all(isinstance(m, e.MensajeSnapshot) for m in msgs)
    assert [m.t_sim for m in msgs] == [100.0, 101.0, 200.0, 50.0]


def test_publico_nunca_recibe_verdad(app):
    with TestClient(app) as c:
        publico = conectar(c, app, "/ws/estado?rol=publico", n=1)
        sin_verdad = conectar(c, app, "/ws/estado?rol=visor&verdad=0", n=2)
        visor = conectar(c, app, "/ws/estado", n=3)
        try:
            c.post("/api/v1/sim/paso", json=EJEMPLO)
            app.state.servicios.publicar_snapshot(kpi())  # centinela, detrás en la cola
            tipos = {nombre: [m.tipo for m in leer_hasta(ws, lambda m: m.tipo == "kpi")]
                     for nombre, ws in (("publico", publico), ("sin_verdad", sin_verdad), ("visor", visor))}
        finally:
            for ws in (publico, sin_verdad, visor):
                ws.__exit__(None, None, None)
    assert tipos["publico"] == ["snapshot", "kpi"]
    assert tipos["sin_verdad"] == ["snapshot", "kpi"]
    assert tipos["visor"] == ["snapshot", "verdad", "kpi"]


def test_publicar_en_proceso_desde_otro_hilo(app):
    with TestClient(app) as c:
        ws = conectar(c, app)
        try:
            s = app.state.servicios
            hilo = threading.Thread(target=lambda: (s.publicar_snapshot(e.PasoSimulacion.model_validate(EJEMPLO)),
                                                    s.publicar_snapshot(kpi(1234.0))))
            hilo.start()
            hilo.join(2)
            msgs = leer_hasta(ws, lambda m: m.tipo == "kpi")
        finally:
            ws.__exit__(None, None, None)
    assert [m.tipo for m in msgs] == ["snapshot", "verdad", "kpi"]
    assert msgs[2] == kpi(1234.0)  # el KPI llega tal cual


# ---------------------------------------------------------------------------- token


def test_interno_snapshot_exige_token(app_token):
    with TestClient(app_token) as c:
        ws = conectar(c, app_token, "/ws/estado?rol=publico")
        try:
            r = c.post("/api/v1/interno/snapshot", json=EJEMPLO)
            assert r.status_code == 401
            assert r.json()["error"]["codigo"] == "TOKEN_SIM_INVALIDO"
            r = c.post("/api/v1/interno/snapshot", json=EJEMPLO, headers={"Authorization": "Bearer otro"})
            assert r.status_code == 401
            assert c.post("/api/v1/interno/snapshot", json=EJEMPLO,
                          headers={"X-Sim-Token": "otro"}).status_code == 401
            r = c.post("/api/v1/interno/snapshot", json=EJEMPLO, headers={"Authorization": f"Bearer {TOKEN}"})
            assert r.status_code == 202 and r.json() == {"aceptado": True, "espejos": [], "ordenes": []}
            snap = e.leer_mensaje_ws(ws.receive_text())
            assert isinstance(snap, e.MensajeSnapshot) and snap.t_sim == 1234.0
            r = c.post("/api/v1/interno/snapshot", json=paso(1300.0), headers={"X-Sim-Token": TOKEN})
            assert r.status_code == 202
            assert e.leer_mensaje_ws(ws.receive_text()).t_sim == 1300.0
        finally:
            ws.__exit__(None, None, None)


def test_sim_paso_sin_token_401(app_token):
    with TestClient(app_token) as c:
        r = c.post("/api/v1/sim/paso", json=EJEMPLO)
        assert r.status_code == 401
        assert r.json()["error"]["codigo"] == "TOKEN_SIM_INVALIDO"
        assert app_token.state.servicios.mundo.t_sim is None  # el paso rechazado no se aplica
        assert c.post("/api/v1/sim/paso", json=EJEMPLO, headers={"X-Sim-Token": TOKEN}).status_code == 202


# ---------------------------------------------------------------------------- gestor


class WsFalso:
    """Imita un `WebSocket`: guarda lo enviado o falla si está caído."""

    def __init__(self, caido: bool = False):
        self.caido = caido
        self.enviados: list = []

    async def send_text(self, texto: str) -> None:
        if self.caido:
            raise ConnectionError("cliente caído")
        self.enviados.append(texto)


def test_gestor_descarta_caidos_y_filtra_verdad():
    async def caso():
        g = GestorConexiones()
        vivo, caido, publico = WsFalso(), WsFalso(caido=True), WsFalso()
        g.clientes = {vivo: True, caido: True, publico: False}
        verdad = e.MensajeVerdad(t_sim=1.0, ts="2026-10-20T14:03:05Z", puestos=[])
        assert await g.difundir(verdad) == 1  # el público no la pide, el caído falla
        assert caido not in g.clientes and set(g.clientes) == {vivo, publico}
        assert publico.enviados == []
        assert await g.difundir(kpi()) == 2
        assert len(vivo.enviados) == 2 and len(publico.enviados) == 1

    asyncio.run(caso())


def test_publicar_antes_de_iniciar_no_falla():
    g = GestorConexiones()
    g.publicar(kpi())  # sin bucle: se descarta
    assert g.cola is None


def test_desconectar_saca_al_cliente(app):
    with TestClient(app) as c:
        with c.websocket_connect("/ws/estado"):
            esperar(lambda: len(app.state.servicios.gestor.clientes) == 1)
        esperar(lambda: len(app.state.servicios.gestor.clientes) == 0)


# ---------------------------------------------------------------------------- espejo y salud


def test_candidatos_espejo_y_salud(app):
    with TestClient(app) as c:
        assert c.get("/salud").json()["t_sim"] is None
        assert c.get("/api/v1/espejo/candidatos").json() == []
        c.post("/api/v1/sim/paso", json=EJEMPLO)
        assert c.get("/api/v1/espejo/candidatos").json() == [
            {"id": "sim_veh42", "destino_nombre": "Parque Calderón", "estado": "GUIADO", "t_sim": 1234.0}]
        assert {k: v for k, v in c.get("/salud").json().items() if k != "ts"} == {"ok": True, "contrato": 1, "t_sim": 1234.0}


def test_sim_kpi_difunde_y_exige_token(app_token):
    """S3-1: `POST /sim/kpi` (🔒) difunde el mensaje `kpi` de `KPIsSistema` por `/ws/estado`."""
    cuerpo = kpi(1240.0).model_dump(mode="json")
    with TestClient(app_token) as c:
        assert c.post("/api/v1/sim/kpi", json=cuerpo).status_code == 401
        ws = conectar(c, app_token, ruta="/ws/estado?rol=publico")
        try:
            r = c.post("/api/v1/sim/kpi", json=cuerpo, headers={"X-Sim-Token": TOKEN})
            assert r.status_code == 202
            m = e.leer_mensaje_ws(ws.receive_text())
        finally:
            ws.__exit__(None, None, None)
    assert isinstance(m, e.MensajeKpi) and m.t_sim == 1240.0 and m.valores == {"precision_mapa": 0.9}
