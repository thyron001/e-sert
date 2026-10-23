"""WebSocket `/ws/estado` (contrato §6) y la cola por la que el controlador TraCI publica.

- `GestorConexiones` lleva los clientes conectados y difunde con `asyncio.gather`, descartando
  los que se cayeron.
- `publicar(mensaje)` es síncrono y seguro entre hilos: mete el mensaje en una
  `asyncio.Queue` que un consumidor (arrancado en el *lifespan*) difunde. Así el controlador
  puede empujar snapshots **en proceso**; desde otro proceso usa `POST /api/v1/interno/snapshot`.
- `verdad` solo va a los clientes que la piden: `?rol=visor` (por defecto) la recibe y
  `?rol=publico` nunca; `?verdad=0|1` lo fuerza para un visor.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from enum import Enum
from typing import Dict, Optional

from fastapi import APIRouter, Query, Request, WebSocket, WebSocketDisconnect

from comun import esquemas as e

log = logging.getLogger("e-sert.ws")

router = APIRouter(tags=["websocket"])


class Rol(str, Enum):
    """Quién se conecta a `/ws/estado`."""

    visor = "visor"
    publico = "publico"


class GestorConexiones:
    """Clientes de `/ws/estado` y difusión de mensajes del contrato."""

    def __init__(self, tamanio_cola: int = 1000):
        self.clientes: Dict[WebSocket, bool] = {}  # socket → ¿recibe verdad?
        self.tamanio_cola = tamanio_cola
        self.cola: Optional[asyncio.Queue] = None  # se crea en el bucle de la app (iniciar)
        self.bucle: Optional[asyncio.AbstractEventLoop] = None
        self._hilo_bucle: Optional[int] = None
        self._tarea: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------ clientes

    async def conectar(self, ws: WebSocket, verdad: bool) -> None:
        await ws.accept()
        self.clientes[ws] = verdad

    def desconectar(self, ws: WebSocket) -> None:
        self.clientes.pop(ws, None)

    async def difundir(self, mensaje: e.Modelo) -> int:
        """Envía el mensaje a quien corresponda. Devuelve a cuántos clientes llegó."""
        texto = mensaje.model_dump_json()
        es_verdad = getattr(mensaje, "tipo", None) == "verdad"
        destino = [ws for ws, quiere_verdad in list(self.clientes.items()) if quiere_verdad or not es_verdad]
        resultados = await asyncio.gather(*(ws.send_text(texto) for ws in destino), return_exceptions=True)
        for ws, r in zip(destino, resultados):
            if isinstance(r, BaseException):
                log.info("Cliente WS caído, se descarta: %r", r)
                self.desconectar(ws)
        return sum(1 for r in resultados if not isinstance(r, BaseException))

    # ------------------------------------------------------------------ cola

    def publicar(self, mensaje: e.Modelo) -> None:
        """Encola un mensaje para difundir. Se puede llamar desde cualquier hilo."""
        if self.bucle is None:
            return  # la app aún no arrancó: no hay a quién enviar
        if threading.get_ident() == self._hilo_bucle:
            self._encolar(mensaje)
        else:
            self.bucle.call_soon_threadsafe(self._encolar, mensaje)

    def _encolar(self, mensaje: e.Modelo) -> None:
        try:
            self.cola.put_nowait(mensaje)
        except asyncio.QueueFull:
            log.warning("Cola WS llena: se descarta un mensaje %s", getattr(mensaje, "tipo", "?"))

    async def _consumir(self) -> None:
        while True:
            mensaje = await self.cola.get()
            try:
                await self.difundir(mensaje)
            except Exception:  # pragma: no cover - un fallo no debe matar el consumidor
                log.exception("Fallo al difundir")
            finally:
                self.cola.task_done()

    def iniciar(self) -> None:
        """Arranca el consumidor en el bucle actual (lo llama el *lifespan*)."""
        self.bucle = asyncio.get_running_loop()
        self.cola = asyncio.Queue(maxsize=self.tamanio_cola)
        self._hilo_bucle = threading.get_ident()
        self._tarea = asyncio.create_task(self._consumir())

    async def detener(self) -> None:
        if self._tarea is not None:
            self._tarea.cancel()
            try:
                await self._tarea
            except asyncio.CancelledError:
                pass
        self.bucle = None


@router.websocket("/ws/estado")
async def ws_estado(ws: WebSocket, rol: Rol = Query(Rol.visor),
                    verdad: Optional[bool] = Query(None)) -> None:
    """Snapshots, KPIs y (solo visor) `verdad`. El cliente no necesita enviar nada."""
    gestor: GestorConexiones = ws.app.state.servicios.gestor
    recibe_verdad = rol is Rol.visor and (verdad is None or verdad)
    await gestor.conectar(ws, recibe_verdad)
    try:
        while True:
            await ws.receive_text()  # mantiene viva la conexión y detecta el cierre
    except WebSocketDisconnect:
        pass
    finally:
        gestor.desconectar(ws)


def gestor_de(request: Request) -> GestorConexiones:
    return request.app.state.servicios.gestor
