"""Lanza y detiene la simulación de la demo (SUMO + controlador TraCI) junto al backend.

En el VPS la imagen trae SUMO 1.12, así que el backend corre `python3 -m kpis.correr_una` como
subproceso y el controlador publica en el propio backend (`http://127.0.0.1:<puerto>`) con
`ESERT_TOKEN_SIM`. Solo puede haber una corrida a la vez.

El proceso se lanza en su propio grupo (`start_new_session`) y se detiene con SIGINT, como un
Ctrl+C: así el controlador cierra SUMO limpio. Si en 15 s no terminó, SIGKILL al grupo entero,
para que no quede SUMO vivo publicando.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

PROYECTO = Path(__file__).resolve().parents[2]          # .../proyecto
NOMBRES_PEN = {20: "app20", 50: "app50", 80: "app80"}
ESPERA_SIGINT_S = 15.0


@dataclass
class Escenario:
    penetracion: int = 50
    semilla: int = 2
    ritmo: float = 2.0
    hasta_s: int = 3600
    clasificador: str = "rf"

    @property
    def id(self) -> str:
        return f"p{self.penetracion:02d}_{self.clasificador}_s{self.semilla}"


@dataclass
class Estado:
    disponible: bool
    motivo: Optional[str]
    corriendo: bool
    fase: str                                   # inactiva | preparando | corriendo | deteniendo
    escenario: Optional[Escenario] = None
    inicio: Optional[str] = None
    fin: Optional[str] = None
    codigo_salida: Optional[int] = None
    ultimas_lineas: List[str] = field(default_factory=list)


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class GestorSimulacion:
    """Una corrida de la demo a la vez. Seguro entre hilos (lo llaman las rutas de FastAPI)."""

    def __init__(self, url_backend: str, token_sim: Optional[str], proyecto: Path = PROYECTO,
                 python: str = sys.executable, dir_logs: Optional[Path] = None,
                 lanzar: Callable[..., subprocess.Popen] = subprocess.Popen):
        self.url_backend = url_backend
        self.token_sim = token_sim
        self.proyecto = Path(proyecto)
        self.python = python
        self.dir_logs = Path(dir_logs or os.environ.get("ESERT_DIR_LOGS_DEMO", "/tmp/esert-demo"))
        self._lanzar = lanzar
        self._cerrojo = threading.RLock()
        self._proc: Optional[subprocess.Popen] = None
        self._fase = "inactiva"
        self._escenario: Optional[Escenario] = None
        self._inicio: Optional[str] = None
        self._fin: Optional[str] = None
        self._codigo: Optional[int] = None
        self._log: Optional[Path] = None

    # ------------------------------------------------------------------ disponibilidad
    def motivo_no_disponible(self) -> Optional[str]:
        if not (self.proyecto / "kpis" / "correr_una.py").is_file():
            return "esta instalación no trae el código de la simulación (kpis/correr_una.py)"
        if shutil.which("sumo") is None and not os.environ.get("SUMO_HOME"):
            return "no hay SUMO en este servidor"
        return None

    # ------------------------------------------------------------------ estado
    def _refrescar(self) -> None:
        if self._proc is not None and self._fase in ("corriendo", "deteniendo"):
            rc = self._proc.poll()
            if rc is not None:
                self._codigo = rc
                self._fin = _ahora()
                self._fase = "inactiva"
                self._proc = None

    def corriendo(self) -> bool:
        with self._cerrojo:
            self._refrescar()
            return self._fase != "inactiva"

    def estado(self) -> Estado:
        with self._cerrojo:
            self._refrescar()
            motivo = self.motivo_no_disponible()
            return Estado(disponible=motivo is None, motivo=motivo, corriendo=self._fase != "inactiva",
                          fase=self._fase, escenario=self._escenario, inicio=self._inicio, fin=self._fin,
                          codigo_salida=self._codigo, ultimas_lineas=self._cola_log())

    def _cola_log(self, n: int = 8) -> List[str]:
        if not self._log or not self._log.exists():
            return []
        try:
            lineas = self._log.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []
        return [l[:300] for l in lineas[-n:]]

    # ------------------------------------------------------------------ iniciar
    def iniciar(self, esc: Escenario) -> Estado:
        """Arranca la corrida en segundo plano. Lanza RuntimeError si ya hay una o si no se puede."""
        with self._cerrojo:
            self._refrescar()
            motivo = self.motivo_no_disponible()
            if motivo:
                raise LookupError(motivo)
            if self._fase != "inactiva":
                raise RuntimeError("ya hay una simulación en curso")
            self._fase = "preparando"
            self._escenario = esc
            self._inicio = _ahora()
            self._fin = None
            self._codigo = None
            self.dir_logs.mkdir(parents=True, exist_ok=True)
            self._log = self.dir_logs / f"demo_{datetime.now():%Y%m%d_%H%M%S}.log"
        threading.Thread(target=self._preparar_y_lanzar, args=(esc,), daemon=True).start()
        return self.estado()

    @staticmethod
    def pantalla() -> Optional[str]:
        """`:99` si el contenedor tiene la pantalla virtual de `arranque.sh` (sumo-gui por noVNC)."""
        if os.environ.get("ESERT_GUI", "1") != "1":
            return None
        return ":99" if Path("/tmp/.X11-unix/X99").exists() else None

    def _env(self) -> dict:
        env = dict(os.environ)
        env.setdefault("SUMO_HOME", "/usr/share/sumo")
        if self.pantalla():
            env["DISPLAY"] = self.pantalla()
            env.setdefault("ESERT_VISTA_GUI", "sumo/demanda/vista_vps.xml")
        if self.token_sim:
            env["ESERT_TOKEN_SIM"] = self.token_sim
        return env

    def _demanda(self, esc: Escenario) -> Path:
        return self.proyecto / "sumo" / "escenarios" / f"{NOMBRES_PEN[esc.penetracion]}_s{esc.semilla}.rou.xml"

    def _preparar_y_lanzar(self, esc: Escenario) -> None:
        log = self._log
        assert log is not None
        try:
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"[{_ahora()}] escenario {esc.id}, ritmo {esc.ritmo}, hasta {esc.hasta_s} s\n")
                if not self._demanda(esc).exists():
                    f.write(f"[{_ahora()}] genero la demanda de la semilla {esc.semilla}…\n")
                    f.flush()
                    self._generar_demanda(esc, f)
                cmd = [self.python, "-u", "-m", "kpis.correr_una", "--id", esc.id,
                       "--duracion", str(esc.hasta_s), "--warmup", "0",
                       "--publicar", self.url_backend, "--ritmo", str(esc.ritmo),
                       "--subdir", f"demo_vps_{datetime.now():%Y%m%d_%H%M%S}"]
                modelo = self.proyecto / "ia" / "modelos" / "rf_final.plano.npz"
                if esc.clasificador == "rf" and modelo.exists():
                    cmd += ["--modelo", "ia/modelos/rf_final.plano.npz"]
                if self.pantalla():
                    cmd += ["--gui"]               # sumo-gui en :99, visible en sumo.tesisucuenca.com
                f.write(f"[{_ahora()}] {' '.join(cmd)}\n")
                f.flush()
            salida = open(log, "a", encoding="utf-8")
            with self._cerrojo:
                if self._fase != "preparando":     # la detuvieron mientras se preparaba
                    salida.close()
                    return
                self._proc = self._lanzar(cmd, cwd=str(self.proyecto), env=self._env(), stdout=salida,
                                          stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                          start_new_session=True)
                self._fase = "corriendo"
            salida.close()                         # el hijo conserva su copia del descriptor
        except Exception as exc:  # noqa: BLE001 - se informa en el estado
            with self._cerrojo:
                self._fase = "inactiva"
                self._fin = _ahora()
                self._codigo = -1
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"[{_ahora()}] error al lanzar: {exc}\n")

    def _generar_demanda(self, esc: Escenario, f) -> None:
        """`generar_escenarios.py` reescribe `escenarios.json`: se guarda y se restaura."""
        carpeta = self.proyecto / "sumo" / "escenarios"
        indice = carpeta / "escenarios.json"
        copia = indice.read_bytes() if indice.exists() else None
        try:
            r = subprocess.run([self.python, "generar_escenarios.py", "--semillas", str(esc.semilla)],
                               cwd=str(carpeta), env=self._env(), stdout=f, stderr=subprocess.STDOUT,
                               timeout=300)
        finally:
            if copia is not None:
                indice.write_bytes(copia)
        if r.returncode != 0:
            raise RuntimeError(f"generar_escenarios.py salió con {r.returncode}")

    # ------------------------------------------------------------------ detener
    def detener(self, espera_s: float = ESPERA_SIGINT_S) -> Estado:
        with self._cerrojo:
            self._refrescar()
            if self._fase == "preparando":
                self._fase = "inactiva"
                self._fin = _ahora()
                return self.estado()
            proc = self._proc
            if proc is None:
                return self.estado()
            self._fase = "deteniendo"
        self._senal(proc, signal.SIGINT)
        limite = time.monotonic() + espera_s
        while proc.poll() is None and time.monotonic() < limite:
            time.sleep(0.2)
        if proc.poll() is None:
            self._senal(proc, signal.SIGKILL)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        return self.estado()

    @staticmethod
    def _senal(proc: subprocess.Popen, sig: int) -> None:
        try:
            os.killpg(os.getpgid(proc.pid), sig)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                proc.send_signal(sig)
            except Exception:  # noqa: BLE001
                pass
