"""Ensayo cronometrado de la demo desde arranque en frío (S4-3).

    demo/.venv/bin/python demo/presentacion/ensayo.py --vuelta 1 --grabar demo/plan_b/snapshots_demo.jsonl
    demo/.venv/bin/python demo/presentacion/ensayo.py --vuelta 2

Fases (las del guion):

1. **arranque**: `demo.py --local --cronometro` (con sumo-gui) hasta la tabla de arranque;
2. **demo guiada**: un "teléfono" sigue por `/ws/espejo` a los candidatos, como hace el modo espejo
   de la app de Miguel (sin teléfono real en esta máquina; es el mismo canal que usa la app). El
   visor (Chromium *headless*, como el proyector) se abre con `?espejo=<veh>` y se comprueba el halo.
   La fase termina cuando una sesión seguida pasa a `CERRADA` y llega su recibo;
3. **apagado**: Ctrl+C (SIGINT) hasta que todo queda libre.

En la vuelta con `--grabar`, los mensajes de `/ws/estado` de los primeros `--grabar-s` segundos van a
un `.jsonl` para el plan B (`python -m visor.servidor_prueba --snapshots ...`). Escribe
`demo/presentacion/ensayos/ensayo_<n>.json` con los tiempos, los eventos y los tropiezos detectados.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import signal
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
DEMO = AQUI.parent
sys.path.insert(0, str(DEMO))
from demo import RAIZ, docker, http_json, leer_config, puerto_libre  # noqa: E402

PRESUPUESTO = {"arranque": 60, "demo_guiada": 300, "apagado": 15}


async def demo_guiada(base_http: str, base_ws: str, url_visor_base: str, limite: float, grabar: Path | None,
                      grabar_s: float, ev: list, t0: float) -> dict:
    import websockets

    fin = time.time() + limite
    estado = {"recibo": None, "seguidos": [], "visor": None, "grabados": 0}

    def evento(texto):
        ev.append({"t": round(time.time() - t0, 1), "evento": texto})
        print(f"  [{time.time() - t0:6.1f} s] {texto}", flush=True)

    async def grabar_ws():
        if not grabar:
            return
        grabar.parent.mkdir(parents=True, exist_ok=True)
        hasta = time.time() + grabar_s
        async with websockets.connect(base_ws + "/ws/estado", max_size=None) as ws:
            with open(grabar, "w", encoding="utf-8") as f:
                while time.time() < min(hasta, fin + 60):
                    try:
                        texto = await asyncio.wait_for(ws.recv(), timeout=5)
                    except asyncio.TimeoutError:
                        continue
                    f.write(texto.strip() + "\n")
                    estado["grabados"] += 1
        import gzip
        import shutil

        with open(grabar, "rb") as fi, gzip.open(grabar.with_name(grabar.name + ".gz"), "wb", compresslevel=9) as fo:
            shutil.copyfileobj(fi, fo)  # el .jsonl crudo pasa de 100 MB: se versiona el .gz
        evento(f"grabación del plan B: {estado['grabados']} mensajes en {grabar.name}(.gz)")

    async def telefono(veh):
        try:
            async with websockets.connect(f"{base_ws}/ws/espejo/{veh}", max_size=None) as ws:
                while time.time() < fin and estado["recibo"] is None:
                    try:
                        m = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                    except asyncio.TimeoutError:
                        continue
                    if m.get("tipo") == "espejo_fin":
                        return
                    if m.get("recibo"):
                        estado["recibo"] = {"veh": veh, **m["recibo"], "billetera": m.get("billetera")}
                        evento(f"sesión de {veh} CERRADA con recibo: cobrado ${m['recibo']['cobrado_usd']} "
                               f"(tarjeta SERT ${m['recibo']['tarjeta_sert_usd']})")
                        return
        except Exception as e:  # noqa: BLE001
            evento(f"espejo {veh}: {e!r}"[:120])

    tareas = []

    def seguir(veh, motivo):
        if veh in estado["seguidos"] or len(estado["seguidos"]) >= 12:
            return
        estado["seguidos"].append(veh)
        if len(estado["seguidos"]) == 1 or motivo.startswith("vuelve"):
            evento(f"el teléfono espejo sigue a {veh} ({motivo})")
        tareas.append(asyncio.create_task(telefono(veh)))

    async def elegir_y_seguir():
        while time.time() < fin and estado["recibo"] is None:
            try:
                cand = await asyncio.to_thread(http_json, base_http + "/api/v1/espejo/candidatos", 3)
            except Exception:  # noqa: BLE001
                cand = []
            for c in cand[:2]:  # el teléfono sigue a pocos autos, como en la demo
                seguir(c["id"], f"destino {c['destino_nombre']}, {c['estado']}")
            await asyncio.sleep(3)
        for t in tareas:
            t.cancel()

    async def por_cerrar():
        """Como haría Miguel en vivo: elegir un auto cuyo conductor ya vuelve (REGRESANDO), que cerrará pronto."""
        async with websockets.connect(base_ws + "/ws/estado", max_size=None) as ws:
            while time.time() < fin and estado["recibo"] is None:
                try:
                    m = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                except asyncio.TimeoutError:
                    continue
                if m.get("tipo") != "snapshot":
                    continue
                for v in m.get("vehiculos", []):
                    if v.get("estado") in ("REGRESANDO", "SALIENDO"):
                        seguir(v["id"], f"vuelve a su auto, t_sim = {m.get('t_sim')}")

    async def visor():
        while not estado["seguidos"] and time.time() < fin:
            await asyncio.sleep(1)
        if not estado["seguidos"]:
            return
        veh = estado["seguidos"][0]
        estado["visor"] = await asyncio.to_thread(revisar_visor, f"{url_visor_base}&espejo={veh}", veh)
        evento(f"visor: halo del espejo {'visible' if estado['visor'].get('halo') else 'NO visible'}, "
               f"ruta {estado['visor'].get('ruta')} puntos, puesto {estado['visor'].get('puesto')}")

    await asyncio.gather(grabar_ws(), elegir_y_seguir(), por_cerrar(), visor())
    return estado


def revisar_visor(url: str, veh: str) -> dict:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception:  # noqa: BLE001
            exe = sorted((Path.home() / ".cache" / "ms-playwright").glob("chromium-*/chrome-linux*/chrome"))[-1]
            b = p.chromium.launch(executable_path=str(exe))
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        pg.goto(url + "&presentacion=1")
        r = {"halo": False}
        try:
            pg.wait_for_function(f"(window.visorEspejosVisibles || []).includes({json.dumps(veh)})", timeout=45000)
            pg.wait_for_function("window.visorEspejoPuesto !== undefined", timeout=20000)
            r = {"halo": True, "ruta": pg.evaluate("window.visorEspejoRuta"),
                 "puesto": pg.evaluate("window.visorEspejoPuesto")}
        except Exception as e:  # noqa: BLE001
            r["error"] = repr(e)[:160]
        b.close()
    return r


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vuelta", type=int, required=True)
    ap.add_argument("--ritmo", type=float, default=10, help="veces el tiempo real durante el ensayo")
    ap.add_argument("--grabar", default=None)
    ap.add_argument("--grabar-s", type=float, default=300)
    ap.add_argument("--limite-demo", type=float, default=PRESUPUESTO["demo_guiada"])
    ap.add_argument("--ruta", action="append", default=[])
    args = ap.parse_args(argv)
    cfg = leer_config(DEMO / "config_demo.yaml")
    pb, pv = cfg["puertos"]["backend"], cfg["puertos"]["visor"]
    tropiezos, eventos = [], []
    t0 = time.time()
    cmd = [sys.executable, str(DEMO / "demo.py"), "--local", "--cronometro", "--sin-navegador", "--ritmo",
           str(args.ritmo)] + sum((["--ruta", r] for r in args.ruta), [])
    print(f"Ensayo {args.vuelta}: arranque en frío ({' '.join(cmd[1:])})", flush=True)
    demo = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    dir_logs = None
    for linea in demo.stdout:
        print(linea, end="")
        if "Logs:" in linea:
            dir_logs = RAIZ / linea.split("Logs:")[1].strip()
        if "Ctrl+C para terminar" in linea or demo.poll() is not None:
            break
    t_listo = time.time()
    if demo.poll() is not None:
        tropiezos.append("la demo no arrancó (ver logs)")
        estado = {}
    else:
        eventos.append({"t": round(t_listo - t0, 1), "evento": "demo lista (tabla de arranque)"})
        estado = asyncio.run(demo_guiada(f"http://127.0.0.1:{pb}", f"ws://127.0.0.1:{pb}",
                                         f"http://localhost:{pv}/?ws=ws://127.0.0.1:{pb}/ws/estado",
                                         args.limite_demo, Path(args.grabar) if args.grabar else None,
                                         args.grabar_s, eventos, t0))
    t_fin_guiada = time.time()
    demo.send_signal(signal.SIGINT)
    try:
        demo.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        demo.kill()
        tropiezos.append("el apagado tardó más de 60 s: kill()")
    t_apagado = time.time() - t_fin_guiada
    time.sleep(1)
    tiempos = json.loads((dir_logs / "tiempos.json").read_text(encoding="utf-8")) if dir_logs and \
        (dir_logs / "tiempos.json").exists() else {}
    fases = {"arranque": round(t_listo - t0, 1), "demo_guiada": round(t_fin_guiada - t_listo, 1),
             "apagado": round(t_apagado, 1)}
    if not estado.get("recibo"):
        tropiezos.append(f"ninguna sesión seguida cerró en {args.limite_demo:.0f} s de demo guiada")
    if estado.get("visor") and not estado["visor"].get("halo"):
        tropiezos.append(f"el visor no mostró el halo: {estado['visor']}")
    for fase, s in fases.items():
        if s > PRESUPUESTO[fase]:
            tropiezos.append(f"{fase}: {s} s supera el presupuesto de {PRESUPUESTO[fase]} s")
    limpieza = {"puertos_libres": all(puerto_libre(p) for p in (pb, pv)),
                "sumo_gui": docker("exec", cfg.get("contenedor", "van3twin"), "pgrep", "-l", "sumo-gui").stdout.split()}
    if not limpieza["puertos_libres"] or limpieza["sumo_gui"]:
        tropiezos.append(f"limpieza incompleta: {limpieza}")
    salida = {"vuelta": args.vuelta, "fecha": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "ritmo": args.ritmo,
              "fases_s": fases, "presupuesto_s": PRESUPUESTO, "arranque_componentes_s": tiempos.get("arranque_s"),
              "eventos": eventos, "recibo": estado.get("recibo"), "visor": estado.get("visor"),
              "seguidos": estado.get("seguidos"), "grabados_plan_b": estado.get("grabados"),
              "limpieza": limpieza, "tropiezos": tropiezos, "logs": str(dir_logs.relative_to(RAIZ)) if dir_logs else None}
    destino = AQUI / "ensayos" / f"ensayo_{args.vuelta}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(salida, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"fases_s": fases, "tropiezos": tropiezos}, indent=1, ensure_ascii=False))
    return 0 if not tropiezos else 1


if __name__ == "__main__":
    sys.exit(main())
