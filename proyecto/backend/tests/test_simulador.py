"""Demo en el servidor: `/api/v1/demo/*` y `GestorSimulacion`.

El "controlador" es un `sleep` real en su propio grupo de procesos: así se prueba de verdad que
detener manda SIGINT al grupo, sin lanzar SUMO ni tocar el proceso de pytest.
"""

from __future__ import annotations

import subprocess
import time

import pytest
from fastapi.testclient import TestClient

from backend.api.main import Config, crear_app
from backend.simulador.gestor import Escenario, GestorSimulacion

CLAVE = "clave-de-prueba"


def proyecto_falso(tmp_path):
    (tmp_path / "kpis").mkdir(parents=True)
    (tmp_path / "kpis" / "correr_una.py").write_text("# falso\n")
    (tmp_path / "sumo" / "escenarios").mkdir(parents=True)
    (tmp_path / "sumo" / "escenarios" / "app50_s2.rou.xml").write_text("<routes/>\n")
    return tmp_path


class Lanzador:
    """Guarda el comando pedido y lanza en su lugar un proceso inofensivo."""

    def __init__(self, programa=("sleep", "30")):
        self.programa = list(programa)
        self.comandos = []
        self.kwargs = []

    def __call__(self, cmd, **kw):
        self.comandos.append(cmd)
        self.kwargs.append(kw)
        return subprocess.Popen(self.programa, **kw)


def esperar(cond, s=5.0):
    fin = time.monotonic() + s
    while time.monotonic() < fin:
        if cond():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    monkeypatch.setenv("SUMO_HOME", "/usr/share/sumo")
    lanz = Lanzador()
    g = GestorSimulacion("http://127.0.0.1:8000", "token-sim", proyecto=proyecto_falso(tmp_path / "p"),
                         python="python3", dir_logs=tmp_path / "logs", lanzar=lanz)
    yield g, lanz
    if g.corriendo():
        g.detener(espera_s=2)


def cliente(g, clave=CLAVE):
    app = crear_app(Config(db_url="sqlite:///:memory:", clave_demo=clave))
    app.state.simulador = g
    return TestClient(app)


def test_estado_publico_inactiva(entorno):
    g, _ = entorno
    with cliente(g) as c:
        r = c.get("/api/v1/demo/estado")
    assert r.status_code == 200
    d = r.json()
    assert d["disponible"] is True and d["corriendo"] is False and d["fase"] == "inactiva"


def test_sin_clave_en_el_servidor_no_se_puede_iniciar(entorno):
    g, lanz = entorno
    with cliente(g, clave=None) as c:
        est = c.get("/api/v1/demo/estado").json()
        r = c.post("/api/v1/demo/iniciar", headers={"X-Clave-Demo": "lo-que-sea"})
    assert est["disponible"] is False and "ESERT_CLAVE_DEMO" in est["motivo"]
    assert r.status_code == 503 and r.json()["error"]["codigo"] == "DEMO_NO_DISPONIBLE"
    assert lanz.comandos == []


@pytest.mark.parametrize("cabeceras", [{}, {"X-Clave-Demo": "otra"}])
def test_clave_incorrecta_401(entorno, cabeceras):
    g, lanz = entorno
    with cliente(g) as c:
        r = c.post("/api/v1/demo/iniciar", headers=cabeceras)
        r2 = c.post("/api/v1/demo/detener", headers=cabeceras)
    assert r.status_code == 401 and r.json()["error"]["codigo"] == "CLAVE_DEMO_INVALIDA"
    assert r2.status_code == 401
    assert lanz.comandos == []


def test_iniciar_lanza_el_controlador_contra_el_propio_backend(entorno):
    g, lanz = entorno
    with cliente(g) as c:
        r = c.post("/api/v1/demo/iniciar", headers={"X-Clave-Demo": CLAVE},
                   json={"penetracion": 50, "semilla": 2, "ritmo": 1, "hasta_s": 600})
        assert r.status_code == 202
        assert esperar(lambda: g.estado().fase == "corriendo")
        d = c.get("/api/v1/demo/estado").json()
    assert d["corriendo"] is True and d["escenario"]["id"] == "p50_rf_s2"
    cmd = lanz.comandos[0]
    assert cmd[cmd.index("-m") + 1] == "kpis.correr_una"
    assert cmd[cmd.index("--publicar") + 1] == "http://127.0.0.1:8000"
    assert cmd[cmd.index("--duracion") + 1] == "600" and cmd[cmd.index("--ritmo") + 1] == "1.0"
    kw = lanz.kwargs[0]
    assert kw["start_new_session"] is True and kw["env"]["ESERT_TOKEN_SIM"] == "token-sim"


