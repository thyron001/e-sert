"""Carga del backend (S3-2): 200 usuarios a 1 Hz durante 60 s y 5 visores por WebSocket.

Se excluye por defecto; se corre con `pytest -m carga backend/tests` (dura ~70 s). El servidor
es uvicorn real en otro proceso, sobre `127.0.0.1` y un puerto libre. Metas:

- `POST /api/v1/eventos/ubicacion`: p95 < 50 ms y 0 respuestas 5xx;
- 5 clientes `WS /ws/estado` reciben snapshots a ≤ 1 Hz y la cola no crece: el atraso entre el
  `POST /sim/paso` y la llegada del snapshot a cada visor se mantiene (no se acumula).

El servidor corre en **otro proceso** (`python -m uvicorn backend.api.main:app`). Los 200 usuarios
se reparten en `PROCESOS_CLIENTE` procesos y cada uno usa una conexión HTTP/1.1 persistente con
un cliente mínimo sobre `asyncio` (como `wrk`): con `httpx`, el propio generador gastaba más CPU
por petición que el servidor (0,73 ms) y su espera inflaba el p95 medido.
`ESERT_CARGA_S` cambia la duración (por defecto 60 s). El informe queda en
`traci/salidas_kpi/carga_backend.json`.
"""

from __future__ import annotations

import asyncio
import json
import multiprocessing as mp
import os
import socket
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
import websockets

pytestmark = pytest.mark.carga

USUARIOS = 200
VISORES = 5
PROCESOS_CLIENTE = 4
DURACION_S = float(os.environ.get("ESERT_CARGA_S", "60"))
EJEMPLOS = Path(__file__).resolve().parents[2] / "comun" / "ejemplos"
INFORME = Path(__file__).resolve().parents[2] / "traci" / "salidas_kpi" / "carga_backend.json"


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def servidor():
    puerto = _puerto_libre()
    codigo = Path(__file__).resolve().parents[2]
    env = {**os.environ, "ESERT_DB_URL": "sqlite:///:memory:", "PYTHONPATH": str(codigo)}
    env.pop("ESERT_TOKEN_SIM", None)
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.api.main:app", "--host", "127.0.0.1",
                             "--port", str(puerto), "--log-level", "warning"], cwd=codigo, env=env)
    url = f"127.0.0.1:{puerto}"
    fin = time.monotonic() + 20
    while True:
        try:
            if httpx.get(f"http://{url}/salud", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        assert time.monotonic() < fin and proc.poll() is None, "uvicorn no arrancó"
        time.sleep(0.2)
    yield url
    proc.terminate()
    proc.wait(timeout=10)


async def _usuario(url: str, i: int, fin: float, latencias: list, estados: list) -> None:
    """Un usuario: `POST /api/v1/eventos/ubicacion` a 1 Hz por su propia conexión persistente."""
    base = json.loads((EJEMPLOS / "ubicacion.json").read_text(encoding="utf-8"))
    host, puerto = url.split(":")
    lector, escritor = await asyncio.open_connection(host, int(puerto))
    usuario = f"sim_carga{i:03d}"
    await asyncio.sleep((i % 100) / 100)  # reparte los envíos dentro del segundo
    k = 0
    try:
        while time.monotonic() < fin:
            inicio = time.monotonic()
            cuerpo = json.dumps({**base, "usuario_id": usuario, "ts": _ts(), "t_sim": float(k),
                                 "lat": base["lat"] + 1e-5 * (k % 10), "lon": base["lon"]}).encode()
            escritor.write(b"POST /api/v1/eventos/ubicacion HTTP/1.1\r\nHost: " + url.encode() +
                           b"\r\nContent-Type: application/json\r\nContent-Length: " + str(len(cuerpo)).encode() +
                           b"\r\n\r\n" + cuerpo)
            await escritor.drain()
            cabecera = await lector.readuntil(b"\r\n\r\n")
            largo = 0
            for linea in cabecera.split(b"\r\n"):
                if linea.lower().startswith(b"content-length:"):
                    largo = int(linea.split(b":")[1])
            await lector.readexactly(largo)
            latencias.append(1000 * (time.monotonic() - inicio))
            estados.append(int(cabecera.split(b" ", 2)[1]))
            k += 1
            await asyncio.sleep(max(0.0, 1.0 - (time.monotonic() - inicio)))
    finally:
        escritor.close()


async def _simulador(cliente, fin: float, enviados: dict) -> None:
    """El controlador: un `POST /sim/paso` por segundo (t_sim avanza 1 s)."""
    paso = json.loads((EJEMPLOS / "sim_paso.json").read_text(encoding="utf-8"))
    t = 0.0
    while time.monotonic() < fin:
        enviados[t] = time.monotonic()
        await cliente.post("/api/v1/sim/paso", json={**paso, "t_sim": t, "ts": _ts()})
        t += 1.0
        await asyncio.sleep(1.0)


async def _visor(url: str, fin: float, llegadas: list) -> None:
    async with websockets.connect(f"ws://{url}/ws/estado?rol=visor") as ws:
        while time.monotonic() < fin:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=max(0.1, fin - time.monotonic())))
            except asyncio.TimeoutError:
                break
            if m["tipo"] == "snapshot":
                llegadas.append((time.monotonic(), m["t_sim"]))


