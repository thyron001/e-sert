"""Demo de e-sert en un solo comando: backend FastAPI, controlador TraCI con sumo-gui y visor (S4-1).

    python demo/demo.py                 # modo remoto (principal): publica en el VPS; si no responde, local
    python demo/demo.py --local         # plan B sin internet: backend uvicorn local + visor local
    python demo/demo.py --sin-gui --sin-navegador --ritmo 20     # lo que usa verificar_demo.py

Orden de arranque: (backend) → controlador (SUMO en el contenedor `van3twin`) → visor; comprueba que
cada pieza responde y, con Ctrl+C o al cerrar sumo-gui, apaga todo en orden inverso (también lo que
corre dentro del contenedor). Logs en `demo/logs/<AAAAMMDD-HHMMSS>/<componente>.log`.

Rutas: todas relativas a la raíz del repo (la carpeta con `CLAUDE.md`), leídas de
`demo/config_demo.yaml`; `--ruta visor=semanas/S4/Tyrone/codigo/visor` cambia una.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent            # .../demo
WINDOWS = platform.system() == "Windows"


def raiz_repo(desde: Path = AQUI) -> Path:
    for p in [desde, *desde.parents]:
        if (p / "CLAUDE.md").is_file():
            return p
    sys.exit("No encontré la raíz del repo (la carpeta con CLAUDE.md).")


RAIZ = raiz_repo()
# El contenedor monta `results/` en /home/vanet/results; el repo puede llamarse distinto de `e-sert`.
RAIZ_CONTENEDOR = f"/home/vanet/results/{RAIZ.name}"


# ------------------------------------------------------------------ utilidades

def leer_config(ruta: Path) -> dict:
    try:
        import yaml
    except ImportError:
        sys.exit("Falta PyYAML: pip install -r demo/requirements.txt")
    return yaml.safe_load(ruta.read_text(encoding="utf-8"))


def puerto_libre(puerto: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if not WINDOWS:
            # como uvicorn y http.server: las conexiones en TIME_WAIT de una demo anterior no bloquean
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", puerto))
            return True
        except OSError:
            return False


def ip_lan() -> str:
    """IP de la computadora en la red local (la que usan los teléfonos en modo --local)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def http_json(url: str, timeout: float = 2.0, cabeceras=None):
    req = urllib.request.Request(url, headers=dict({"X-Contrato-Version": "1"}, **(cabeceras or {})))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def esperar(cond, limite: float, cada: float = 0.5) -> bool:
    fin = time.time() + limite
    while time.time() < fin:
        try:
            if cond():
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(cada)
    return False


def docker(*args, timeout=30, check=False) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout, check=check)


def puerta_enlace_contenedor(contenedor: str) -> str:
    """Cómo ve el contenedor a la computadora: host.docker.internal o la puerta de enlace (Linux)."""
    r = docker("exec", contenedor, "bash", "-lc",
               "H=$(getent hosts host.docker.internal | awk '{print $1}'); "
               "H=${H:-$(ip route | awk '/default/{print $3}')}; echo $H")
    return r.stdout.strip() or "host.docker.internal"


def ruta_contenedor(ruta: Path) -> str:
    return RAIZ_CONTENEDOR + "/" + ruta.resolve().relative_to(RAIZ).as_posix()


def python_backend(dir_backend: Path) -> str:
    """El Python del `.venv` de la demo o del backend si tiene FastAPI; si no, el actual."""
    for venv in (AQUI / ".venv", dir_backend / ".venv"):
        exe = venv / ("Scripts/python.exe" if WINDOWS else "bin/python")
        if exe.exists():
            r = subprocess.run([str(exe), "-c", "import fastapi, uvicorn, sqlalchemy"], capture_output=True)
            if r.returncode == 0:
                return str(exe)
    return sys.executable


# ------------------------------------------------------------------ procesos

