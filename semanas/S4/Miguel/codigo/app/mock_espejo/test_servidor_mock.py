# MOCK: pruebas del servidor mock del modo espejo (reemplazar junto con servidor_mock.py)
"""Pruebas del mock del modo espejo.

La mayoría usa un reloj falso (`RelojFalso`): `dormir` avanza el reloj en vez de esperar,
así la reproducción es determinista e instantánea. Una prueba usa el reloj real con un
intervalo de 0.01 s.
"""

from __future__ import annotations

import asyncio
import re

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from servidor_mock import CODIGO_CORTE, cargar_recorrido, crear_app

ISO_MS_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
MENSAJES, FIN = cargar_recorrido()
N = len(MENSAJES)


class RelojFalso:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def avanzar(self, s: float) -> None:
        self.t += s

    async def dormir(self, s: float) -> None:
        self.t += s
        await asyncio.sleep(0)


def cliente_falso(**kw) -> tuple[TestClient, RelojFalso]:
    r = RelojFalso()
    app = crear_app(reloj=r, dormir=r.dormir, intervalo_s=1.0, **kw)
    return TestClient(app), r


def test_recorrido_tiene_59_mensajes_y_fin():
    assert N == 59
    assert FIN["motivo"] == "salio_simulacion"


def test_candidatos_tres_con_claves():
    c, _ = cliente_falso()
    r = c.get("/api/v1/espejo/candidatos")
    assert r.status_code == 200
    datos = r.json()
    assert [d["id"] for d in datos] == ["sim_veh42", "sim_veh17", "sim_veh63"]
    assert len({d["destino_nombre"] for d in datos}) == 3
    for d in datos:
        assert set(d) == {"id", "destino_nombre", "estado", "t_sim"}
        assert d["estado"] is None
        assert d["t_sim"] == MENSAJES[0]["t_sim"]


def test_reproduccion_completa():
    c, _ = cliente_falso()
    with c.websocket_connect("/ws/espejo/sim_veh17") as ws:
        recibidos = [ws.receive_json() for _ in range(N)]
        fin = ws.receive_json()
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
    assert exc.value.code == 1000
    for i, m in enumerate(recibidos):
        assert m["tipo"] == "espejo"
        assert m["veh_id"] == "sim_veh17"
        assert m["t_sim"] == MENSAJES[i]["t_sim"]
        assert m["estado"] == MENSAJES[i]["estado"]
        assert ISO_MS_Z.match(m["ts"]), m["ts"]
    assert fin["tipo"] == "espejo_fin"
    assert fin["veh_id"] == "sim_veh17"
    assert fin["motivo"] == "salio_simulacion"
    assert fin["t_sim"] == FIN["t_sim"]
    assert ISO_MS_Z.match(fin["ts"])
    # El candidato refleja el final; los demás siguen sin arrancar.
    cand = {d["id"]: d for d in c.get("/api/v1/espejo/candidatos").json()}
    assert cand["sim_veh17"]["estado"] == MENSAJES[-1]["estado"]
    assert cand["sim_veh42"]["estado"] is None


def test_reloj_real_intervalo_corto():
    c = TestClient(crear_app(intervalo_s=0.01))
    with c.websocket_connect("/ws/espejo/sim_veh63") as ws:
        recibidos = []
        while True:
            m = ws.receive_json()
            recibidos.append(m)
            if m["tipo"] == "espejo_fin":
                break
    espejos = recibidos[:-1]
    assert recibidos[-1]["motivo"] == "salio_simulacion"
    assert all(m["veh_id"] == "sim_veh63" for m in recibidos)
    t_sims = [m["t_sim"] for m in espejos]
    assert t_sims == sorted(t_sims) and len(set(t_sims)) == len(t_sims)
    assert len(espejos) >= N - 3  # en reloj real se toleran saltos por retrasos del planificador


def test_veh_desconocido_no_existe():
    c, _ = cliente_falso()
    with c.websocket_connect("/ws/espejo/sim_veh99") as ws:
        fin = ws.receive_json()
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
    assert fin == {"tipo": "espejo_fin", "veh_id": "sim_veh99", "t_sim": None, "ts": fin["ts"], "motivo": "no_existe"}
    assert ISO_MS_Z.match(fin["ts"])


