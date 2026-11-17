# MOCK: reemplazar cuando Freddy publique el modo espejo (S3-3)
"""Servidor MOCK del modo espejo (docs/CONTRATO.md §7) para probar la app sin SUMO.

Reproduce el recorrido grabado en `../src/espejo/recorrido_mock.json` como si fuera una
simulación en vivo: cada vehículo arranca cuando el primer cliente se conecta a él y avanza
un mensaje por segundo, haya o no clientes conectados. Si un cliente se reconecta, retoma
donde va el vehículo ahora (no reinicia).

Uso:
    python servidor_mock.py [--bucle] [--cortar-en N] [--host 0.0.0.0] [--port 8001]
    ESPEJO_BUCLE=1 ESPEJO_CORTAR_EN=10 uvicorn servidor_mock:app --host 0.0.0.0 --port 8001
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketDisconnect, WebSocketState

RUTA_RECORRIDO = Path(__file__).resolve().parent.parent / "src" / "espejo" / "recorrido_mock.json"

# Mismo recorrido grabado para los tres; solo cambian el id y el nombre del destino mostrado
# en la lista de candidatos.
CANDIDATOS = (
    ("sim_veh42", "Parque Calderón"),
    ("sim_veh17", "Mercado 10 de Agosto"),
    ("sim_veh63", "Catedral Nueva"),
)

# Código de cierre que usa --cortar-en (rango 4000-4999 reservado para aplicaciones).
CODIGO_CORTE = 4000
EPS = 1e-6

log = logging.getLogger("mock_espejo")


def ahora_iso() -> str:
    """Hora UTC actual en ISO 8601 con milisegundos y sufijo Z."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def cargar_recorrido(ruta: Path = RUTA_RECORRIDO) -> tuple[list[dict], dict]:
    """Devuelve (mensajes `espejo`, mensaje `espejo_fin`) del recorrido grabado."""
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    mensajes = [m for m in datos if m.get("tipo") == "espejo"]
    fines = [m for m in datos if m.get("tipo") == "espejo_fin"]
    fin = fines[-1] if fines else {"tipo": "espejo_fin", "t_sim": None, "motivo": "salio_simulacion"}
    if not mensajes:
        raise ValueError(f"El recorrido {ruta} no tiene mensajes 'espejo'")
    return mensajes, fin


@dataclass
class Vehiculo:
    veh_id: str
    destino_nombre: str
    inicio: float | None = None  # reloj() cuando arrancó la reproducción; None = sin arrancar


async def _dormir_real(segundos: float) -> None:
    await asyncio.sleep(segundos)


