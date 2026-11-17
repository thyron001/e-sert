"""Fixtures de las pruebas de punta a punta (S4-1): backend real por HTTP/WS y SUMO en el contenedor.

- `servidor`: `uvicorn` de verdad en un hilo, en un puerto libre, con una SQLite temporal.
- `cliente`: `httpx.Client` contra ese servidor, con `X-Contrato-Version: 1`.
- `usuario_app` / `nuevo_usuario`: usuarios `app_<uuid4>`; la recarga pasa por el adaptador de
  Payphone de Miguel en modo `mock` si `backend/pagos/` existe, y si no por `POST /recarga`.
- `requiere_sumo`: salta limpio si el contenedor `van3twin` no responde y, al terminar, comprueba
  que no queden procesos `sumo` dentro del contenedor.

Correr: `pytest -m e2e` desde la carpeta que contiene `backend/` y `comun/`.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Optional

import httpx
import pytest

CONTRATO = {"X-Contrato-Version": "1"}
TOKEN = "e2e-token"
CONTENEDOR = "van3twin"
AQUI = Path(__file__).resolve()
CODIGO = AQUI.parents[3]  # carpeta que contiene backend/, comun/ y traci/


# --------------------------------------------------------------------------- rutas del repo


def raiz_repo() -> Optional[Path]:
    """La carpeta con `.git` (el repo e-sert), subiendo desde este archivo."""
    for p in AQUI.parents:
        if (p / ".git").exists():
            return p
    return None


def puestos_csv_real() -> Optional[Path]:
    """`proyecto/sumo/parqueos/puestos.csv` (los parkingAreas de Tyrone), si está en el repo."""
    raiz = raiz_repo()
    csv = raiz / "proyecto" / "sumo" / "parqueos" / "puestos.csv" if raiz else None
    return csv if csv and csv.is_file() else None


def ruta_en_contenedor(ruta: Path) -> Optional[str]:
    """Ruta equivalente dentro de `van3twin` (el repo está en `results/e-sert`, CLAUDE.md)."""
    raiz = raiz_repo()
    if raiz is None or raiz.parent.name != "results":
        return None
    return f"/home/vanet/results/{raiz.name}/" + ruta.resolve().relative_to(raiz).as_posix()


# --------------------------------------------------------------------------- contenedor


def docker(*args: str, timeout: float = 30) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)


def motivo_sin_sumo() -> Optional[str]:
    """None si `docker exec van3twin which sumo` funciona; si no, el motivo para saltar."""
    if shutil.which("docker") is None:
        return "no hay `docker` en esta máquina (¿falta la integración WSL de Docker Desktop?)"
    if ruta_en_contenedor(CODIGO) is None:
        return "el repo no está clonado en van3twin-docker/results/e-sert: el contenedor no lo ve"
    try:
        r = docker("exec", CONTENEDOR, "which", "sumo", timeout=20)
    except (OSError, subprocess.TimeoutExpired) as err:
        return f"docker no responde: {err}"
    if r.returncode != 0:
        return f"el contenedor {CONTENEDOR} no responde: {(r.stderr or r.stdout).strip()[:160]}"
    return None


def procesos_sumo() -> list:
    """PIDs de `sumo`/`sumo-gui` vivos en el contenedor."""
    r = docker("exec", CONTENEDOR, "bash", "-lc", "pgrep -x sumo; pgrep -x sumo-gui; true")
    return [p for p in r.stdout.split() if p.strip()]


def host_desde_contenedor() -> str:
    """Cómo ve el contenedor a esta computadora: `host.docker.internal` o la puerta de enlace."""
    cmd = ("HOST=$(getent hosts host.docker.internal | awk '{print $1}'); "
           "HOST=${HOST:-$(ip route | awk '/default/{print $3}')}; echo $HOST")
    return docker("exec", CONTENEDOR, "bash", "-lc", cmd).stdout.strip()


@pytest.fixture
def requiere_sumo() -> Iterator[None]:
    motivo = motivo_sin_sumo()
    if motivo:
        pytest.skip(f"sin SUMO: {motivo}")
    antes = set(procesos_sumo())
    yield
    fin = time.monotonic() + 10
    while (quedan := set(procesos_sumo()) - antes) and time.monotonic() < fin:
        time.sleep(0.5)
    assert not quedan, f"quedaron procesos sumo en el contenedor: {sorted(quedan)}"


# --------------------------------------------------------------------------- servidor


def puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@dataclass
class Servidor:
    url: str
    host: str
    port: int
    app: object
    token: str = TOKEN

    @property
    def ws(self) -> str:
        return self.url.replace("http://", "ws://", 1)


def _mini_puestos(ruta: Path) -> Path:
    """MOCK: 3 puestos junto al Parque Calderón, solo si falta `proyecto/sumo/parqueos/puestos.csv`."""
    ruta.write_text(
        "puesto_id,edge,lane,calle,capacidad,lat,lon,x,y\n"
        "pa_e2e_0,e0,e0_1,Simón Bolívar,1,-2.8972,-79.0046,0,0\n"
        "pa_e2e_1,e1,e1_1,Benigno Malo,2,-2.8978,-79.0040,0,0\n"
        "pa_e2e_2,e2,e2_1,Luis Cordero,3,-2.8968,-79.0035,0,0\n",
        encoding="utf-8")
    return ruta


@pytest.fixture
def arrancar_servidor(tmp_path) -> Iterator[Callable[..., Servidor]]:
    """Fábrica: `arrancar_servidor(host="0.0.0.0")` levanta un backend y lo apaga al final."""
    import uvicorn

    from backend.api.main import Config, crear_app

    vivos = []

    def arrancar(host: str = "127.0.0.1", puestos: Optional[Path] = None) -> Servidor:
        os.environ.setdefault("PAYPHONE_MODO", "mock")  # adaptador de Miguel sin credenciales
        csv = puestos or puestos_csv_real() or _mini_puestos(tmp_path / "puestos_mock.csv")
        db = tmp_path / f"e2e_{len(vivos)}.db"
        app = crear_app(Config(db_url=f"sqlite:///{db.as_posix()}", puestos_csv=str(csv), token_sim=TOKEN,
                               visor_dir=None, cors="*"))
        port = puerto_libre()
        server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning",
                                               lifespan="on"))
        hilo = threading.Thread(target=server.run, name=f"uvicorn-{port}", daemon=True)
        hilo.start()
        vivos.append((server, hilo))
        url = f"http://127.0.0.1:{port}"
        fin = time.monotonic() + 15
        while True:
            try:
                if httpx.get(f"{url}/api/v1/puestos", headers=CONTRATO, timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            assert time.monotonic() < fin and hilo.is_alive(), "el backend no arrancó en 15 s"
            time.sleep(0.05)
        return Servidor(url=url, host=host, port=port, app=app)

    yield arrancar
    for server, hilo in vivos:
        server.should_exit = True
    for server, hilo in vivos:
        hilo.join(timeout=10)
        assert not hilo.is_alive(), "uvicorn no se apagó"


@pytest.fixture
def servidor(arrancar_servidor) -> Servidor:
    return arrancar_servidor()


@pytest.fixture
def cliente(servidor) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=f"{servidor.url}/api/v1", headers=CONTRATO, timeout=10) as c:
        yield c


@pytest.fixture
def token_sim(servidor) -> dict:
    """Cabecera de las rutas 🔒 del controlador."""
    return {"X-Sim-Token": servidor.token}


# --------------------------------------------------------------------------- usuarios


class UsuarioApp:
    """Un usuario de la app (`app_<uuid4>`) con su billetera en el backend vivo."""

    def __init__(self, cliente: httpx.Client, servidor: Servidor):
        self.id = f"app_{uuid.uuid4()}"
        self.c = cliente
        self.servidor = servidor
        self.via = None

    def billetera(self) -> dict:
        r = self.c.get(f"/billetera/{self.id}")
        assert r.status_code == 200, r.text
        return r.json()

    def recargar(self, monto: float = 5.0) -> dict:
        """Recarga por Payphone (adaptador de Miguel, modo mock) o, sin él, por `POST /recarga`."""
        if getattr(self.servidor.app.state, "pagos_montado", False):
            self.via = "payphone_mock"
            r = self.c.post("/pagos/preparar", json={"usuario_id": self.id, "monto": monto})
            assert r.status_code == 201, r.text
            p = r.json()
            assert p["modo"] == "mock", p
            # El usuario aprueba en el formulario simulado; Payphone vuelve a /pagos/retorno.
            r = self.c.get("/pagos/mock/decidir", follow_redirects=True,
                           params={"id": p["payment_id"], "clientTransactionId": p["client_transaction_id"],
                                   "decision": "aprobar"})
            assert r.status_code == 200, r.text
            estado = self.c.get(f"/pagos/{p['client_transaction_id']}").json()
            assert estado["estado"] == "aprobado", estado
        else:
            # MOCK: reemplazar cuando backend/pagos (Miguel) esté junto a este backend; sin él se
            # recarga directo, con la referencia de prueba que el contrato admite.
            self.via = "recarga_directa"
            r = self.c.post(f"/billetera/{self.id}/recarga",
                            json={"monto": monto, "referencia_payphone": "PRUEBA"})
            assert r.status_code == 201, r.text
        return self.billetera()


@pytest.fixture
def nuevo_usuario(cliente, servidor) -> Callable[[], UsuarioApp]:
    """Fábrica de usuarios con saldo 0."""
    return lambda: UsuarioApp(cliente, servidor)


@pytest.fixture
def usuario_app(nuevo_usuario) -> UsuarioApp:
    """Usuario `app_<uuid4>` ya recargado con $5."""
    u = nuevo_usuario()
    b = u.recargar(5.0)
    assert b["saldo"] == pytest.approx(5.0)
    return u
