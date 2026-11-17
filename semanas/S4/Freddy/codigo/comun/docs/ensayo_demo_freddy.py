"""Ensayo de la demo desde el lado de Freddy (backend + controlador TraCI), S4-3.

    python comun/docs/ensayo_demo_freddy.py            # desde la carpeta con backend/, comun/, traci/
    python comun/docs/ensayo_demo_freddy.py --grafica  # solo rehace la gráfica con el último ensayo

La demo de Tyrone (`demo/`) no está publicada (no existe `origin/tyrone/s4`), así que se lanza como la
describe `docs/DESPLIEGUE.md`: backend `uvicorn` en la computadora (`--host 0.0.0.0`, con el visor en
`/visor`) y el controlador `traci.correr_kpis --publicar` en el contenedor `van3twin`. Pruebas:

1. Arranque en frío y tiempo hasta el primer `snapshot` en el visor.
2. Reinicio del backend en mitad de la demo: ¿el controlador sigue publicando? ¿vuelven los snapshots?
3. El teléfono espejo pierde el WS y se reconecta: mismo vehículo, sesión abierta, recibo una sola vez.
4. 80 % de penetración con `sumo-gui`: ms por paso con y sin GUI (y captura de `sumo-gui`).
5. Ctrl+C: ¿quedan procesos o puertos ocupados?

Escribe `comun/docs/ensayo/eventos.jsonl`, `resultados.json`, los logs y `captura_sumo_gui.png`.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional

AQUI = Path(__file__).resolve().parent
CODIGO = AQUI.parents[1]
SALIDA = AQUI / "ensayo"
if str(CODIGO) not in sys.path:
    sys.path.insert(0, str(CODIGO))

import httpx  # noqa: E402

TOKEN = "ensayo-token"
CONTENEDOR = "van3twin"
RITMO = 5           # la demo en vivo usa 1; 5 acorta el ensayo y mantiene el mismo flujo
HASTA_DEMO = 1500   # s simulados de la corrida principal
ID_DEMO = "p50_rf_s1"
VIGILAR_STDIN = True  # False reproduce el hallazgo: Ctrl+C deja vivos el controlador y sumo


def raiz_repo() -> Path:
    return next(p for p in CODIGO.parents if (p / ".git").exists())


def en_contenedor(ruta: Path) -> str:
    return "/home/vanet/results/e-sert/" + ruta.resolve().relative_to(raiz_repo()).as_posix()


class Registro:
    """Eventos con hora relativa al inicio del ensayo (para la línea de tiempo)."""

    def __init__(self, nombre: str = "eventos.jsonl"):
        self.t0 = time.monotonic()
        self.eventos: List[dict] = []
        self.lock = threading.Lock()
        SALIDA.mkdir(parents=True, exist_ok=True)
        self.archivo = (SALIDA / nombre).open("w", encoding="utf-8")

    def ahora(self) -> float:
        return round(time.monotonic() - self.t0, 2)

    def __call__(self, fuente: str, evento: str, incidente: bool = False, **extra) -> dict:
        e = {"t": self.ahora(), "fuente": fuente, "evento": evento, "incidente": incidente, **extra}
        with self.lock:
            self.eventos.append(e)
            self.archivo.write(json.dumps(e, ensure_ascii=False) + "\n")
            self.archivo.flush()
        print(f"[{e['t']:7.2f}] {fuente:12} {'⚠ ' if incidente else ''}{evento}", flush=True)
        return e


def leer_log(proc: subprocess.Popen, archivo: Path, reg: Registro, fuente: str, interesantes) -> threading.Thread:
    """Copia la salida del proceso a un archivo y registra las líneas interesantes como eventos."""

    def bucle():
        with archivo.open("a", encoding="utf-8") as f:
            for linea in iter(proc.stdout.readline, ""):
                f.write(f"[{reg.ahora():8.2f}] {linea}")
                f.flush()
                texto = linea.strip()
                for clave, incidente in interesantes:
                    if clave in texto:
                        reg(fuente, texto[:120], incidente=incidente)
                        break

    h = threading.Thread(target=bucle, daemon=True)
    h.start()
    return h


# --------------------------------------------------------------------------- piezas


class Backend:
    def __init__(self, reg: Registro, port: int, db: Path):
        self.reg, self.port, self.db, self.proc = reg, port, db, None
        self.url = f"http://127.0.0.1:{port}"
        self.log = "backend.log"

    def arrancar(self) -> float:
        raiz = raiz_repo()
        env = {**os.environ, "ESERT_DB_URL": f"sqlite:///{self.db.as_posix()}", "ESERT_TOKEN_SIM": TOKEN,
               "ESERT_PUESTOS_CSV": str(raiz / "proyecto" / "sumo" / "parqueos" / "puestos.csv"),
               "ESERT_VISOR_DIR": str(raiz / "proyecto" / "visor"), "PYTHONUNBUFFERED": "1"}
        t = time.monotonic()
        self.proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.api.main:app", "--host", "0.0.0.0",
                                      "--port", str(self.port), "--log-level", "info"], cwd=CODIGO, env=env,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        leer_log(self.proc, SALIDA / self.log, self.reg, "backend",
                 [("Traceback", True), ("ERROR", True), ("Application startup complete", False),
                  ("Shutting down", False), ("e-sert API", False)])
        while True:
            try:
                if httpx.get(f"{self.url}/salud", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.05)
            if time.monotonic() - t > 30:
                raise RuntimeError("el backend no arrancó en 30 s")
        dt = round(time.monotonic() - t, 2)
        self.reg("backend", f"responde /salud ({dt} s)", arranque_s=dt)
        return dt

    def detener(self, sig=signal.SIGTERM) -> float:
        t = time.monotonic()
        self.proc.send_signal(sig)
        try:
            self.proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.reg("backend", "no se detuvo en 15 s: kill", incidente=True)
        return round(time.monotonic() - t, 2)


class Controlador:
    def __init__(self, reg: Registro, nombre: str, args: str, backend_host: Optional[str] = None):
        self.reg, self.nombre, self.args, self.host, self.proc = reg, nombre, args, backend_host, None

    def arrancar(self):
        # `-i` + `--vigilar-stdin`: si este lanzador muere (Ctrl+C), se cierra stdin y el controlador se
        # detiene solo; `docker exec` sin TTY no reenvía la señal (hallazgo del ensayo S4-3).
        vigilar = " --vigilar-stdin" if VIGILAR_STDIN else ""
        cmd = ["docker", "exec", "-i", "-w", en_contenedor(CODIGO), "-e", f"ESERT_TOKEN_SIM={TOKEN}",
               "-e", "PYTHONUNBUFFERED=1", CONTENEDOR, "bash", "-lc",
               f"exec python3 -m traci.correr_kpis {self.args}{vigilar}"]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True)
        leer_log(self.proc, SALIDA / f"{self.nombre}.log", self.reg, "controlador",
                 [("Traceback", True), ("Error", True), ("rror:", True), ("t=", False), ("ms_por_paso", False)])
        self.reg("controlador", f"lanzado: correr_kpis {self.args.split(' --publicar')[0]}"
                                f"{' --vigilar-stdin' if VIGILAR_STDIN else ''}")

    def vivo(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def salida(self) -> str:
        return (SALIDA / f"{self.nombre}.log").read_text(encoding="utf-8", errors="replace")


def procesos_contenedor() -> List[str]:
    r = subprocess.run(["docker", "exec", CONTENEDOR, "bash", "-lc",
                        "pgrep -af 'traci.correr_kpis' | grep -v pgrep; pgrep -a -x sumo; pgrep -a -x sumo-gui; true"],
                       capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if l.strip() and "bash -lc" not in l]


def host_desde_contenedor() -> str:
    return subprocess.run(["docker", "exec", CONTENEDOR, "bash", "-lc",
                           "H=$(getent hosts host.docker.internal | awk '{print $1}'); "
                           "echo ${H:-$(ip route | awk '/default/{print $3}')}"],
                          capture_output=True, text=True).stdout.strip()


def capturar_visor(reg: Registro, host: str, port: int) -> bool:
    """Captura `/visor` con Chromium headless (Playwright) dentro del contenedor, con la demo corriendo."""
    destino = en_contenedor(SALIDA / "captura_visor.png")
    script = (
        "from playwright.sync_api import sync_playwright\n"
        "with sync_playwright() as p:\n"
        "    b = p.chromium.launch()\n"
        "    pg = b.new_page(viewport={'width': 1280, 'height': 800})\n"
        f"    pg.goto('http://{host}:{port}/visor/', wait_until='networkidle')\n"
        "    pg.wait_for_timeout(6000)\n"
        f"    pg.screenshot(path='{destino}')\n"
        "    b.close()\n")
    r = subprocess.run(["docker", "exec", CONTENEDOR, "python3", "-c", script], capture_output=True, text=True,
                       timeout=120)
    ok = r.returncode == 0 and (SALIDA / "captura_visor.png").is_file()
    reg("visor", "captura del visor" if ok else f"captura del visor falló: {r.stderr.strip()[-120:]}",
        incidente=not ok)
    return ok


def puerto_libre_ahora(port: int) -> bool:
    """True si nadie escucha en el puerto (conexión rechazada) y se puede volver a abrir como uvicorn
    (`SO_REUSEADDR`). Un `bind` sin esa opción falla por las conexiones en TIME_WAIT de los clientes WS
    aunque el servidor ya no exista: fue un falso positivo en el primer ensayo."""
    with socket.socket() as c:
        c.settimeout(1)
        if c.connect_ex(("127.0.0.1", port)) == 0:
            return False
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


class Visor(threading.Thread):
    """Cliente `/ws/estado?rol=visor` que se reconecta solo; registra el primer snapshot y los cortes."""

    def __init__(self, reg: Registro, url_ws: str):
        super().__init__(daemon=True)
        self.reg, self.url, self.alto = reg, f"{url_ws}/ws/estado?rol=visor", threading.Event()
        self.snapshots: List[tuple] = []  # (t, t_sim)
        self.primero = threading.Event()
        self.conectado = threading.Event()

    def run(self):
        from websockets.sync.client import connect

        while not self.alto.is_set():
            try:
                with connect(self.url, open_timeout=3) as ws:
                    self.conectado.set()
                    self.reg("visor", "WS /ws/estado conectado")
                    while not self.alto.is_set():
                        try:
                            m = json.loads(ws.recv(timeout=0.5))
                        except TimeoutError:
                            continue
                        if m["tipo"] == "snapshot":
                            self.snapshots.append((self.reg.ahora(), m["t_sim"]))
                            if not self.primero.is_set():
                                self.primero.set()
                                self.reg("visor", f"primer snapshot (t_sim={m['t_sim']})")
            except Exception as err:  # noqa: BLE001 — se registra y se reintenta
                if self.conectado.is_set():
                    self.conectado.clear()
                    self.reg("visor", f"WS cortado: {type(err).__name__}", incidente=False)
                time.sleep(0.5)

    def snapshot_despues(self, t: float, timeout: float) -> Optional[float]:
        fin = time.monotonic() + timeout
        while time.monotonic() < fin:
            for ts, _ in self.snapshots:
                if ts > t:
                    return ts
            time.sleep(0.1)
        return None


# --------------------------------------------------------------------------- pruebas


def prueba_espejo(reg: Registro, url: str, ventana_s: float = 60) -> dict:
    """El teléfono sigue un vehículo, pierde el WS y se reconecta al mismo."""
    from websockets.exceptions import ConnectionClosed
    from websockets.sync.client import connect

    url_ws = url.replace("http", "ws", 1)
    res = {"prueba": "espejo_reconexion"}
    fin = time.monotonic() + ventana_s
    veh = None
    with httpx.Client(base_url=f"{url}/api/v1", timeout=5) as c:
        while time.monotonic() < fin and veh is None:
            cands = c.get("/espejo/candidatos").json()
            if cands:
                veh = cands[0]["id"]
            else:
                time.sleep(0.5)
    if veh is None:
        reg("espejo", "sin candidatos en 60 s", incidente=True)
        return {**res, "resultado": "sin candidatos"}
    reg("espejo", f"sigue a {veh}")
    mensajes: List[dict] = []

    def leer(ws, hasta: float, cortar_en_sesion: bool):
        while time.monotonic() < hasta:
            try:
                m = json.loads(ws.recv(timeout=0.5))
            except TimeoutError:
                continue
            except ConnectionClosed:
                return "cerrado"
            mensajes.append({**m, "_t": reg.ahora()})
            if m["tipo"] == "espejo_fin":
                return "fin"
            if cortar_en_sesion and m.get("sesion"):
                return "con_sesion"
            if not cortar_en_sesion and m.get("recibo"):
                pass
        return "tiempo"

    with connect(f"{url_ws}/ws/espejo/{veh}") as ws:
        motivo = leer(ws, time.monotonic() + 90, cortar_en_sesion=True)
    sesion_antes = next((m["sesion"] for m in reversed(mensajes) if m.get("sesion")), None)
    reg("espejo", f"WS del teléfono cortado a propósito ({motivo}; sesión {bool(sesion_antes)})", incidente=False)
    time.sleep(3)
    n_antes = len(mensajes)
    with connect(f"{url_ws}/ws/espejo/{veh}") as ws:
        reg("espejo", f"reconectado a {veh}")
        motivo2 = leer(ws, time.monotonic() + 150, cortar_en_sesion=False)
    despues = mensajes[n_antes:]
    sesion_despues = next((m["sesion"] for m in despues if m.get("sesion")), None)
    recibos = sum(1 for m in mensajes if m.get("recibo"))
    estados = [m.get("estado") for m in mensajes if m["tipo"] == "espejo"]
    mismo_vehiculo = all(m.get("veh_id") == veh for m in mensajes)
    id_antes = (sesion_antes or {}).get("sesion_id")
    id_despues = (sesion_despues or {}).get("sesion_id")
    ok = mismo_vehiculo and recibos <= 1 and (id_antes is None or id_despues in (None, id_antes))
    reg("espejo", f"fin seguimiento ({motivo2}): recibos={recibos}, misma sesión={id_antes == id_despues}",
        incidente=not ok)
    return {**res, "veh": veh, "mensajes": len(mensajes), "mensajes_tras_reconexion": len(despues),
            "sesion_antes": id_antes, "sesion_despues": id_despues, "recibos": recibos,
            "ultimo_estado": estados[-1] if estados else None, "mismo_vehiculo": mismo_vehiculo,
            "fin": motivo2, "ok": ok}


def ensayo_principal(reg: Registro) -> dict:
    resultados = {}
    with socket.socket() as s:
        s.bind(("", 0))
        port = s.getsockname()[1]
    db = SALIDA / "ensayo.db"
    db.unlink(missing_ok=True)
    backend = Backend(reg, port, db)
    resultados["arranque_backend_s"] = backend.arrancar()
    visor = Visor(reg, backend.url.replace("http", "ws", 1))
    visor.start()
    visor.conectado.wait(10)
    host = host_desde_contenedor()
    ctrl = Controlador(reg, "controlador_demo",
                       f"--id {ID_DEMO} --hasta {HASTA_DEMO} --ritmo {RITMO} --sufijo _ensayo "
                       f"--publicar http://{host}:{port}")
    t_lanza = reg.ahora()
    ctrl.arrancar()

    # 1. arranque en frío
    ok = visor.primero.wait(180)
    t_primero = next((t for t, _ in visor.snapshots), None)
    resultados["arranque_frio"] = {"prueba": "arranque_frio", "ok": ok,
                                   "s_hasta_primer_snapshot": None if not ok else round(t_primero - t_lanza, 2)}
    if not ok:
        reg("ensayo", "no llegó ningún snapshot en 180 s", incidente=True)

    resultados["captura_visor"] = capturar_visor(reg, host, port)

    # 3. espejo (antes del reinicio, que borra el registro en memoria del espejo)
    resultados["espejo"] = prueba_espejo(reg, backend.url)

    # 2. reinicio del backend
    reg("ensayo", "reinicio del backend (SIGTERM)", incidente=True)
    t_corte = reg.ahora()
    resultados_reinicio = {"prueba": "reinicio_backend", "detener_s": backend.detener()}
    time.sleep(5)
    vivo_durante = ctrl.vivo()
    resultados_reinicio["arranque_s"] = backend.arrancar()
    t_vuelta = visor.snapshot_despues(reg.ahora(), 60)
    resultados_reinicio.update({
        "controlador_vivo_tras_corte": vivo_durante and ctrl.vivo(),
        "s_sin_snapshots": None if t_vuelta is None else round(t_vuelta - t_corte, 2),
        "snapshots_vuelven": t_vuelta is not None,
        "ok": vivo_durante and ctrl.vivo() and t_vuelta is not None})
    if t_vuelta is not None:
        reg("visor", f"snapshots de nuevo tras {resultados_reinicio['s_sin_snapshots']} s")
    else:
        reg("visor", "no vuelven los snapshots tras el reinicio", incidente=True)
    resultados["reinicio_backend"] = resultados_reinicio
    time.sleep(15)

    # 5. Ctrl+C
    resultados["ctrl_c"] = prueba_ctrl_c(reg, ctrl, backend, port)
    visor.alto.set()
    resultados["snapshots_recibidos"] = len(visor.snapshots)
    return resultados


def prueba_ctrl_c(reg: Registro, ctrl: Controlador, backend: Backend, port: int) -> dict:
    res = {"prueba": "ctrl_c"}
    # a) Ctrl+C a `docker exec` sin TTY (como lo lanza un script): ¿llega la señal al contenedor?
    reg("ensayo", "Ctrl+C (SIGINT) al `docker exec` del controlador", incidente=True)
    ctrl.proc.send_signal(signal.SIGINT)
    try:
        ctrl.proc.stdin.close()  # al morir el lanzador, su extremo de stdin se cierra
    except OSError:
        pass
    try:
        ctrl.proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass
    time.sleep(3)
    quedan = procesos_contenedor()
    res["procesos_tras_sigint_docker_exec"] = quedan
    if quedan:
        reg("contenedor", f"siguen vivos {len(quedan)} procesos tras Ctrl+C", incidente=True)
        # b) Ctrl+C dentro del contenedor (lo que hace una terminal con -it)
        t = time.monotonic()
        subprocess.run(["docker", "exec", CONTENEDOR, "pkill", "-INT", "-f", "traci.correr_kpis"])
        fin = time.monotonic() + 20
        while procesos_contenedor() and time.monotonic() < fin:
            time.sleep(0.5)
        res["procesos_tras_sigint_en_contenedor"] = procesos_contenedor()
        res["s_para_salir_con_sigint_interno"] = round(time.monotonic() - t, 2)
        reg("contenedor", f"SIGINT dentro del contenedor: quedan {len(res['procesos_tras_sigint_en_contenedor'])}",
            incidente=bool(res["procesos_tras_sigint_en_contenedor"]))
        if res["procesos_tras_sigint_en_contenedor"]:
            subprocess.run(["docker", "exec", CONTENEDOR, "pkill", "-KILL", "-f", "traci.correr_kpis"])
            subprocess.run(["docker", "exec", CONTENEDOR, "pkill", "-KILL", "-x", "sumo"])
    else:
        reg("contenedor", "Ctrl+C: no quedan procesos")
    # Ctrl+C al backend
    reg("ensayo", "Ctrl+C (SIGINT) al backend")
    res["backend_detener_s"] = backend.detener(signal.SIGINT)
    res["backend_codigo_salida"] = backend.proc.returncode
    time.sleep(1)
    res["puerto_libre"] = puerto_libre_ahora(port) and backend.proc.poll() is not None
    reg("backend", f"puerto {port} {'libre' if res['puerto_libre'] else 'OCUPADO'}", incidente=not res["puerto_libre"])
    res["ok"] = not res.get("procesos_tras_sigint_en_contenedor") and res["puerto_libre"]
    res["ok_sin_tty"] = not quedan
    return res


def solo_ctrl_c(reg: Registro) -> dict:
    """Prueba 5 aislada: backend + controlador publicando, primer snapshot y Ctrl+C."""
    with socket.socket() as s:
        s.bind(("", 0))
        port = s.getsockname()[1]
    db = SALIDA / "ensayo_ctrl_c.db"
    db.unlink(missing_ok=True)
    backend = Backend(reg, port, db)
    backend.log = "backend_ctrl_c.log"
    backend.arrancar()
    visor = Visor(reg, backend.url.replace("http", "ws", 1))
    visor.start()
    ctrl = Controlador(reg, "controlador_ctrl_c", f"--id {ID_DEMO} --hasta {HASTA_DEMO} --ritmo {RITMO} "
                       f"--sufijo _ensayo_c --publicar http://{host_desde_contenedor()}:{port}")
    ctrl.arrancar()
    visor.primero.wait(120)
    time.sleep(20)
    res = prueba_ctrl_c(reg, ctrl, backend, port)
    visor.alto.set()
    (CODIGO / "traci" / "salidas_kpi" / f"ejemplo_{ID_DEMO}_ensayo_c.json").unlink(missing_ok=True)
    return res


def prueba_gui(reg: Registro) -> dict:
    """80 % de penetración: ms por paso sin GUI y con `sumo-gui` (pantalla :99), 600 s simulados."""
    res = {"prueba": "p80_gui", "hasta_s": 600}
    captura = en_contenedor(SALIDA / "captura_sumo_gui.png")
    for modo, extra in (("sin_gui", ""), ("con_gui", f" --gui --captura {captura}@450")):
        c = Controlador(reg, f"controlador_{modo}", f"--id p80_rf_s1 --hasta 600 --sufijo _ensayo_{modo}{extra}")
        c.arrancar()
        c.proc.wait(timeout=1800)
        texto = c.salida()
        ms = None
        for linea in texto.splitlines():
            if '"ms_por_paso"' in linea:
                ms = float(linea.split(":")[-1].strip(" ,"))
                break
        res[modo] = {"ms_por_paso": ms, "codigo_salida": c.proc.returncode}
        reg("controlador", f"p80 {modo}: {ms} ms/paso", incidente=c.proc.returncode != 0)
        (CODIGO / "traci" / "salidas_kpi" / f"ejemplo_p80_rf_s1_ensayo_{modo}.json").unlink(missing_ok=True)
    ms_gui = (res.get("con_gui") or {}).get("ms_por_paso")
    res["fluido_a_ritmo_1"] = ms_gui is not None and ms_gui < 1000
    res["captura"] = (SALIDA / "captura_sumo_gui.png").is_file()
    res["ok"] = res["fluido_a_ritmo_1"] and res["captura"]
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--grafica", action="store_true", help="solo la gráfica del último ensayo")
    ap.add_argument("--sin-gui", action="store_true", help="omite la prueba 4")
    ap.add_argument("--solo-gui", action="store_true", help="solo la prueba 4")
    ap.add_argument("--solo-ctrl-c", action="store_true", help="solo la prueba 5 (arranca backend y controlador)")
    args = ap.parse_args()
    if args.grafica:
        from comun.docs.grafica_ensayo import graficar  # noqa: WPS433

        graficar()
        return 0
    previo = json.loads((SALIDA / "resultados.json").read_text()) if (SALIDA / "resultados.json").is_file() else {}
    if not (args.solo_gui or args.solo_ctrl_c):
        for nombre in ("backend.log", "controlador_demo.log", "controlador_sin_gui.log", "controlador_con_gui.log"):
            (SALIDA / nombre).unlink(missing_ok=True)
    elif args.solo_ctrl_c:
        (SALIDA / "controlador_ctrl_c.log").unlink(missing_ok=True)
    reg = Registro("eventos_ctrl_c.jsonl" if args.solo_ctrl_c else
                   "eventos_gui.jsonl" if args.solo_gui else "eventos.jsonl")
    if args.solo_gui:
        resultados = {**previo, "p80_gui": prueba_gui(reg)}
    elif args.solo_ctrl_c:
        resultados = {**previo, "ctrl_c_primer_ensayo": previo.get("ctrl_c_primer_ensayo", previo.get("ctrl_c")),
                      "ctrl_c": solo_ctrl_c(reg)}
    else:
        resultados = ensayo_principal(reg)
        if not args.sin_gui:
            resultados["p80_gui"] = prueba_gui(reg)
    resultados["fecha"] = time.strftime("%Y-%m-%d %H:%M")
    (SALIDA / "resultados.json").write_text(json.dumps(resultados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(resultados, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