def crear_app(
    bucle: bool = False,
    cortar_en: float | None = None,
    reloj: Callable[[], float] = time.monotonic,
    intervalo_s: float = 1.0,
    dormir: Callable[[float], Awaitable[None]] = _dormir_real,
    ruta_recorrido: Path = RUTA_RECORRIDO,
) -> FastAPI:
    """Crea la app del mock.

    - `bucle`: al terminar el recorrido, el vehículo vuelve al primer mensaje (sin espejo_fin).
    - `cortar_en`: cierra cada websocket N segundos después de abrirse (sin espejo_fin).
    - `reloj`, `dormir`, `intervalo_s`: inyectables para que las pruebas usen un reloj falso.
    """
    mensajes, fin_grabado = cargar_recorrido(ruta_recorrido)
    total = len(mensajes)
    vehiculos = {vid: Vehiculo(vid, nombre) for vid, nombre in CANDIDATOS}

    app = FastAPI(title="MOCK modo espejo e-sert", version="0.1")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.vehiculos = vehiculos
    app.state.config = {"bucle": bucle, "cortar_en": cortar_en, "intervalo_s": intervalo_s}

    def pasos(v: Vehiculo, t: float) -> int:
        """Pasos (mensajes) transcurridos desde que arrancó el vehículo; sin módulo."""
        assert v.inicio is not None
        return max(0, int((t - v.inicio) / intervalo_s + EPS))

    def terminado(k: int) -> bool:
        return not bucle and k >= total

    def mensaje(v: Vehiculo, k: int) -> dict:
        m = copy.deepcopy(mensajes[k % total])
        m["veh_id"] = v.veh_id
        m["ts"] = ahora_iso()
        return m

    def mensaje_fin(veh_id: str, motivo: str, t_sim: Any) -> dict:
        return {"tipo": "espejo_fin", "veh_id": veh_id, "t_sim": t_sim, "ts": ahora_iso(), "motivo": motivo}

    @app.get("/salud")
    @app.get("/api/v1/salud")
    def salud() -> dict:
        # `ts` permite a la app estimar el desfase de reloj (método de Cristian).
        return {"ok": True, "contrato": 1, "t_sim": None, "ts": ahora_iso()}

    @app.get("/api/v1/espejo/candidatos")
    def candidatos() -> list[dict]:
        t = reloj()
        salida = []
        for v in vehiculos.values():
            if v.inicio is None:
                estado, t_sim = None, mensajes[0]["t_sim"]
            else:
                k = pasos(v, t)
                actual = mensajes[total - 1] if terminado(k) else mensajes[k % total]
                estado, t_sim = actual.get("estado"), actual.get("t_sim")
            salida.append({"id": v.veh_id, "destino_nombre": v.destino_nombre, "estado": estado, "t_sim": t_sim})
        return salida

    @app.post("/api/v1/espejo/latencias")
    async def latencias(request: Request) -> dict:
        """Solo del mock: la app envía aquí su CSV de latencias al terminar un recorrido.

        Se agregan las filas a ESPEJO_LATENCIAS (por defecto `salidas/latencias.csv` junto a este
        archivo, ignorado por git) para hacer el histograma sin pasar el CSV a mano.
        """
        texto = (await request.body()).decode("utf-8", errors="replace")
        lineas = [l for l in texto.splitlines() if l.strip()]
        if not lineas or lineas[0] != "modo,t_sim,lat_total_ms,lat_cliente_ms":
            return {"ok": False, "filas": 0}
        filas = lineas[1:]
        destino = Path(os.environ.get("ESPEJO_LATENCIAS", Path(__file__).with_name("salidas") / "latencias.csv"))
        destino.parent.mkdir(parents=True, exist_ok=True)
        nuevo = not destino.exists()
        with destino.open("a", encoding="utf-8") as f:
            if nuevo:
                f.write(lineas[0] + "\n")
            f.writelines(fila + "\n" for fila in filas)
        log.info("Latencias recibidas: %d filas → %s", len(filas), destino)
        return {"ok": True, "filas": len(filas)}

    @app.api_route("/api/v1/espejo/reiniciar", methods=["GET", "POST"])
    def reiniciar() -> dict:
        for v in vehiculos.values():
            v.inicio = None
        log.info("Relojes de reproducción reiniciados")
        return {"ok": True, "reiniciados": list(vehiculos)}

    async def emitir(ws: WebSocket, v: Vehiculo, abierto_en: float) -> str:
        """Envía mensajes a 1 Hz alineados al reloj del vehículo. Devuelve el motivo de salida."""
        ultimo_k = -1
        while True:
            t = reloj()
            if cortar_en is not None and t - abierto_en >= cortar_en - EPS:
                await ws.close(code=CODIGO_CORTE, reason="corte_prueba")
                return f"cortada tras {cortar_en} s (--cortar-en)"
            if v.inicio is None:  # primera conexión o tras /reiniciar
                v.inicio = t
                ultimo_k = -1
            k = pasos(v, t)
            if terminado(k):
                await ws.send_json(mensaje_fin(v.veh_id, fin_grabado.get("motivo", "salio_simulacion"), fin_grabado.get("t_sim")))
                await ws.close(code=1000)
                return "fin del recorrido (espejo_fin)"
            if k != ultimo_k:
                await ws.send_json(mensaje(v, k))
                ultimo_k = k
            espera = v.inicio + (k + 1) * intervalo_s - reloj()
            if cortar_en is not None:
                espera = min(espera, abierto_en + cortar_en - reloj())
            await dormir(max(espera, 0.0))

    async def escuchar(ws: WebSocket) -> str:
        """Lee (y descarta) lo que mande el cliente para detectar la desconexión."""
        while True:
            m = await ws.receive()
            if m["type"] == "websocket.disconnect":
                return "el cliente se desconectó"

    @app.websocket("/ws/espejo/{veh_id}")
    async def ws_espejo(ws: WebSocket, veh_id: str) -> None:
        await ws.accept()
        cliente = f"{ws.client.host}:{ws.client.port}" if ws.client else "?"
        v = vehiculos.get(veh_id)
        if v is None:
            log.info("WS %s desde %s: no existe -> espejo_fin no_existe", veh_id, cliente)
            await ws.send_json(mensaje_fin(veh_id, "no_existe", None))
            await ws.close(code=1000)
            return
        abierto_en = reloj()
        log.info("WS conectado: %s desde %s", veh_id, cliente)
        emisor = asyncio.ensure_future(emitir(ws, v, abierto_en))
        tareas = {emisor, asyncio.ensure_future(escuchar(ws))}
        motivo = "?"
        try:
            hechas, pendientes = await asyncio.wait(tareas, return_when=asyncio.FIRST_COMPLETED)
            for p in pendientes:
                p.cancel()
            # Si terminan las dos a la vez (p. ej. el corte del servidor), manda el motivo de emitir.
            for h in sorted(hechas, key=lambda h: h is emisor):
                try:
                    motivo = h.result()
                except (WebSocketDisconnect, RuntimeError, OSError) as e:
                    motivo = f"conexión perdida ({type(e).__name__})"
        finally:
            for t in tareas:
                t.cancel()
            if ws.application_state != WebSocketState.DISCONNECTED and ws.client_state != WebSocketState.DISCONNECTED:
                try:
                    await ws.close(code=1000)
                except Exception:  # noqa: BLE001 - el socket ya pudo cerrarse
                    pass
            log.info("WS desconectado: %s desde %s (%s)", veh_id, cliente, motivo)

    return app


def _config_entorno() -> dict:
    bucle = os.environ.get("ESPEJO_BUCLE", "0").strip().lower() in ("1", "true", "si", "sí", "yes")
    cortar = os.environ.get("ESPEJO_CORTAR_EN", "").strip()
    return {"bucle": bucle, "cortar_en": float(cortar) if cortar else None}


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# Instancia por defecto, para `uvicorn servidor_mock:app` (configurable con ESPEJO_BUCLE y
# ESPEJO_CORTAR_EN).
app = crear_app(**_config_entorno())


def main() -> None:
    import uvicorn

    entorno = _config_entorno()
    p = argparse.ArgumentParser(description="MOCK del modo espejo de e-sert (CONTRATO §7)")
    p.add_argument("--bucle", action="store_true", default=entorno["bucle"],
                   help="al terminar, el recorrido vuelve a empezar (sin espejo_fin)")
    p.add_argument("--cortar-en", type=float, default=entorno["cortar_en"], metavar="N",
                   help="cierra cada websocket N segundos después de abrirse (prueba de reconexión)")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8001)
    a = p.parse_args()
    log.info("MOCK espejo en %s:%s (bucle=%s, cortar_en=%s)", a.host, a.port, a.bucle, a.cortar_en)
    uvicorn.run(crear_app(bucle=a.bucle, cortar_en=a.cortar_en), host=a.host, port=a.port)


if __name__ == "__main__":
    main()
