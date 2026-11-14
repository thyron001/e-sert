"""Prueba de humo de la demo, sin GUI (S4-1). También la usa la unificación.

    python demo/verificar_demo.py [--segundos 120] [--ritmo 20] [--ruta kpis=...] [--ruta visor=...]

Arranca `demo.py --local --sin-gui --sin-navegador`, escucha `/ws/estado` durante `--segundos` y
comprueba:

1. al menos 100 `snapshot` válidos contra `proyecto/comun/esquemas.py` y nunca más de 1 por segundo
   de simulación (t_sim estrictamente creciente);
2. `GET /api/v1/puestos` tiene tantos puestos como `sumo/parqueos/puestos.csv`;
3. al menos una sesión pasa a `CERRADA` (estado en el snapshot o recibo por `/ws/espejo`) y la
   billetera del auto seguido cumple `saldo = Σrecargas − Σdébitos` (saldo antes − cobrado = saldo
   después del cierre);
4. tras el apagado, los puertos del backend y del visor quedan libres y no quedan procesos `sumo`
   ni del controlador dentro del contenedor.

Sale con 0 si todo cumple (1 si no) y escribe `demo/verificacion.json`.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from demo import RAIZ, WINDOWS, docker, http_json, leer_config, puerto_libre  # noqa: E402

sys.path.insert(0, str(RAIZ / "proyecto"))


def esquemas():
    from comun import esquemas as e  # contrato (proyecto/comun/esquemas.py)

    return e


async def escuchar(url_ws: str, url_api: str, segundos: float, res: dict) -> None:
    """Snapshots por /ws/estado y, en paralelo, sigue por /ws/espejo a los candidatos."""
    import websockets

    e = esquemas()
    fin = time.time() + segundos
    seguidos: dict = {}
    tareas: list = []
    # solo los que están por cerrar: seguir a todos los estacionados frena al controlador (arma ruta y
    # detalle por cada espejo)
    POR_CERRAR = {"REGRESANDO", "SALIENDO"}

    def seguir(veh: str, candidato: bool = False) -> None:
        # candidatos (autos buscando): pocos, como el teléfono de la demo; cada espejo cuesta al controlador
        if veh in seguidos or (candidato and sum(seguidos.values()) >= 5):
            return
        seguidos[veh] = candidato
        tareas.append(asyncio.create_task(espejo(veh)))

    async def estado():
        async with websockets.connect(url_ws, max_size=None) as ws:
            t_ant = -1.0
            while time.time() < fin:
                try:
                    texto = await asyncio.wait_for(ws.recv(), timeout=max(0.1, fin - time.time()))
                except asyncio.TimeoutError:
                    break
                tipo = json.loads(texto).get("tipo")
                res["mensajes"][tipo] = res["mensajes"].get(tipo, 0) + 1
                if tipo != "snapshot":
                    continue
                try:
                    msg = e.MensajeSnapshot.model_validate_json(texto)
                except Exception as err:  # noqa: BLE001
                    res["snapshots_invalidos"] += 1
                    res["errores"].append(f"snapshot inválido: {str(err)[:200]}")
                    continue
                res["snapshots_validos"] += 1
                if msg.t_sim <= t_ant:
                    res["mas_de_1_por_s_sim"] += 1
                t_ant = msg.t_sim
                res["t_sim_ultimo"] = msg.t_sim
                for v in msg.vehiculos:
                    if v.estado is not None and v.estado.value == "CERRADA":
                        res["cerradas_en_snapshot"].add(v.id)
                    elif v.estado is not None and v.estado.value in POR_CERRAR:
                        seguir(v.id)  # con sesión abierta: su recibo llega por /ws/espejo al cerrar

    async def espejo(veh: str):
        try:
            async with websockets.connect(url_ws.replace("/ws/estado", f"/ws/espejo/{veh}"), max_size=None) as ws:
                saldo_antes = None  # último saldo visto antes del recibo (el débito se hace al cerrar)
                while time.time() < fin:
                    try:
                        m = json.loads(await asyncio.wait_for(ws.recv(), timeout=max(0.1, fin - time.time())))
                    except asyncio.TimeoutError:
                        return
                    if m.get("tipo") != "espejo":
                        return
                    b = m.get("billetera")
                    if m.get("recibo") is None and b:
                        saldo_antes = b["saldo"]
                    if m.get("recibo"):
                        r = m["recibo"]
                        caso = {"veh": veh, "saldo_antes": saldo_antes, "cobrado_usd": r["cobrado_usd"],
                                "saldo_despues": b["saldo"] if b else None, "minutos_cobrados": r["minutos_cobrados"]}
                        if saldo_antes is not None and b:
                            caso["cumple"] = abs(saldo_antes - r["cobrado_usd"] - b["saldo"]) < 0.011
                        res["recibos"].append(caso)
                        return
        except Exception as err:  # noqa: BLE001
            res["errores"].append(f"espejo {veh}: {err!r}"[:200])

    async def buscar_candidatos():
        while time.time() < fin - 5:
            try:
                for c in await asyncio.to_thread(http_json, url_api + "/espejo/candidatos", 3):
                    seguir(c["id"], candidato=True)
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(5)
        await asyncio.gather(*tareas, return_exceptions=True)

    await asyncio.gather(estado(), buscar_candidatos())
    res["seguidos_por_espejo"] = len(seguidos)


def contenedor_limpio(contenedor: str) -> dict:
    sumo = docker("exec", contenedor, "pgrep", "-l", "sumo").stdout.split()
    ctrl = docker("exec", contenedor, "pgrep", "-f", "kpis.correr_una --id .* --subdir demo_").stdout.split()
    return {"sumo": sumo, "controlador": ctrl}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--segundos", type=float, default=120)
    ap.add_argument("--ritmo", type=float, default=30, help="veces el tiempo real (tope; para ver cierres en 2 min)")
    ap.add_argument("--ruta", action="append", default=[])
    ap.add_argument("--salida", default=str(AQUI / "verificacion.json"))
    args = ap.parse_args(argv)
    cfg = leer_config(AQUI / "config_demo.yaml")
    puertos = cfg["puertos"]
    contenedor = cfg.get("contenedor", "van3twin")
    rutas = {k: RAIZ / v for k, v in cfg["rutas"].items()}
    for par in args.ruta:
        k, v = par.split("=", 1)
        rutas[k] = RAIZ / v

    res = {"mensajes": {}, "snapshots_validos": 0, "snapshots_invalidos": 0, "mas_de_1_por_s_sim": 0,
           "cerradas_en_snapshot": set(), "recibos": [], "errores": [], "t_sim_ultimo": None}
    cmd = [sys.executable, str(AQUI / "demo.py"), "--local", "--sin-gui", "--sin-navegador", "--ritmo", str(args.ritmo),
           "--cronometro"] + sum((["--ruta", r] for r in args.ruta), [])
    opciones = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if WINDOWS else {}
    t0 = time.time()
    demo = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **opciones)
    salida = []
    url_api = f"http://127.0.0.1:{puertos['backend']}/api/v1"
    try:
        for linea in demo.stdout:  # espera la tabla de arranque ("Ctrl+C para terminar")
            salida.append(linea)
            print(linea, end="")
            if "Ctrl+C para terminar" in linea or demo.poll() is not None:
                break
        res["arranque_s"] = round(time.time() - t0, 1)
        if demo.poll() is not None:
            raise RuntimeError("la demo terminó antes de estar lista")
        asyncio.run(escuchar(f"ws://127.0.0.1:{puertos['backend']}/ws/estado", url_api, args.segundos, res))
        n_api = len(http_json(url_api + "/puestos", timeout=5))
        with open(rutas["sumo"] / "parqueos" / "puestos.csv", encoding="utf-8") as f:
            n_csv = sum(1 for _ in csv.DictReader(f))
        res["puestos_api"], res["puestos_csv"] = n_api, n_csv
    except Exception as err:  # noqa: BLE001
        res["errores"].append(f"{err!r}"[:300])
    finally:
        t_ap = time.time()
        if demo.poll() is None:
            demo.send_signal(signal.CTRL_BREAK_EVENT if WINDOWS else signal.SIGINT)
            try:
                resto, _ = demo.communicate(timeout=40)
                salida.append(resto)
            except subprocess.TimeoutExpired:
                demo.kill()
        res["apagado_s"] = round(time.time() - t_ap, 1)
        time.sleep(1)

    res["puertos_libres"] = {str(p): puerto_libre(p) for p in (puertos["backend"], puertos["visor"])}
    res["contenedor_tras_apagar"] = contenedor_limpio(contenedor)
    res["cerradas_en_snapshot"] = sorted(res["cerradas_en_snapshot"])
    recibos_ok = [r for r in res["recibos"] if r.get("cumple")]
    criterios = {
        "snapshots_100_validos": res["snapshots_validos"] >= 100 and res["snapshots_invalidos"] == 0,
        "max_1_snapshot_por_s_sim": res["mas_de_1_por_s_sim"] == 0,
        "puestos_api_igual_csv": res.get("puestos_api") == res.get("puestos_csv") and res.get("puestos_api", 0) > 0,
        "sesion_cerrada": bool(res["cerradas_en_snapshot"] or res["recibos"]),
        "billetera_cuadra": bool(recibos_ok) and all(r.get("cumple", True) for r in res["recibos"]),
        "puertos_libres": all(res["puertos_libres"].values()),
        "sin_procesos_en_contenedor": not any(res["contenedor_tras_apagar"].values()),
    }
    res["criterios"] = criterios
    res["ok"] = all(criterios.values())
    res["fecha"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    res["segundos"], res["ritmo"] = args.segundos, args.ritmo
    Path(args.salida).write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"criterios": criterios, "ok": res["ok"]}, indent=1, ensure_ascii=False))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
