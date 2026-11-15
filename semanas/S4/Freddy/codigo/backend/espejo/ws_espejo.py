"""WebSocket `/ws/espejo/{veh_id}` (S3-3, contrato §7): la pantalla de un conductor simulado.

- Si `veh_id` no está en la simulación: `espejo_fin` con `motivo: "no_existe"` y cierre `4404`.
- Al conectar envía el último estado conocido; luego `{"tipo": "espejo"}` **solo de ese vehículo**,
  como mucho 1 por segundo (aunque lleguen 10 snapshots por segundo) y al menos uno cada
  `LATIDO_S` aunque no haya datos nuevos (la app reconecta tras 5 s de silencio).
- El recibo va una sola vez por sesión y conexión; una pantalla que se reconecta dentro de los
  60 s lo vuelve a recibir.
- Si el vehículo sale de la simulación o la corrida termina: `espejo_fin` y cierre `1000`.
- Varias pantallas pueden seguir al mismo vehículo; al desconectarse se libera el contador.

`DifusorEspejo` despierta a los WebSocket cuando llega un snapshot: el registro lo llama desde el
hilo de la ruta y el aviso entra al bucle con `call_soon_threadsafe`.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from comun import esquemas as e

from .registro import RegistroEspejo, ahora_utc

log = logging.getLogger("e-sert.espejo")

router = APIRouter(tags=["espejo"])

INTERVALO_MIN_S = 1.0  # 1 Hz como máximo
LATIDO_S = 2.0         # reenvía el último estado si no hay nada nuevo
CIERRE_NO_EXISTE = 4404
CIERRE_NORMAL = 1000


class DifusorEspejo:
    """Eventos de los WebSocket abiertos; `despertar()` se puede llamar desde cualquier hilo."""

    def __init__(self):
        self.eventos: Set[asyncio.Event] = set()
        self.bucle: Optional[asyncio.AbstractEventLoop] = None
        self._candado = threading.Lock()

    def unir(self) -> asyncio.Event:
        self.bucle = asyncio.get_running_loop()
        ev = asyncio.Event()
        with self._candado:
            self.eventos.add(ev)
        return ev

    def salir(self, ev: asyncio.Event) -> None:
        with self._candado:
            self.eventos.discard(ev)

    def despertar(self) -> None:
        bucle = self.bucle
        if bucle is None or bucle.is_closed():
            return
        with self._candado:
            eventos = list(self.eventos)
        if not eventos:
            return
        try:
            bucle.call_soon_threadsafe(lambda: [ev.set() for ev in eventos])
        except RuntimeError:  # el bucle se cerró entre medio
            pass


async def _enviar(ws: WebSocket, mensaje: e.Modelo) -> None:
    await ws.send_text(mensaje.model_dump_json())


async def _seguir(ws: WebSocket, reg: RegistroEspejo, veh_id: str, evento: asyncio.Event) -> None:
    """Bucle de envío de una pantalla."""
    recibos_enviados: Set[str] = set()
    version_enviada: Optional[int] = None
    ultimo_envio = -1e9
    corrida = reg.corrida
    while True:
        # se limpia ANTES de leer: un snapshot que llegue mientras se lee o se envía deja el
        # evento puesto y la espera de abajo vuelve enseguida (no se pierde el aviso)
        evento.clear()
        pendiente = reg.recibo_pendiente(veh_id, recibos_enviados)
        version = reg.version(veh_id)
        motivo = reg.fin(veh_id, corrida)
        nuevo = version != version_enviada or pendiente is not None
        if nuevo or time.monotonic() - ultimo_envio >= LATIDO_S:
            espera = INTERVALO_MIN_S - (time.monotonic() - ultimo_envio)
            if espera > 0 and motivo is None:
                await asyncio.sleep(espera)
                continue  # vuelve a leer: durante la espera pudo llegar algo más nuevo
            mensaje = reg.mensaje(veh_id, recibo=pendiente[1] if pendiente else None)
            if mensaje is not None and (motivo is None or nuevo):
                await _enviar(ws, mensaje)
                ultimo_envio = time.monotonic()
                version_enviada = version
                if pendiente is not None:
                    recibos_enviados.add(pendiente[0])
        if motivo is not None:
            await _enviar(ws, e.MensajeEspejoFin(veh_id=veh_id, t_sim=reg.t_sim, ts=ahora_utc(), motivo=motivo))
            await ws.close(code=CIERRE_NORMAL)
            return
        try:
            await asyncio.wait_for(evento.wait(), timeout=LATIDO_S)
        except asyncio.TimeoutError:
            pass


async def _escuchar(ws: WebSocket) -> None:
    """Detecta el cierre del cliente (que no necesita enviar nada)."""
    while True:
        msg = await ws.receive()
        if msg["type"] == "websocket.disconnect":
            return


@router.websocket("/ws/espejo/{veh_id}")
async def ws_espejo(ws: WebSocket, veh_id: str) -> None:
    """Mensajes `espejo` de un vehículo a ≤ 1 Hz y `espejo_fin` al terminar (§7)."""
    servicios = ws.app.state.servicios
    reg: RegistroEspejo = servicios.espejo
    difusor: DifusorEspejo = servicios.difusor_espejo
    await ws.accept()
    if not reg.existe(veh_id):
        fin = e.MensajeEspejoFin.model_construct(tipo="espejo_fin", veh_id=veh_id, t_sim=reg.t_sim,
                                                 ts=ahora_utc(), motivo=e.MotivoFinEspejo.no_existe)
        await ws.send_text(fin.model_dump_json())
        await ws.close(code=CIERRE_NO_EXISTE)
        return
    reg.suscribir(veh_id)
    evento = difusor.unir()
    tareas = [asyncio.create_task(_seguir(ws, reg, veh_id, evento)), asyncio.create_task(_escuchar(ws))]
    try:
        hechas, pendientes = await asyncio.wait(tareas, return_when=asyncio.FIRST_COMPLETED)
        for t in pendientes:
            t.cancel()
        for t in hechas:
            exc = t.exception()
            if exc is not None and not isinstance(exc, (WebSocketDisconnect, RuntimeError)):
                log.warning("WS espejo %s: %r", veh_id, exc)
    finally:
        for t in tareas:
            t.cancel()
        reg.liberar(veh_id)
        difusor.salir(evento)