def test_solo_una_corrida_a_la_vez(entorno):
    g, lanz = entorno
    with cliente(g) as c:
        assert c.post("/api/v1/demo/iniciar", headers={"X-Clave-Demo": CLAVE}).status_code == 202
        assert esperar(lambda: g.estado().fase == "corriendo")
        r = c.post("/api/v1/demo/iniciar", headers={"X-Clave-Demo": CLAVE})
    assert r.status_code == 409 and r.json()["error"]["codigo"] == "DEMO_EN_CURSO"
    assert len(lanz.comandos) == 1


def test_detener_manda_sigint_al_grupo(entorno):
    g, _ = entorno
    with cliente(g) as c:
        c.post("/api/v1/demo/iniciar", headers={"X-Clave-Demo": CLAVE})
        assert esperar(lambda: g.estado().fase == "corriendo")
        proc = g._proc
        r = c.post("/api/v1/demo/detener", headers={"X-Clave-Demo": CLAVE})
    assert r.status_code == 200
    d = r.json()
    assert d["corriendo"] is False and d["fase"] == "inactiva"
    assert proc.poll() is not None
    assert d["codigo_salida"] == -2  # SIGINT


def test_parametros_fuera_de_rango_422(entorno):
    g, lanz = entorno
    with cliente(g) as c:
        r = c.post("/api/v1/demo/iniciar", headers={"X-Clave-Demo": CLAVE}, json={"ritmo": 100})
    assert r.status_code == 422
    assert lanz.comandos == []


def test_la_corrida_termina_sola(entorno):
    g, lanz = entorno
    lanz.programa = ["true"]
    g.iniciar(Escenario())
    assert esperar(lambda: not g.corriendo())
    est = g.estado()
    assert est.fase == "inactiva" and est.codigo_salida == 0 and est.fin


def test_sin_codigo_de_simulacion_no_disponible(tmp_path):
    g = GestorSimulacion("http://127.0.0.1:8000", None, proyecto=tmp_path, dir_logs=tmp_path / "l")
    assert "correr_una" in g.motivo_no_disponible()
    with pytest.raises(LookupError):
        g.iniciar(Escenario())


def test_genera_la_demanda_si_falta_y_restaura_el_indice(tmp_path, monkeypatch):
    monkeypatch.setenv("SUMO_HOME", "/usr/share/sumo")
    p = proyecto_falso(tmp_path / "p")
    esc = p / "sumo" / "escenarios"
    (esc / "app50_s2.rou.xml").unlink()
    (esc / "escenarios.json").write_text('{"original": true}')
    (esc / "generar_escenarios.py").write_text(
        "import pathlib\n"
        "pathlib.Path('app50_s2.rou.xml').write_text('<routes/>')\n"
        "pathlib.Path('escenarios.json').write_text('{}')\n")
    lanz = Lanzador(["true"])
    g = GestorSimulacion("http://127.0.0.1:8000", None, proyecto=p, python="python3",
                         dir_logs=tmp_path / "l", lanzar=lanz)
    g.iniciar(Escenario())
    assert esperar(lambda: lanz.comandos and not g.corriendo())
    assert (esc / "app50_s2.rou.xml").exists()
    assert (esc / "escenarios.json").read_text() == '{"original": true}'


# --------------------------------------------------------------------------- ritmo en vivo

def test_ritmo_en_vivo_viaja_en_la_respuesta_del_paso(entorno):
    g, _ = entorno
    with cliente(g) as c:
        assert c.post("/api/v1/demo/ritmo", json={"ritmo": 10}).status_code == 401
        c.post("/api/v1/demo/iniciar", headers={"X-Clave-Demo": CLAVE}, json={"ritmo": 2})
        paso = {"t_sim": 1, "ts": "2026-11-18T03:00:00Z", "vehiculos": [], "peatones": [],
                "verdad": {"puestos": [], "estacionados": [], "falsas_liberaciones": []}}
        assert c.post("/api/v1/sim/paso", json=paso).json()["ritmo"] == 2.0
        r = c.post("/api/v1/demo/ritmo", headers={"X-Clave-Demo": CLAVE}, json={"ritmo": 10})
        assert r.status_code == 200 and r.json()["escenario"]["ritmo"] == 10.0
        assert c.post("/api/v1/sim/paso", json=dict(paso, t_sim=2)).json()["ritmo"] == 10.0
        assert c.post("/api/v1/demo/ritmo", headers={"X-Clave-Demo": CLAVE}, json={"ritmo": 3}).status_code == 422