def _proceso_usuarios(url: str, desde: int, hasta: int, inicio: float, duracion: float) -> tuple:
    """Proceso cliente: usuarios `desde..hasta-1` desde el instante `inicio` (time.time)."""
    async def correr():
        latencias, estados = [], []
        await asyncio.sleep(max(0.0, inicio - time.time()))
        fin = time.monotonic() + duracion
        await asyncio.gather(*[_usuario(url, i, fin, latencias, estados) for i in range(desde, hasta)])
        return latencias, estados
    return asyncio.run(correr())


async def _carga(url: str) -> dict:
    enviados = {}
    llegadas = [[] for _ in range(VISORES)]
    inicio = time.time() + 3.0  # tiempo para que arranquen los procesos cliente
    por_proceso = USUARIOS // PROCESOS_CLIENTE
    ctx = mp.get_context("spawn")
    with ctx.Pool(PROCESOS_CLIENTE) as pool:
        trabajos = [pool.apply_async(_proceso_usuarios, (url, k * por_proceso, (k + 1) * por_proceso, inicio,
                                                         DURACION_S)) for k in range(PROCESOS_CLIENTE)]
        async with httpx.AsyncClient(base_url=f"http://{url}", timeout=10) as cliente:
            visores = [asyncio.create_task(_visor(url, time.monotonic() + 3 + DURACION_S + 3, llegadas[i]))
                       for i in range(VISORES)]
            await asyncio.sleep(max(0.0, inicio - time.time()))
            await _simulador(cliente, time.monotonic() + DURACION_S, enviados)
            await asyncio.gather(*visores)
        resultados = [t.get(timeout=DURACION_S + 60) for t in trabajos]
    latencias = [x for lat, _ in resultados for x in lat]
    estados = [x for _, est in resultados for x in est]
    lat = sorted(latencias)
    atrasos = [[1000 * (llega - enviados[t]) for llega, t in x if t in enviados] for x in llegadas]
    tercio = max(1, min(len(a) for a in atrasos) // 3)
    return {"peticiones": len(lat), "procesos_cliente": PROCESOS_CLIENTE, "p50_ms": round(statistics.median(lat), 2),
            "p95_ms": round(lat[int(0.95 * (len(lat) - 1))], 2), "max_ms": round(lat[-1], 2),
            "respuestas_5xx": sum(1 for s in estados if s >= 500),
            "respuestas_no_202": sum(1 for s in estados if s != 202),
            "snapshots_por_visor": [len(x) for x in llegadas],
            "hz_max_por_visor": [_hz_max(x) for x in llegadas],
            "atraso_ws_ms_primer_tercio": [round(statistics.fmean(a[:tercio]), 1) for a in atrasos],
            "atraso_ws_ms_ultimo_tercio": [round(statistics.fmean(a[-tercio:]), 1) for a in atrasos],
            "atraso_ws_ms_max": round(max(max(a) for a in atrasos), 1), "duracion_s": DURACION_S}


def _hz_max(llegadas: list) -> float:
    """Snapshots por segundo de simulación: nunca dos con el mismo segundo ni menos de 1 s de t_sim."""
    ts = [t for _, t in llegadas]
    if len(ts) < 2:
        return 0.0
    return max(1.0 / (b - a) if b > a else float("inf") for a, b in zip(ts, ts[1:]))


def test_200_usuarios_a_1_hz_y_5_visores(servidor):
    informe = asyncio.run(_carga(servidor))
    INFORME.parent.mkdir(parents=True, exist_ok=True)
    INFORME.write_text(json.dumps(informe, indent=2), encoding="utf-8")
    print(json.dumps(informe, indent=2))
    assert informe["peticiones"] >= 0.9 * USUARIOS * DURACION_S
    assert informe["respuestas_5xx"] == 0
    assert informe["p95_ms"] < 50
    assert all(n >= 0.8 * DURACION_S for n in informe["snapshots_por_visor"])
    assert all(hz <= 1.0 for hz in informe["hz_max_por_visor"])
    # sin cola creciente: el atraso de entrega al final no supera al del inicio en más de 100 ms
    for primero, ultimo in zip(informe["atraso_ws_ms_primer_tercio"], informe["atraso_ws_ms_ultimo_tercio"]):
        assert ultimo <= primero + 100
    assert informe["atraso_ws_ms_max"] < 1000