class Proceso:
    """Un componente: `Popen` en su propio grupo de procesos y su log."""

    def __init__(self, nombre: str, cmd: list, log: Path, cwd: Path = None, env: dict = None):
        self.nombre, self.cmd, self.log_path = nombre, cmd, log
        self.log = open(log, "w", encoding="utf-8", errors="replace")
        opciones = {"cwd": str(cwd) if cwd else None, "env": env, "stdout": self.log, "stderr": subprocess.STDOUT}
        if WINDOWS:
            opciones["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            opciones["start_new_session"] = True
        self.log.write("$ " + " ".join(map(str, cmd)) + "\n")
        self.log.flush()
        self.proc = subprocess.Popen([str(c) for c in cmd], **opciones)

    def vivo(self) -> bool:
        return self.proc.poll() is None

    def terminar(self, espera: float = 5.0) -> None:
        if self.vivo():
            try:
                if WINDOWS:
                    self.proc.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    os.killpg(self.proc.pid, signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass
            try:
                self.proc.wait(espera)
            except subprocess.TimeoutExpired:
                try:
                    if WINDOWS:
                        self.proc.kill()
                    else:
                        os.killpg(self.proc.pid, signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    pass
                self.proc.wait(5)
        self.log.close()


# ------------------------------------------------------------------ demo

class Demo:
    def __init__(self, args, cfg: dict):
        self.args, self.cfg = args, cfg
        self.rutas = {k: RAIZ / v for k, v in cfg["rutas"].items()}
        for par in args.ruta or []:
            k, v = par.split("=", 1)
            self.rutas[k] = RAIZ / v
        esc = dict(cfg["escenario"])
        if args.penetracion is not None:
            esc["penetracion"] = args.penetracion
        if args.semilla is not None:
            esc["semilla"] = args.semilla
        if args.clasificador:
            esc["clasificador"] = args.clasificador
        if args.ritmo is not None:
            esc["ritmo"] = args.ritmo
        if args.hasta is not None:
            esc["hasta_s"] = args.hasta
        pen = esc["penetracion"]
        esc["pen_pct"] = int(round(pen * 100 if pen <= 1 else pen))
        self.esc = esc
        self.id = f"p{esc['pen_pct']:02d}_{esc['clasificador']}_s{esc['semilla']}"
        self.puertos = cfg["puertos"]
        self.contenedor = cfg.get("contenedor", "van3twin")
        self.modo = "remoto" if args.remoto else "local"
        self.procesos: list[Proceso] = []
        self.tiempos: dict = {}
        self.t0 = time.time()
        sello = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.dir_logs = AQUI / "logs" / sello
        self.dir_logs.mkdir(parents=True, exist_ok=True)
        # sin guiones al inicio: pkill/pgrep leerían "--subdir" como una opción y no matarían nada
        self.patron_contenedor = f"subdir demo_{sello}"
        self.sello = sello
        self.cerrando = False
        self.captura_gui = self.dir_logs / "sumo_gui.png"
        self.url_visor = ""

    # --- mensajes ---
    def info(self, texto: str) -> None:
        linea = f"[demo {time.time() - self.t0:6.1f} s] {texto}"
        try:
            print(linea, flush=True)
        except (BrokenPipeError, OSError):
            pass  # la terminal ya no está (p. ej. tubería cerrada): el apagado sigue igual
        try:
            with open(self.dir_logs / "demo.log", "a", encoding="utf-8") as f:
                f.write(linea + "\n")
        except OSError:
            pass

    def fallar(self, texto: str, solucion: str) -> None:
        print(f"\n✗ {texto}\n  Solución: {solucion}\n", file=sys.stderr, flush=True)
        self.apagar()
        sys.exit(1)

    # --- prerrequisitos ---
    def prerrequisitos(self) -> None:
        if sys.version_info < (3, 11):
            self.fallar(f"Python {platform.python_version()}: se necesita 3.11 o más.",
                        "instala Python 3.11+ y crea demo/.venv con él (ver demo/README.md).")
        if shutil.which("docker") is None:
            self.fallar("No encuentro `docker`.", "instala Docker y arranca el stack van3twin-docker.")
        r = docker("ps", "--format", "{{.Names}}")
        if self.contenedor not in r.stdout.split():
            self.fallar(f"El contenedor `{self.contenedor}` no está corriendo.",
                        "en tu carpeta van3twin-docker: docker compose up -d van3twin")
        if not self.args.sin_gui and docker("exec", self.contenedor, "which", "sumo-gui").returncode != 0:
            self.fallar("El contenedor no tiene sumo-gui.", "usa --sin-gui o reconstruye la imagen van3twin.")
        if not self.args.sin_gui:
            self.pantalla_virtual()
        if RAIZ.parent.name != "results":
            self.fallar(f"El repo está en {RAIZ}, fuera de van3twin-docker/results/.",
                        "clona el repo dentro de van3twin-docker/results/ (el contenedor solo ve esa carpeta).")
        if not (self.rutas["kpis"] / "correr_una.py").exists():
            self.fallar(f"No existe {self.rutas['kpis'] / 'correr_una.py'}.",
                        "durante la semana: --ruta kpis=semanas/S4/Tyrone/codigo/kpis")
        puertos = [self.puertos["visor"]] + ([self.puertos["backend"]] if self.modo == "local" else [])
        for p in puertos:
            if not puerto_libre(p):
                self.fallar(f"El puerto {p} está ocupado.",
                            f"cierra lo que lo usa (Linux: `ss -ltnp | grep {p}`; Windows: "
                            f"`netstat -ano | findstr {p}`) o quedó una demo anterior: Ctrl+C en esa terminal.")
        # restos de una demo anterior dentro del contenedor
        docker("exec", self.contenedor, "pkill", "-f", "kpis.correr_una --id .* --subdir demo_")

    def pantalla_virtual(self) -> None:
        """sumo-gui necesita la pantalla :99 del contenedor (Xvfb) y el VNC del puerto 5901. El
        contenedor las arranca al iniciarse; si se cayeron, se relanzan con los mismos comandos."""
        if docker("exec", self.contenedor, "pgrep", "-x", "Xvfb").returncode == 0:
            return
        self.info("la pantalla virtual :99 del contenedor no está: relanzo Xvfb, fluxbox y x11vnc")
        docker("exec", "-d", self.contenedor, "bash", "-c",
               "Xvfb :99 -screen 0 1680x1050x24 +extension GLX +render -noreset >/dev/null 2>&1")
        time.sleep(1.5)
        docker("exec", "-d", self.contenedor, "bash", "-c", "DISPLAY=:99 fluxbox >/dev/null 2>&1")
        docker("exec", self.contenedor, "bash", "-c",
               "x11vnc -display :99 -nopw -forever -shared -rfbport 5900 -listen 0.0.0.0 -quiet -bg >/dev/null 2>&1")
        if docker("exec", self.contenedor, "pgrep", "-x", "Xvfb").returncode != 0:
            self.fallar("No hay pantalla :99 en el contenedor para sumo-gui.",
                        "reinicia el contenedor (docker compose restart van3twin) o usa --sin-gui.")

    def preparar_escenario(self) -> None:
        """Demanda de la semilla (ignorada por git) y RF exportado (si se pide rf)."""
        codigo = self.rutas["kpis"].parent
        rou = codigo / "sumo" / "escenarios" / f"app{self.esc['pen_pct']}_s{self.esc['semilla']}.rou.xml"
        if self.esc["pen_pct"] == 0:
            rou = rou.with_name(f"base_s{self.esc['semilla']}.rou.xml")
        if not rou.exists():
            self.info(f"genero la demanda de la semilla {self.esc['semilla']} (una sola vez)…")
            # generar_escenarios.py reescribe escenarios.json (versionado) solo con esta semilla:
            # se guarda y se restaura para no dejar el repo modificado.
            indice = codigo / "sumo" / "escenarios" / "escenarios.json"
            copia = indice.read_bytes() if indice.exists() else None
            r = docker("exec", "-w", ruta_contenedor(codigo / "sumo" / "escenarios"), self.contenedor, "bash", "-lc",
                       f"python3 generar_escenarios.py --semillas {self.esc['semilla']}", timeout=300)
            if copia is not None:
                indice.write_bytes(copia)
            if r.returncode != 0:
                self.fallar("No pude generar la demanda.", r.stderr[-500:])
        if self.esc["clasificador"] == "rf":
            npz = self.rutas["kpis"] / "externo" / "rf_final.plano.npz"
            versionado = RAIZ / "proyecto" / "ia" / "modelos" / "rf_final.plano.npz"
            if not npz.exists() and versionado.exists():
                npz = versionado  # S4-U final: el .npz está versionado; no hace falta sklearn
            self.npz = npz
            if not npz.exists():
                self.info("no está el RF exportado (kpis/externo/rf_final.plano.npz): intento exportarlo…")
                ok = self.exportar_rf(npz)
                if not ok:
                    self.info("⚠ sin RF exportado: la demo usa el clasificador de umbral "
                              "(ver demo/README.md, «RF en el contenedor»).")
                    self.esc["clasificador"] = "umbral"
                    self.id = self.id.replace("_rf_", "_umbral_")

    def exportar_rf(self, npz: Path) -> bool:
        candidatos = [self.rutas["kpis"] / "externo" / "ia" / "modelos" / "rf_final.joblib",
                      RAIZ / "proyecto" / "ia" / "modelos" / "rf_final.joblib"]
        joblib = next((c for c in candidatos if c.exists()), None)
        if joblib is None:
            return False
        for py in (RAIZ / "proyecto" / "ia" / ".venv" / ("Scripts/python.exe" if WINDOWS else "bin/python"),
                   Path(sys.executable)):
            if py.exists():
                npz.parent.mkdir(parents=True, exist_ok=True)
                r = subprocess.run([str(py), "-m", "kpis.modelo_plano", "exportar", "--joblib", str(joblib),
                                    "--salida", str(npz)], cwd=self.rutas["kpis"].parent, capture_output=True)
                if r.returncode == 0:
                    return True
        return False

    # --- componentes ---
    def arrancar_backend(self) -> None:
        if self.modo == "remoto":
            return
        t = time.time()
        db = (AQUI.parent / self.cfg["db"]).resolve()
        for extra in ("", "-wal", "-shm", "-journal"):
            Path(str(db) + extra).unlink(missing_ok=True)
        env = dict(os.environ)
        env.update({
            "PYTHONPATH": str(self.rutas["backend"].parent) + os.pathsep + env.get("PYTHONPATH", ""),
            "ESERT_DB_URL": f"sqlite:///{db.as_posix()}",
            "ESERT_VISOR_DIR": str(self.rutas["visor"]),
            "ESERT_PUESTOS_CSV": str(self.rutas["sumo"] / "parqueos" / "puestos.csv"),
        })
        py = python_backend(self.rutas["backend"])
        modulo = f"{self.rutas['backend'].name}.api.main:app"
        p = Proceso("backend", [py, "-m", "uvicorn", modulo, "--host", "0.0.0.0", "--port", str(self.puertos["backend"]),
                                "--log-level", "warning"], self.dir_logs / "backend.log", cwd=AQUI.parent, env=env)
        self.procesos.append(p)
        url = f"http://127.0.0.1:{self.puertos['backend']}/api/v1/puestos"
        if not esperar(lambda: p.vivo() and len(http_json(url)) > 0, 20, 0.5):
            self.fallar("El backend no respondió en 20 s (GET /api/v1/puestos).",
                        f"mira {p.log_path}; ¿faltan dependencias? pip install -r demo/requirements.txt")
        self.tiempos["backend"] = round(time.time() - t, 1)
        self.info(f"backend listo en {self.tiempos['backend']} s")

    def url_backend(self) -> str:
        if self.modo == "remoto":
            return self.cfg["remoto"]["url"]
        return f"http://127.0.0.1:{self.puertos['backend']}"

    def url_ws(self) -> str:
        return self.url_backend().replace("https://", "wss://").replace("http://", "ws://") + "/ws/estado"

    def arrancar_controlador(self) -> None:
        t = time.time()
        codigo = self.rutas["kpis"].parent
        if self.modo == "remoto":
            publicar = self.cfg["remoto"]["url"]
        else:
            publicar = f"http://{puerta_enlace_contenedor(self.contenedor)}:{self.puertos['backend']}"
        captura = os.path.relpath(self.dir_logs / "sumo_gui.png", codigo).replace(os.sep, "/")
        partes = [f"python3 -m kpis.correr_una --id {self.id} --duracion {self.esc['hasta_s']} --warmup 0",
                  f"--publicar {publicar}", f"--ritmo {self.esc['ritmo']}", f"--subdir demo_{self.sello}"]
        if getattr(self, "npz", None) is not None and self.esc["clasificador"] == "rf":
            partes.append(f"--modelo {os.path.relpath(self.npz, codigo).replace(os.sep, '/')}")
        if not self.args.sin_gui:
            partes += ["--gui", f"--delay-ms {self.esc.get('delay_ms', 0)}", f"--captura-gui {captura}"]
        else:
            partes += ["--libsumo"]  # sin GUI no hace falta el socket TraCI: SUMO dentro del proceso
        cmd = ["docker", "exec", "-w", ruta_contenedor(codigo)]
        if os.environ.get("ESERT_TOKEN_SIM"):
            cmd += ["-e", "ESERT_TOKEN_SIM"]
        cmd += [self.contenedor, "bash", "-lc", "exec " + " ".join(partes)]
        self.captura_gui = self.dir_logs / "sumo_gui.png"
        p = Proceso("controlador", cmd, self.dir_logs / "controlador.log")
        self.procesos.append(p)
        self.controlador = p
        if not self.esperar_snapshot(30):
            self.fallar("No llegó ningún snapshot por /ws/estado en 30 s.",
                        f"mira {p.log_path} (¿SUMO arrancó?, ¿el contenedor ve el backend en {publicar}? "
                        "En Windows, permite Python en el firewall de red privada).")
        self.tiempos["controlador"] = round(time.time() - t, 1)
        self.info(f"controlador y SUMO listos en {self.tiempos['controlador']} s (primer snapshot recibido)")

    def esperar_snapshot(self, limite: float) -> bool:
        import websockets

        async def uno():
            async with websockets.connect(self.url_ws(), open_timeout=5) as ws:
                while True:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=limite))
                    if msg.get("tipo") == "snapshot":
                        return True

        fin = time.time() + limite
        while time.time() < fin:
            if not self.controlador.vivo():
                return False
            try:
                return asyncio.run(asyncio.wait_for(uno(), timeout=max(1.0, fin - time.time())))
            except Exception:  # noqa: BLE001
                time.sleep(1)
        return False

    def arrancar_visor(self) -> None:
        t = time.time()
        if self.modo == "remoto":
            self.url_visor = self.cfg["remoto"]["url"] + "/visor/"
        else:
            p = Proceso("visor", [sys.executable, "-m", "http.server", str(self.puertos["visor"]), "--bind", "0.0.0.0",
                                  "--directory", str(self.rutas["visor"])], self.dir_logs / "visor.log")
            self.procesos.append(p)
            url = f"http://127.0.0.1:{self.puertos['visor']}/"
            if not esperar(lambda: urllib.request.urlopen(url, timeout=1).status == 200, 10, 0.3):
                self.fallar("El visor no respondió en 10 s.", f"mira {p.log_path}")
            self.url_visor = f"http://localhost:{self.puertos['visor']}/?ws={self.url_ws()}"
        self.tiempos["visor"] = round(time.time() - t, 1)
        if not self.args.sin_navegador:
            webbrowser.open(self.url_visor)
        self.info(f"visor listo en {self.tiempos['visor']} s: {self.url_visor}")

    # --- información para el público ---
    def resumen(self) -> None:
        total = round(time.time() - self.t0, 1)
        self.tiempos["total"] = total
        print("\n┌──────────────────────────────────────────────────────────────")
        print(f"│ e-sert · demo en modo {self.modo.upper()} · escenario {self.id} · ritmo {self.esc['ritmo']}×")
        print("├──────────────────────────────────────────────────────────────")
        print("│ Componente     Arranque")
        for k in ("backend", "controlador", "visor"):
            if k in self.tiempos:
                print(f"│ {k:<14} {self.tiempos[k]:>6.1f} s")
        print(f"│ {'TOTAL':<14} {total:>6.1f} s")
        print("├──────────────────────────────────────────────────────────────")
        print(f"│ Visor:            {self.url_visor}")
        if self.modo == "remoto":
            print(f"│ Teléfono espejo:  {self.cfg['remoto']['url']}  (Expo Go, modo espejo)")
        else:
            lan = ip_lan()
            print(f"│ Teléfono espejo:  http://{lan}:{self.puertos['backend']}  (misma red/hotspot)")
            print(f"│ Visor en la LAN:  http://{lan}:{self.puertos['backend']}/visor/")
        if not self.args.sin_gui:
            print("│ sumo-gui:         VNC en 127.0.0.1:5901 (cerrar sumo-gui también apaga la demo)")
        try:
            cand = http_json(self.url_backend() + "/api/v1/espejo/candidatos", timeout=3)[:5]
            texto = ", ".join(f"{c['id']} → {c['destino_nombre']}" for c in cand) or "todavía ninguno (esperar ~1 min)"
        except Exception as e:  # noqa: BLE001
            texto = f"no disponible ({e.__class__.__name__})"
        print(f"│ Candidatos espejo: {texto}")
        print(f"│ Logs:             {self.dir_logs.relative_to(RAIZ)}")
        print("└──────────────────────────────────────────────────────────────  Ctrl+C para terminar\n",
              flush=True)

    def cronometro(self, **extra) -> None:
        if not self.args.cronometro:
            return
        datos = {"modo": self.modo, "id": self.id, "ritmo": self.esc["ritmo"], "gui": not self.args.sin_gui,
                 "arranque_s": {k: v for k, v in self.tiempos.items()}, **extra}
        (self.dir_logs / "tiempos.json").write_text(json.dumps(datos, indent=1, ensure_ascii=False), encoding="utf-8")

    # --- apagado ---
    def apagar(self) -> None:
        if self.cerrando:
            return
        self.cerrando = True
        t = time.time()
        self.info("apagando en orden inverso…")
        for p in reversed(self.procesos):
            try:
                self._apagar_uno(p)
            except Exception as e:  # noqa: BLE001  (un fallo no deja vivos a los demás)
                self.info(f"  error al detener {p.nombre}: {e!r}")
        self.tiempos["apagado"] = round(time.time() - t, 1)

    def _apagar_uno(self, p: "Proceso") -> None:
        if p.nombre == "controlador":
            # matar `docker exec` no detiene lo que corre dentro del contenedor
            docker("exec", self.contenedor, "pkill", "-INT", "-f", self.patron_contenedor)
            fin = time.time() + 5
            while time.time() < fin and docker("exec", self.contenedor, "pgrep", "-f",
                                               self.patron_contenedor).returncode == 0:
                time.sleep(0.3)
            docker("exec", self.contenedor, "pkill", "-9", "-f", self.patron_contenedor)
            docker("exec", self.contenedor, "pkill", "-9", "-f", f"salidas/demo_{self.sello}/")
        p.terminar()
        self.info(f"  {p.nombre} detenido")


    # --- bucle principal ---
    def correr(self) -> int:
        self.prerrequisitos()
        if self.modo == "remoto":
            url = self.cfg["remoto"]["url"] + "/salud"
            espera = float(self.cfg["remoto"].get("salud_s", 5))
            if not esperar(lambda: http_json(url, timeout=espera).get("ok"), espera, 1):
                self.info(f"⚠ el VPS no respondió /salud en {espera:.0f} s: paso a --local (plan B)")
                self.modo = "local"
                self.prerrequisitos()
            elif not os.environ.get("ESERT_TOKEN_SIM"):
                # sin token el VPS rechaza los snapshots (401): mejor el plan B local que una demo vacía
                self.info("⚠ falta ESERT_TOKEN_SIM en el entorno (el VPS rechazaría los snapshots con 401): "
                          "paso a --local (plan B). Defínelo en .env o en el entorno para el modo remoto.")
                self.modo = "local"
                self.prerrequisitos()
        self.preparar_escenario()
        self.arrancar_backend()
        self.arrancar_controlador()
        self.arrancar_visor()
        self.resumen()
        t_listo = time.time()
        motivo = "ctrl+c"
        try:
            while True:
                if not self.controlador.vivo():
                    motivo = "sumo-gui cerrado o fin de la simulación"
                    break
                if any(not p.vivo() for p in self.procesos):
                    caido = next(p.nombre for p in self.procesos if not p.vivo())
                    motivo = f"se cayó {caido}"
                    break
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        demo_s = round(time.time() - t_listo, 1)
        self.info(f"fin: {motivo}")
        self.apagar()
        self.cronometro(demo_s=demo_s, apagado_s=self.tiempos.get("apagado"), motivo_fin=motivo,
                        captura_gui=str(self.captura_gui.relative_to(RAIZ)) if self.captura_gui.exists() else None)
        self.info(f"demo cerrada (apagado en {self.tiempos.get('apagado')} s). Logs: {self.dir_logs.relative_to(RAIZ)}")
        return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Demo de e-sert en un comando")
    modo = ap.add_mutually_exclusive_group()
    modo.add_argument("--remoto", action="store_true", default=True,
                      help="(por defecto) publica en el VPS; si /salud no responde en 5 s, pasa a --local")
    modo.add_argument("--local", action="store_true", help="plan B sin internet: backend y visor locales")
    ap.add_argument("--config", default=str(AQUI / "config_demo.yaml"))
    ap.add_argument("--ruta", action="append", help="componente=ruta relativa a la raíz (p. ej. visor=...)")
    ap.add_argument("--sin-gui", action="store_true", help="SUMO sin GUI")
    ap.add_argument("--sin-navegador", action="store_true")
    ap.add_argument("--penetracion", type=float, default=None, help="0.5 o 50")
    ap.add_argument("--semilla", type=int, default=None)
    ap.add_argument("--clasificador", choices=["rf", "umbral"], default=None)
    ap.add_argument("--ritmo", type=float, default=None, help="veces el tiempo real (1 = en vivo)")
    ap.add_argument("--hasta", type=float, default=None, help="segundo de simulación final")
    ap.add_argument("--cronometro", action="store_true", help="escribe logs/<sello>/tiempos.json")
    args = ap.parse_args(argv)
    if args.local:
        args.remoto = False
    demo = Demo(args, leer_config(Path(args.config)))
    # Ctrl+C (SIGINT) y SIGTERM terminan la demo igual, aunque se haya lanzado en segundo plano
    signal.signal(signal.SIGINT, signal.default_int_handler)
    if not WINDOWS:
        signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    else:
        signal.signal(signal.SIGBREAK, signal.default_int_handler)
    try:
        return demo.correr()
    except KeyboardInterrupt:
        demo.apagar()
        return 0
    except SystemExit:
        raise
    except Exception:
        demo.apagar()
        raise


if __name__ == "__main__":
    sys.exit(main())
