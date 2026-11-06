"""Cliente de prueba del modo espejo (S3-3): sigue candidatos y mide la latencia.

Hace lo que haría el teléfono espejo, sin la app:

1. pide `GET /api/v1/espejo/candidatos` hasta que haya autos en `GUIADO`;
2. abre `WS /ws/espejo/{veh_id}` para hasta `--pantallas` de ellos (cuando uno termina sin recibo,
   toma otro candidato);
3. a la vez escucha `/ws/estado?rol=publico`: de ahí saca el `ts` del controlador de cada
   `t_sim` (el snapshot reenvía el `ts` del cuerpo) y si `espejos` resalta al auto seguido;
4. termina cuando un auto seguido recibió el recibo y su `espejo_fin` (o al agotar `--max-s`).

Latencia snapshot → pantalla = hora de llegada del mensaje espejo − `ts` del controlador del mismo
`t_sim`. Con controlador y cliente en la misma máquina, los relojes coinciden; contra el VPS hay
que correr el cliente en la misma laptop que el controlador.

    python3 -m backend.espejo.seguir --url http://localhost:8000 --salida traci/salidas_kpi/espejo_local.json
    python3 -m backend.espejo.seguir --url https://demo.e-sert.tesisucuenca.com --min-s 600 ...

Escribe un JSON con la línea de tiempo de cada auto seguido y el resumen de latencias (p50, p95).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import websockets


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _iso(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


def percentil(xs: List[float], q: float) -> Optional[float]:
    if not xs:
        return None
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    i = int(k)
    return xs[i] if i + 1 >= len(xs) else xs[i] + (xs[i + 1] - xs[i]) * (k - i)


class Seguidor:
    def __init__(self, url: str, pantallas: int, max_s: float, min_s: float, estados: tuple):
        self.url = url.rstrip("/")
        self.ws_url = self.url.replace("https://", "wss://").replace("http://", "ws://")
        self.pantallas = pantallas
        self.max_s = max_s
        self.min_s = min_s
        self.estados = estados
        self.ts_controlador: Dict[float, datetime] = {}
        self.resaltados: Dict[str, int] = {}  # veh → snapshots en que aparece en `espejos`
        self.snapshots = 0
        self.lineas: Dict[str, List[dict]] = {}
        self.fin: Dict[str, dict] = {}
        self.desconexiones: Dict[str, int] = {}
        self.terminado = asyncio.Event()
        self.con_recibo: List[str] = []
        self.inicio = time.monotonic()

    # ------------------------------------------------------------------ candidatos

    def candidatos(self) -> List[dict]:
        req = urllib.request.Request(f"{self.url}/api/v1/espejo/candidatos", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())

    async def elegir(self, excluir: set) -> Optional[str]:
        while not self.terminado.is_set():
            try:
                lista = await asyncio.to_thread(self.candidatos)
            except OSError as err:
                print("candidatos:", err, file=sys.stderr)
                lista = []
            for c in lista:
                if c["estado"] in self.estados and c["id"] not in excluir:
                    return c["id"]
            await asyncio.sleep(1.0)
        return None

    # ------------------------------------------------------------------ WebSockets

    async def estado(self) -> None:
        """`/ws/estado?rol=publico`: `ts` del controlador por `t_sim` y el resaltado `espejos`."""
        while not self.terminado.is_set():
            try:
                async with websockets.connect(f"{self.ws_url}/ws/estado?rol=publico", max_size=None) as ws:
                    async for texto in ws:
                        m = json.loads(texto)
                        if m["tipo"] != "snapshot":
                            continue
                        self.snapshots += 1
                        self.ts_controlador[m["t_sim"]] = _iso(m["ts"])
                        for v in m.get("espejos", []):
                            self.resaltados[v] = self.resaltados.get(v, 0) + 1
                        if self.terminado.is_set():
                            return
            except (OSError, websockets.ConnectionClosed) as err:
                print("ws/estado:", repr(err), file=sys.stderr)
                await asyncio.sleep(1.0)

    async def pantalla(self, veh: str) -> None:
        """Una pantalla siguiendo a `veh`; reconecta si se corta (como la app)."""
        linea = self.lineas.setdefault(veh, [])
        while not self.terminado.is_set():
            try:
                async with websockets.connect(f"{self.ws_url}/ws/espejo/{veh}", max_size=None) as ws:
                    async for texto in ws:
                        llegada = _ahora()
                        m = json.loads(texto)
                        if m["tipo"] == "espejo_fin":
                            self.fin[veh] = {"motivo": m["motivo"], "t_sim": m.get("t_sim"),
                                             "s_desde_inicio": round(time.monotonic() - self.inicio, 1)}
                            return
                        linea.append({
                            "llegada": llegada.isoformat(),
                            "s": round(time.monotonic() - self.inicio, 3),
                            "t_sim": m["t_sim"], "estado": m["estado"], "modo": m["modo"],
                            "distancia_m": (m["puesto"] or {}).get("distancia_m"),
                            "costo_usd": (m["sesion"] or {}).get("costo_usd"),
                            "minutos": (m["sesion"] or {}).get("minutos"),
                            "saldo": (m["billetera"] or {}).get("saldo"),
                            "avisos": m["avisos"], "n_ruta": len(m["ruta"]),
                            "recibo": m["recibo"],
                            "lat_backend_ms": round((llegada - _iso(m["ts"])).total_seconds() * 1000, 1),
                        })
                        if m["recibo"] is not None and veh not in self.con_recibo:
                            self.con_recibo.append(veh)
                return
            except (OSError, websockets.ConnectionClosed) as err:
                self.desconexiones[veh] = self.desconexiones.get(veh, 0) + 1
                print(f"ws/espejo/{veh}:", repr(err), file=sys.stderr)
                await asyncio.sleep(1.0)

    async def correr(self) -> dict:
        tarea_estado = asyncio.create_task(self.estado())
        seguidos: set = set()
        activas: Dict[str, asyncio.Task] = {}

        async def vigilar():
            while True:
                transcurrido = time.monotonic() - self.inicio
                listo = any(v in self.fin for v in self.con_recibo) and transcurrido >= self.min_s
                if listo or transcurrido > self.max_s:
                    self.terminado.set()
                    return
                await asyncio.sleep(0.5)

        tarea_vigilar = asyncio.create_task(vigilar())
        while not self.terminado.is_set():
            for v in [v for v, t in activas.items() if t.done()]:
                del activas[v]
            if len(activas) < self.pantallas:
                veh = await self.elegir(seguidos)
                if veh is None:
                    break
                seguidos.add(veh)
                activas[veh] = asyncio.create_task(self.pantalla(veh))
                print(f"sigo {veh} ({len(activas)} pantallas)", flush=True)
            await asyncio.sleep(0.5)
        await tarea_vigilar
        for t in list(activas.values()) + [tarea_estado]:
            t.cancel()
        await asyncio.gather(*activas.values(), tarea_estado, return_exceptions=True)
        return self.resumen()

    def resumen(self) -> dict:
        todas = [p for linea in self.lineas.values() for p in linea]
        for linea in self.lineas.values():
            visto = set()
            for p in linea:  # el snapshot del mismo t_sim puede llegar por /ws/estado después del espejo
                ts_ctrl = self.ts_controlador.get(p["t_sim"])
                # un latido repite el último dato: no es un dato nuevo y no cuenta como latencia
                p["latido"] = p["t_sim"] in visto
                visto.add(p["t_sim"])
                p["lat_total_ms"] = None if ts_ctrl is None or p["latido"] else \
                    round((_iso(p["llegada"]) - ts_ctrl).total_seconds() * 1000, 1)
        total = [p["lat_total_ms"] for p in todas if p["lat_total_ms"] is not None]
        backend = [p["lat_backend_ms"] for p in todas]
        # el auto principal: el que llegó al recibo y a su espejo_fin; si no, el primero con recibo
        completos = [v for v in self.con_recibo if v in self.fin]
        principal = (completos or self.con_recibo or sorted(self.lineas, key=lambda v: -len(self.lineas[v])) or [None])[0]
        return {
            "url": self.url,
            "duracion_s": round(time.monotonic() - self.inicio, 1),
            "snapshots_visor": self.snapshots,
            "mensajes_espejo": len(todas),
            "latencia_total_ms": {"n": len(total), "p50": percentil(total, 0.5), "p95": percentil(total, 0.95),
                                  "max": max(total) if total else None, "min": min(total) if total else None,
                                  "fuera_de_0_1000": sum(1 for x in total if not 0 <= x <= 1000)},
            "latidos": sum(1 for p in todas if p["latido"]),
            "latencia_desde_backend_ms": {"n": len(backend), "p50": percentil(backend, 0.5),
                                          "p95": percentil(backend, 0.95)},
            "intervalo_entre_mensajes_s": {
                "p50": percentil([b["s"] - a["s"] for l in self.lineas.values() for a, b in zip(l, l[1:])], 0.5),
                "min": min([b["s"] - a["s"] for l in self.lineas.values() for a, b in zip(l, l[1:])] or [None])},
            "principal": principal,
            "con_recibo": self.con_recibo,
            "fin": self.fin,
            "desconexiones": self.desconexiones,
            "resaltados_en_visor": self.resaltados,
            "lineas": self.lineas,
        }


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description="Sigue autos por /ws/espejo y mide la latencia (S3-3)")
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--pantallas", type=int, default=3, help="Autos seguidos a la vez")
    ap.add_argument("--max-s", type=float, default=900, help="Tiempo real máximo")
    ap.add_argument("--min-s", type=float, default=0, help="Seguir al menos este tiempo real (estabilidad)")
    ap.add_argument("--estados", default="GUIADO", help="Estados aceptables del candidato, separados por coma")
    ap.add_argument("--salida", type=Path, required=True)
    args = ap.parse_args(argv)
    s = Seguidor(args.url, args.pantallas, args.max_s, args.min_s, tuple(args.estados.split(",")))
    resumen = asyncio.run(s.correr())
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(resumen, indent=1, ensure_ascii=False), encoding="utf-8")
    corto = {k: v for k, v in resumen.items() if k != "lineas"}
    print(json.dumps(corto, indent=2, ensure_ascii=False))
    return resumen


if __name__ == "__main__":
    main()