def test_cortar_en_y_reconexion_retoma():
    c, reloj = cliente_falso(cortar_en=5)
    with c.websocket_connect("/ws/espejo/sim_veh42") as ws:
        primeros = [ws.receive_json() for _ in range(5)]
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
    assert exc.value.code == CODIGO_CORTE
    assert all(m["tipo"] == "espejo" for m in primeros)
    assert [m["t_sim"] for m in primeros] == [m["t_sim"] for m in MENSAJES[:5]]
    reloj.avanzar(3)  # el cliente estuvo 3 s sin conexión; el vehículo siguió avanzando
    with c.websocket_connect("/ws/espejo/sim_veh42") as ws:
        m = ws.receive_json()
    i = next(j for j, r in enumerate(MENSAJES) if r["t_sim"] == m["t_sim"])
    assert i == 8 and i > 4


def test_bucle_sin_espejo_fin():
    c, _ = cliente_falso(bucle=True)
    with c.websocket_connect("/ws/espejo/sim_veh42") as ws:
        recibidos = [ws.receive_json() for _ in range(2 * N + 10)]
    assert all(m["tipo"] == "espejo" for m in recibidos)
    assert recibidos[N]["t_sim"] == MENSAJES[0]["t_sim"]
    assert recibidos[2 * N + 5]["t_sim"] == MENSAJES[5]["t_sim"]


def test_reiniciar_relojes():
    c, reloj = cliente_falso()
    with c.websocket_connect("/ws/espejo/sim_veh42") as ws:
        ws.receive_json()
    # Con el reloj falso el servidor pudo avanzar unos pasos antes de notar el cierre:
    # se mide el avance relativo.
    t_sims = [m["t_sim"] for m in MENSAJES]
    cand = {d["id"]: d for d in c.get("/api/v1/espejo/candidatos").json()}
    i0 = t_sims.index(cand["sim_veh42"]["t_sim"])
    reloj.avanzar(10)
    cand = {d["id"]: d for d in c.get("/api/v1/espejo/candidatos").json()}
    assert cand["sim_veh42"]["t_sim"] == t_sims[min(i0 + 10, N - 1)]
    assert cand["sim_veh42"]["estado"] is not None
    assert c.post("/api/v1/espejo/reiniciar").json()["ok"] is True
    assert c.get("/api/v1/espejo/reiniciar").status_code == 200
    cand = {d["id"]: d for d in c.get("/api/v1/espejo/candidatos").json()}
    assert cand["sim_veh42"]["estado"] is None
    with c.websocket_connect("/ws/espejo/sim_veh42") as ws:
        assert ws.receive_json()["t_sim"] == MENSAJES[0]["t_sim"]


@pytest.mark.parametrize("ruta", ["/salud", "/api/v1/salud"])
def test_salud(ruta):
    c, _ = cliente_falso()
    r = c.get(ruta)
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True and d["contrato"] == 1 and d["t_sim"] is None
    assert ISO_MS_Z.match(d["ts"])


def test_cors_abierto():
    c, _ = cliente_falso()
    r = c.get("/salud", headers={"Origin": "http://ejemplo.test"})
    assert r.headers.get("access-control-allow-origin") == "*"


def test_latencias_se_agregan_al_csv(tmp_path, monkeypatch):
    """La app envía su CSV al terminar; el mock agrega las filas (una sola cabecera)."""
    from fastapi.testclient import TestClient

    destino = tmp_path / "lat.csv"
    monkeypatch.setenv("ESPEJO_LATENCIAS", str(destino))
    with TestClient(crear_app()) as c:
        csv = "modo,t_sim,lat_total_ms,lat_cliente_ms\nlocal,1180,85,12\nlocal,1181,90,10\n"
        assert c.post("/api/v1/espejo/latencias", content=csv).json() == {"ok": True, "filas": 2}
        assert c.post("/api/v1/espejo/latencias", content=csv).json()["filas"] == 2
        assert c.post("/api/v1/espejo/latencias", content="basura").json()["ok"] is False
    assert destino.read_text().splitlines() == [
        "modo,t_sim,lat_total_ms,lat_cliente_ms", "local,1180,85,12", "local,1181,90,10", "local,1180,85,12", "local,1181,90,10"]
