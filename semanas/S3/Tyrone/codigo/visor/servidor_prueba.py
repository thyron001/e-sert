"""Servidor de prueba del visor (S3-3): reproduce snapshots grabados con el formato del contrato.

Uso (desde semanas/S3/Tyrone/codigo, con el entorno visor/.venv):
    python -m visor.servidor_prueba --puerto 8001 --velocidad 5
    python -m visor.servidor_prueba --vehiculos 800      # relleno sintético para medir rendimiento
    python -m visor.servidor_prueba --snapshots demo/plan_b/snapshots_demo.jsonl   # plan B de la demo

- GET /api/v1/puestos             puestos de sumo/parqueos/puestos.csv (ocupados del primer snapshot)
- GET /api/v1/espejo/candidatos   autos con app que todavía buscan (contrato §7)
- GET /salud                      {ok, contrato: 1, t_sim, ts}
- WS  /ws/estado                  un solo reproductor para todos los clientes: snapshots en bucle a
                                  `velocidad` por segundo y un `kpi` cada 5 s reales
- WS  /ws/espejo/{veh_id}         mensajes `espejo` a 1 Hz del vehículo pedido (§7) y `espejo_fin`
- /visor/ y /                     la carpeta visor/ como estáticos, como en el despliegue

Un archivo con mensajes de varios tipos (p. ej. la grabación del ensayo de la demo, con `snapshot`,
`kpi` y `verdad`) se reproduce tal cual: los `kpi` grabados reemplazan a los sintéticos.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

DIR = Path(__file__).resolve().parent
DIR_CODIGO = DIR.parent
PUESTOS = DIR_CODIGO / "sumo" / "parqueos" / "puestos.csv"
DESTINOS = DIR_CODIGO / "sumo" / "demanda" / "destinos.csv"
BASE = DIR / "datos" / "base.json"
SNAPSHOTS = DIR / "datos" / "snapshots.jsonl"
MUESTRA = DIR / "datos" / "snapshots_muestra.jsonl"
KPI_CADA_S = 5.0
N_ESPEJOS = 2


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def dist_m(a, b) -> float:
    r = 6371000.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(min(1.0, h)))


def cargar_mensajes(ruta=None) -> List[dict]:
    ruta = Path(ruta) if ruta else (SNAPSHOTS if SNAPSHOTS.exists() else MUESTRA)
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]


def cargar_base(ruta=BASE) -> dict:
    if not Path(ruta).exists():
        return {}
    return json.loads(Path(ruta).read_text(encoding="utf-8")).get("base", {})


def cargar_puestos(primer_snapshot: dict) -> List[dict]:
    ocupados = {p["puesto_id"]: p["ocupados"] for p in primer_snapshot.get("puestos", [])}
    with open(PUESTOS, encoding="utf-8") as f:
        return [{"puesto_id": p["puesto_id"], "lat": float(p["lat"]), "lon": float(p["lon"]),
                 "calle": p["calle"], "capacidad": int(p["capacidad"]),
                 "ocupados": min(int(p["capacidad"]), ocupados.get(p["puesto_id"], 0))}
                for p in csv.DictReader(f)]


def cargar_destinos() -> List[dict]:
    with open(DESTINOS, encoding="utf-8") as f:
        return [{"nombre": d["nombre"], "lat": float(d["lat"]), "lon": float(d["lon"])} for d in csv.DictReader(f)]


def rellenar(snapshot: dict, n: int, semilla: int = 0) -> dict:
    """Completa `vehiculos` hasta `n` con copias desplazadas (prueba de rendimiento con ~800 autos)."""
    vehs = snapshot["vehiculos"]
    if n <= len(vehs) or not vehs:
        return snapshot
    rng = random.Random(semilla)
    extra = []
    for i in range(n - len(vehs)):
        v = dict(vehs[i % len(vehs)])
        v["id"] = f"sim_relleno_{i}"
        v["lat"] += rng.uniform(-0.0012, 0.0012)
        v["lon"] += rng.uniform(-0.0012, 0.0012)
        v["con_app"] = rng.random() < 0.8
        extra.append(v)
    return dict(snapshot, vehiculos=vehs + extra)


class Reproductor:
    """Un solo reloj para todos los clientes: así el visor y el WS espejo ven el mismo instante."""

    def __init__(self, mensajes: List[dict], velocidad: float, vehiculos: int, base: dict, puestos, destinos,
                 kpi_cada_s: float = KPI_CADA_S):
        self.snapshots = [m for m in mensajes if m.get("tipo") == "snapshot"]
        self.otros = {i: m for i, m in enumerate(mensajes) if m.get("tipo") != "snapshot"}
        self.mensajes = mensajes
        self.grabado_con_kpi = any(m.get("tipo") == "kpi" for m in mensajes)
        self.velocidad = velocidad
        self.vehiculos = vehiculos
        self.base = base
        self.puestos = puestos
        self.destinos = destinos
        self.i = -1
        self.actual: Optional[dict] = None
        self.clientes: set = set()
        self.espejos_mock: List[str] = []
        self.suscritos: Dict[str, int] = {}
        self.ultimo_kpi = 0.0
        self.kpi_cada_s = kpi_cada_s
        self.vueltas = 0
        self.destino_de: Dict[str, dict] = {}

    # MOCK: reemplazar cuando el backend publique espejos (Freddy S3-3). Elige 1–2 autos que buscan
    # y los marca con app; se mantienen mientras sigan en la escena.
    def elegir_espejos(self, snap: dict) -> None:
        ids = {v["id"] for v in snap["vehiculos"]}
        self.espejos_mock = [e for e in self.espejos_mock if e in ids]
        if len(self.espejos_mock) < N_ESPEJOS:
            cand = [v["id"] for v in snap["vehiculos"] if v.get("estado") in ("BUSCANDO", "GUIADO")
                    and v["id"] not in self.espejos_mock]
            self.espejos_mock += cand[: N_ESPEJOS - len(self.espejos_mock)]

    def preparar(self, snap: dict) -> dict:
        snap = rellenar(snap, self.vehiculos)
        if not snap.get("espejos"):
            self.elegir_espejos(snap)
            espejos = list(self.espejos_mock)
        else:
            espejos = list(snap["espejos"])
        espejos += [v for v, n in self.suscritos.items() if n > 0 and v not in espejos]
        marcados = set(espejos)
        vehs = [dict(v, con_app=True, estado=v.get("estado") or "BUSCANDO") if v["id"] in marcados else v
                for v in snap["vehiculos"]]
        return dict(snap, vehiculos=vehs, espejos=espejos, ts=ahora_iso().split(".")[0] + "Z")

    def kpi(self, t_sim: float) -> dict:
        # MOCK: valores sintéticos del orden de la matriz al 50 % con rf (el backend real los manda
        # desde KPIsSistema); oscilan para que se vean las minigráficas.
        b = self.base or {}
        osc = math.sin(t_sim / 120.0)
        valores = {
            "busqueda_media_s": round((b.get("busqueda_media_s") or 300) * (0.62 + 0.05 * osc), 2),
            "falsas_liberaciones_100": round(4.0 + 1.5 * osc, 2),
            "co2_busqueda_kg_h": round((b.get("co2_busqueda_kg_h") or 60) * (0.65 + 0.05 * osc), 2),
            "retardo_cierre_medio_s": round(30 + 5 * osc, 1),
            "precision_mapa": round(0.9 + 0.02 * osc, 4),
        }
        return {"tipo": "kpi", "t_sim": t_sim, "ts": ahora_iso().split(".")[0] + "Z", "valores": valores}

    async def difundir(self, texto: str) -> None:
        muertos = []
        for ws in list(self.clientes):
            try:
                await ws.send_text(texto)
            except Exception:  # noqa: BLE001
                muertos.append(ws)
        for ws in muertos:
            self.clientes.discard(ws)

    async def correr(self) -> None:
        loop = asyncio.get_event_loop()
        while True:
            for idx, m in enumerate(self.mensajes):
                if m.get("tipo") != "snapshot":
                    if m.get("tipo") in ("kpi", "verdad"):
                        await self.difundir(json.dumps(dict(m, ts=ahora_iso().split(".")[0] + "Z")))
                    continue
                self.i = idx
                self.actual = self.preparar(m)
                await self.difundir(json.dumps(self.actual, ensure_ascii=False))
                if not self.grabado_con_kpi and loop.time() - self.ultimo_kpi >= self.kpi_cada_s:
                    self.ultimo_kpi = loop.time()
                    await self.difundir(json.dumps(self.kpi(self.actual["t_sim"])))
                await asyncio.sleep(1.0 / self.velocidad)
            self.vueltas += 1

    # --- espejo (§7) -----------------------------------------------------------------------
    def destino(self, veh: str) -> dict:
        if veh not in self.destino_de:
            self.destino_de[veh] = random.Random(veh).choice(self.destinos)
        return self.destino_de[veh]

    def mensaje_espejo(self, veh: str) -> Optional[dict]:
        """`espejo` del vehículo en el instante actual. MOCK: ruta en línea recta al puesto libre
        más cercano al destino; sesión y billetera sintéticas."""
        snap = self.actual
        if not snap:
            return None
        v = next((x for x in snap["vehiculos"] if x["id"] == veh), None)
        if v is None:
            return None
        d = self.destino(veh)
        libres = [p for p in self.puestos if p["ocupados"] < p["capacidad"]] or self.puestos
        p = min(libres, key=lambda q: dist_m((q["lat"], q["lon"]), (d["lat"], d["lon"])))
        ruta = [[round(v["lat"] + (p["lat"] - v["lat"]) * k / 8, 6), round(v["lon"] + (p["lon"] - v["lon"]) * k / 8, 6)]
                for k in range(9)]
        estacionado = v.get("estado") in ("ESTACIONADO", "A_PIE", "REGRESANDO")
        return {"tipo": "espejo", "veh_id": veh, "t_sim": snap["t_sim"], "ts": ahora_iso(),
                "estado": v.get("estado"), "lat": v["lat"], "lon": v["lon"],
                "modo": "quieto" if estacionado else "vehiculo",
                "destino": {"nombre": d["nombre"], "lat": d["lat"], "lon": d["lon"]},
                "puesto": {"puesto_id": p["puesto_id"], "lat": p["lat"], "lon": p["lon"],
                           "distancia_m": round(dist_m((p["lat"], p["lon"]), (d["lat"], d["lon"])))},
                "ruta": [] if estacionado else ruta,
                "sesion": {"sesion_id": "ses_" + veh, "minutos": 3.0, "costo_usd": 0.03, "retenido_usd": 0.25}
                if estacionado else None,
                "billetera": {"saldo": 5.0, "disponible": 4.75}, "avisos": [], "recibo": None}


def crear_app(ruta_snapshots=None, velocidad=1.0, vehiculos=0, kpi_cada_s=KPI_CADA_S) -> FastAPI:
    mensajes = cargar_mensajes(ruta_snapshots)
    primer = next(m for m in mensajes if m.get("tipo") == "snapshot")
    puestos = cargar_puestos(primer)
    rep = Reproductor(mensajes, velocidad, vehiculos, cargar_base(), puestos, cargar_destinos(), kpi_cada_s)
    app = FastAPI(title="e-sert · servidor de prueba del visor")
    app.state.reproductor = rep

    @app.on_event("startup")
    async def _arrancar():
        app.state.tarea = asyncio.create_task(rep.correr())

    @app.on_event("shutdown")
    async def _parar():
        app.state.tarea.cancel()

    @app.get("/api/v1/puestos")
    def get_puestos():
        return puestos

    @app.get("/salud")
    @app.get("/api/v1/salud")
    def salud():
        return {"ok": True, "contrato": 1, "t_sim": rep.actual["t_sim"] if rep.actual else None, "ts": ahora_iso()}

    @app.get("/api/v1/espejo/candidatos")
    def candidatos():
        snap = rep.actual or rep.preparar(primer)
        return [{"id": v["id"], "destino_nombre": rep.destino(v["id"])["nombre"], "estado": v.get("estado"),
                 "t_sim": snap["t_sim"]} for v in snap["vehiculos"]
                if v.get("con_app") and v.get("estado") in ("BUSCANDO", "GUIADO", None)][:20]

    @app.websocket("/ws/estado")
    async def ws_estado(ws: WebSocket):
        await ws.accept()
        rep.clientes.add(ws)
        try:
            if rep.actual:
                await ws.send_text(json.dumps(rep.actual, ensure_ascii=False))
            while True:
                await ws.receive_text()  # el visor no manda nada; esto detecta el cierre
        except (WebSocketDisconnect, RuntimeError):
            rep.clientes.discard(ws)

    @app.websocket("/ws/espejo/{veh_id}")
    async def ws_espejo(ws: WebSocket, veh_id: str):
        # MOCK: reemplazar por el WS espejo real del backend (Freddy S3-3, contrato §7)
        await ws.accept()
        if rep.mensaje_espejo(veh_id) is None and rep.actual is not None:
            await ws.send_text(json.dumps({"tipo": "espejo_fin", "veh_id": veh_id, "t_sim": rep.actual["t_sim"],
                                           "ts": ahora_iso(), "motivo": "no_existe"}))
            await ws.close(code=4404)
            return
        rep.suscritos[veh_id] = rep.suscritos.get(veh_id, 0) + 1
        try:
            while True:
                m = rep.mensaje_espejo(veh_id)
                if m is None:
                    await ws.send_text(json.dumps({"tipo": "espejo_fin", "veh_id": veh_id,
                                                   "t_sim": rep.actual["t_sim"] if rep.actual else 0,
                                                   "ts": ahora_iso(), "motivo": "salio_simulacion"}))
                    await ws.close(code=1000)
                    return
                await ws.send_text(json.dumps(m, ensure_ascii=False))
                await asyncio.sleep(1.0)
        except (WebSocketDisconnect, RuntimeError):
            return
        finally:
            rep.suscritos[veh_id] -= 1

    app.mount("/visor", StaticFiles(directory=DIR, html=True), name="visor")
    app.mount("/", StaticFiles(directory=DIR, html=True), name="raiz")
    return app


def main():
    import uvicorn

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--puerto", type=int, default=8001)
    ap.add_argument("--velocidad", type=float, default=1.0, help="snapshots por segundo real")
    ap.add_argument("--snapshots", default=None)
    ap.add_argument("--vehiculos", type=int, default=0, help="rellena cada snapshot hasta N vehículos")
    ap.add_argument("--host", default="0.0.0.0")
    args = ap.parse_args()
    uvicorn.run(crear_app(args.snapshots, args.velocidad, args.vehiculos), host=args.host, port=args.puerto,
                log_level="warning")


if __name__ == "__main__":
    main()
