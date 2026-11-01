"""Servidor de prueba del visor: reproduce snapshots grabados con el formato del contrato.

Uso (desde semanas/S2/Tyrone/codigo, con el entorno visor/.venv):
    python -m visor.servidor_prueba --puerto 8001 --velocidad 5

- GET /api/v1/puestos   puestos de sumo/parqueos/puestos.csv (ocupados del primer snapshot)
- WS  /ws/estado        reproduce visor/datos/snapshots.jsonl en bucle (o la muestra de 60 si
                        no existe), a `velocidad` snapshots por segundo, y cada 30 snapshots
                        un mensaje `kpi` con los valores de kpis/salidas/kpis_base.json
- /visor/ y /           la carpeta visor/ como estáticos, como en el despliegue
"""
import argparse
import asyncio
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

DIR = Path(__file__).resolve().parent
DIR_CODIGO = DIR.parent
PUESTOS = DIR_CODIGO / "sumo" / "parqueos" / "puestos.csv"
KPIS = DIR_CODIGO / "kpis" / "salidas" / "kpis_base.json"
SNAPSHOTS = DIR / "datos" / "snapshots.jsonl"
MUESTRA = DIR / "datos" / "snapshots_muestra.jsonl"
KPI_CADA = 30


def cargar_snapshots(ruta=None):
    ruta = Path(ruta) if ruta else (SNAPSHOTS if SNAPSHOTS.exists() else MUESTRA)
    return [linea for linea in ruta.read_text(encoding="utf-8").splitlines() if linea.strip()]


def cargar_kpis(ruta=KPIS):
    """Valores numéricos del mensaje `kpi` (los null, como falsas_liberaciones_100, se omiten)."""
    if not Path(ruta).exists():
        return {}
    valores = json.loads(Path(ruta).read_text(encoding="utf-8")).get("valores", {})
    return {k: float(v) for k, v in valores.items() if v is not None}


def cargar_puestos(primer_snapshot):
    ocupados = {p["puesto_id"]: p["ocupados"] for p in json.loads(primer_snapshot)["puestos"]}
    with open(PUESTOS, encoding="utf-8") as f:
        return [{"puesto_id": p["puesto_id"], "lat": float(p["lat"]), "lon": float(p["lon"]),
                 "calle": p["calle"], "capacidad": int(p["capacidad"]),
                 "ocupados": min(int(p["capacidad"]), ocupados.get(p["puesto_id"], 0))}
                for p in csv.DictReader(f)]


def crear_app(ruta_snapshots=None, velocidad=1.0):
    snapshots = cargar_snapshots(ruta_snapshots)
    kpis = cargar_kpis()
    puestos = cargar_puestos(snapshots[0])
    app = FastAPI(title="e-sert · servidor de prueba del visor")

    @app.get("/api/v1/puestos")
    def get_puestos():
        return puestos

    @app.websocket("/ws/estado")
    async def ws_estado(ws: WebSocket):
        await ws.accept()
        try:
            n = 0
            while True:
                for linea in snapshots:
                    await ws.send_text(linea)
                    n += 1
                    if kpis and n % KPI_CADA == 0:
                        t_sim = json.loads(linea)["t_sim"]
                        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                        await ws.send_text(json.dumps({"tipo": "kpi", "t_sim": t_sim, "ts": ts,
                                                       "valores": kpis}))
                    await asyncio.sleep(1.0 / velocidad)
        except (WebSocketDisconnect, RuntimeError):
            return

    app.mount("/visor", StaticFiles(directory=DIR, html=True), name="visor")
    app.mount("/", StaticFiles(directory=DIR, html=True), name="raiz")
    return app


def main():
    import uvicorn
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--puerto", type=int, default=8001)
    ap.add_argument("--velocidad", type=float, default=1.0, choices=[1, 5, 10])
    ap.add_argument("--snapshots", default=None)
    ap.add_argument("--host", default="0.0.0.0")
    args = ap.parse_args()
    uvicorn.run(crear_app(args.snapshots, args.velocidad), host=args.host, port=args.puerto)


if __name__ == "__main__":
    main()
