"""Mide las tres cifras de `arquitectura.md` (S4-2) y las deja en `comun/docs/cifras.json`.

    python comun/docs/medir_cifras.py                  # desde la carpeta con backend/, comun/ y traci/
    python comun/docs/medir_cifras.py --sin-sumo       # solo la latencia de la API

1. **ms por paso de TraCI** con 80 % de autos con app: `traci.correr_kpis --id p80_rf_s1` sin
   publicar, dentro del contenedor `van3twin` (`ms_por_paso` del resumen).
2. **Latencia de la API p50/p95**: uvicorn real en esta computadora y `httpx` por loopback, N
   pedidos a cada una de cuatro rutas de la app (`GET /puestos`, `GET /guia`,
   `POST /eventos/ubicacion`, `GET /billetera/{id}`).
3. **Mensajes WS por segundo** que recibe un visor (`/ws/estado?rol=visor`) mientras el
   controlador publica a ritmo real (`--ritmo 1`) con 80 % de penetración.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CODIGO = AQUI.parents[1]
if str(CODIGO) not in sys.path:
    sys.path.insert(0, str(CODIGO))

import httpx  # noqa: E402

CONTRATO = {"X-Contrato-Version": "1"}
TOKEN = "cifras-token"


def raiz_repo():
    return next((p for p in AQUI.parents if (p / ".git").exists()), None)


def ruta_contenedor(ruta: Path) -> str:
    return "/home/vanet/results/e-sert/" + ruta.resolve().relative_to(raiz_repo()).as_posix()


def percentil(xs, q):
    xs = sorted(xs)
    k = (len(xs) - 1) * q / 100
    i = int(k)
    return xs[i] + (xs[min(i + 1, len(xs) - 1)] - xs[i]) * (k - i)


def arrancar_backend(host: str = "127.0.0.1"):
    import logging

    import uvicorn

    from backend.api.main import Config, crear_app

    logging.disable(logging.INFO)
    raiz = raiz_repo()
    csv = raiz / "proyecto" / "sumo" / "parqueos" / "puestos.csv" if raiz else None
    app = crear_app(Config(db_url="sqlite:///:memory:", puestos_csv=str(csv) if csv and csv.exists() else None,
                           token_sim=TOKEN, visor_dir=None))
    with socket.socket() as s:
        s.bind(("", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning"))
    hilo = threading.Thread(target=server.run, daemon=True)
    hilo.start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(300):
        try:
            if httpx.get(f"{url}/salud", timeout=1).status_code == 200:
                return server, hilo, url, port
        except httpx.HTTPError:
            time.sleep(0.05)
    raise RuntimeError("el backend no arrancó")


def medir_latencia(url: str, n: int) -> dict:
    usuario = f"app_{uuid.uuid4()}"
    ahora = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    rutas = {
        "GET /puestos": lambda c: c.get("/puestos"),
        "GET /guia": lambda c: c.get("/guia", params={"lat": -2.896, "lon": -79.006,
                                                      "destino_lat": -2.8973, "destino_lon": -79.0045}),
        "POST /eventos/ubicacion": lambda c: c.post("/eventos/ubicacion", json={
            "usuario_id": usuario, "origen": "app", "ts": ahora, "lat": -2.8973, "lon": -79.0045}),
        "GET /billetera/{id}": lambda c: c.get(f"/billetera/{usuario}"),
    }
    por_ruta, todas = {}, []
    with httpx.Client(base_url=f"{url}/api/v1", headers=CONTRATO, timeout=10) as c:
        for nombre, pedir in rutas.items():
            for _ in range(20):  # calentamiento
                pedir(c)
            ms = []
            for _ in range(n):
                t0 = time.perf_counter()
                r = pedir(c)
                ms.append((time.perf_counter() - t0) * 1000)
                assert r.status_code < 300, (nombre, r.status_code, r.text[:200])
            por_ruta[nombre] = {"p50_ms": round(percentil(ms, 50), 2), "p95_ms": round(percentil(ms, 95), 2)}
            todas += ms
    return {"n_por_ruta": n, "p50_ms": round(percentil(todas, 50), 2), "p95_ms": round(percentil(todas, 95), 2),
            "por_ruta": por_ruta, "cliente": "httpx por loopback, un pedido a la vez"}


def correr_controlador(args_kpis: str, env: dict, timeout: float) -> str:
    cmd = ["docker", "exec", "-w", ruta_contenedor(CODIGO)]
    for k, v in env.items():
        cmd += ["-e", f"{k}={v}"]
    cmd += ["van3twin", "bash", "-lc", f"python3 -m traci.correr_kpis {args_kpis}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(r.stdout[-1500:] + r.stderr[-1500:])
    return r.stdout


def resumen_json(salida: str) -> dict:
    return json.loads(salida[salida.index("{\n"):])


def medir_ms_por_paso(hasta: float) -> dict:
    sufijo = "_cifras"
    try:
        r = resumen_json(correr_controlador(f"--id p80_rf_s1 --hasta {hasta} --sufijo {sufijo}", {}, 1800))
    finally:
        (CODIGO / "traci" / "salidas_kpi" / f"ejemplo_p80_rf_s1{sufijo}.json").unlink(missing_ok=True)
    return {"ms_por_paso": r["ms_por_paso"], "pasos": r["pasos"], "tiempo_real_s": r["tiempo_real_s"],
            "penetracion": r["porc_app"], "sesiones": r["sesiones_maquina"]["sesiones"],
            "libsumo": r["opciones"]["libsumo"], "hasta_s": hasta}


def medir_ws(url: str, port: int, hasta: float) -> dict:
    from websockets.sync.client import connect

    host = subprocess.run(["docker", "exec", "van3twin", "bash", "-lc",
                           "H=$(getent hosts host.docker.internal | awk '{print $1}'); "
                           "echo ${H:-$(ip route | awk '/default/{print $3}')}"],
                          capture_output=True, text=True).stdout.strip()
    tiempos, alto = [], threading.Event()

    def escuchar():
        with connect(url.replace("http", "ws", 1) + "/ws/estado?rol=visor") as ws:
            while not alto.is_set():
                try:
                    m = json.loads(ws.recv(timeout=0.5))
                    tiempos.append((time.monotonic(), m["tipo"]))
                except TimeoutError:
                    continue

    hilo = threading.Thread(target=escuchar, daemon=True)
    hilo.start()
    sufijo = "_cifras_ws"
    try:
        correr_controlador(f"--id p80_rf_s1 --hasta {hasta} --sufijo {sufijo} --ritmo 1 "
                           f"--publicar http://{host}:{port}", {"ESERT_TOKEN_SIM": TOKEN}, hasta * 3 + 600)
    finally:
        alto.set()
        hilo.join(timeout=5)
        (CODIGO / "traci" / "salidas_kpi" / f"ejemplo_p80_rf_s1{sufijo}.json").unlink(missing_ok=True)
    if len(tiempos) < 2:
        raise RuntimeError("el visor no recibió mensajes")
    # régimen estable: se descartan los primeros 10 s
    t0 = tiempos[0][0] + 10
    estables = [(t, k) for t, k in tiempos if t >= t0]
    dur = estables[-1][0] - estables[0][0]
    tipos = Counter(k for _, k in estables)
    return {"mensajes_por_s": round(len(estables) / dur, 2),
            "por_tipo_por_s": {k: round(v / dur, 2) for k, v in sorted(tipos.items())},
            "ventana_s": round(dur, 1), "ritmo": 1, "penetracion": 80, "cliente": "rol=visor"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sin-sumo", action="store_true")
    ap.add_argument("--n", type=int, default=300, help="pedidos por ruta para la latencia")
    ap.add_argument("--hasta-paso", type=float, default=900, help="segundos simulados para ms/paso")
    ap.add_argument("--hasta-ws", type=float, default=90, help="segundos (reales = simulados) para WS/s")
    args = ap.parse_args()

    cifras = {"fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), "maquina": os.uname().nodename if hasattr(os, "uname") else ""}
    server, hilo, url, port = arrancar_backend(host="0.0.0.0")
    try:
        cifras["latencia_api"] = medir_latencia(url, args.n)
        print("latencia API:", json.dumps(cifras["latencia_api"], ensure_ascii=False))
        if not args.sin_sumo:
            cifras["ws"] = medir_ws(url, port, args.hasta_ws)
            print("WS:", json.dumps(cifras["ws"], ensure_ascii=False))
    finally:
        server.should_exit = True
        hilo.join(timeout=10)
    if not args.sin_sumo:
        cifras["traci"] = medir_ms_por_paso(args.hasta_paso)
        print("TraCI:", json.dumps(cifras["traci"], ensure_ascii=False))
    cifras.pop("maquina", None)
    (AQUI / "cifras.json").write_text(json.dumps(cifras, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"→ {AQUI / 'cifras.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
