"""`/ws/estado` contra el backend vivo (uvicorn real, cliente `websockets`).

- Cada mensaje se valida con la unión discriminada `comun.esquemas.MensajeWS`.
- Como máximo un `snapshot` por segundo de simulación, aunque el controlador publique más seguido.
- Los mensajes `verdad` nunca llegan a un cliente tipo app (`rol=publico`, aunque pida `verdad=1`);
  el visor sí los recibe (control positivo).
"""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

import httpx
import pytest
from websockets.sync.client import connect

from comun import esquemas as e

pytestmark = pytest.mark.e2e

EJEMPLO = json.loads((Path(e.__file__).parent / "ejemplos" / "sim_paso.json").read_text(encoding="utf-8"))
T_PASOS = [100.0, 100.2, 100.5, 100.9, 101.0, 101.4, 102.0, 102.1, 102.99, 103.0, 104.5]
CENTINELA = 999.0


def leer_todo(ws, hasta_kpi: float = CENTINELA, timeout: float = 5.0) -> list:
    """Lee y valida mensajes hasta el KPI centinela (incluido)."""
    recibidos = []
    fin = time.monotonic() + timeout
    while time.monotonic() < fin:
        m = e.leer_mensaje_ws(ws.recv(timeout=max(0.01, fin - time.monotonic())))
        recibidos.append(m)
        if isinstance(m, e.MensajeKpi) and m.t_sim == hasta_kpi:
            return recibidos
    pytest.fail("no llegó el KPI centinela")


def esperar_clientes(servidor, n: int) -> None:
    fin = time.monotonic() + 3
    while len(servidor.app.state.servicios.gestor.clientes) < n:
        assert time.monotonic() < fin, "el WS no se registró"
        time.sleep(0.01)


def publicar_corrida(cliente: httpx.Client, token: dict) -> None:
    for t in T_PASOS:
        r = cliente.post("/sim/paso", headers=token, json={**EJEMPLO, "t_sim": t})
        assert r.status_code == 202, r.text
    r = cliente.post("/sim/kpi", headers=token, json={"tipo": "kpi", "t_sim": CENTINELA,
                                                      "ts": "2026-11-14T15:00:00Z", "valores": {"fin": 1}})
    assert r.status_code == 202, r.text


def test_mensajes_validos_un_snapshot_por_segundo_y_sin_verdad_para_la_app(servidor, cliente, token_sim):
    base = f"{servidor.ws}/ws/estado"
    with connect(f"{base}?rol=publico") as app_ws, \
            connect(f"{base}?rol=publico&verdad=1") as app_pide_verdad, \
            connect(f"{base}?rol=visor") as visor:
        esperar_clientes(servidor, 3)
        publicar_corrida(cliente, token_sim)
        por_cliente = {"app": leer_todo(app_ws), "app_verdad1": leer_todo(app_pide_verdad),
                       "visor": leer_todo(visor)}

    for nombre, mensajes in por_cliente.items():
        tipos = Counter(m.tipo for m in mensajes)
        snaps = [m.t_sim for m in mensajes if isinstance(m, e.MensajeSnapshot)]
        # Un snapshot por segundo simulado como máximo, y separados al menos 1 s.
        assert max(Counter(int(t) for t in snaps).values()) == 1, (nombre, snaps)
        assert all(b - a >= 1.0 for a, b in zip(snaps, snaps[1:])), (nombre, snaps)
        assert snaps[0] == T_PASOS[0] and len(snaps) < len(T_PASOS), (nombre, snaps)
        if nombre.startswith("app"):
            assert tipos["verdad"] == 0, f"{nombre} recibió verdad: {tipos}"
        else:
            assert tipos["verdad"] == len(snaps), f"el visor debe recibir verdad: {tipos}"


def test_snapshot_coincide_con_el_mapa_http(servidor, cliente, token_sim, usuario_app):
    """El `snapshot.puestos` que ve la app es el mapa del sistema (`GET /puestos`), no la verdad de SUMO."""
    puesto = EJEMPLO["verdad"]["puestos"][0]["puesto_id"]
    r = cliente.post("/sesiones", json={"usuario_id": usuario_app.id, "placa": "WSS-0001", "puesto_id": puesto})
    assert r.status_code == 201, r.text
    with connect(f"{servidor.ws}/ws/estado?rol=publico") as ws:
        esperar_clientes(servidor, 1)
        publicar_corrida(cliente, token_sim)
        snap = next(m for m in leer_todo(ws) if isinstance(m, e.MensajeSnapshot))
    http = {p["puesto_id"]: p["ocupados"] for p in cliente.get("/puestos").json()}
    ws_ocupados = {p.puesto_id: p.ocupados for p in snap.puestos}
    assert ws_ocupados and all(http[pid] == n for pid, n in ws_ocupados.items())
    # La sesión abierta se ve (1) y no el conteo de la verdad del paso de ejemplo.
    assert ws_ocupados[puesto] == http[puesto] == 1
    assert EJEMPLO["verdad"]["puestos"][0]["ocupados"] != 1


def test_publicar_sin_token_401_y_no_difunde(servidor, cliente, token_sim):
    with connect(f"{servidor.ws}/ws/estado?rol=visor") as ws:
        esperar_clientes(servidor, 1)
        r = cliente.post("/sim/paso", json={**EJEMPLO, "t_sim": 5.0})
        assert r.status_code == 401 and r.json()["error"]["codigo"] == "TOKEN_SIM_INVALIDO"
        r = cliente.post("/sim/kpi", headers=token_sim, json={"tipo": "kpi", "t_sim": CENTINELA,
                                                              "ts": "2026-11-14T15:00:00Z", "valores": {}})
        assert r.status_code == 202
        assert [m.tipo for m in leer_todo(ws)] == ["kpi"]
