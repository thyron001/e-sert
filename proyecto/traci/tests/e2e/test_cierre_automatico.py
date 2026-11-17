"""Cierre automático de punta a punta (S4-1): el peatón que hace diligencias no cierra; el auto
que sale sí, con retardo de cierre < 30 s.

- `test_..._con_sumo`: escenario mínimo en el contenedor `van3twin` (`escenario_cierre.py`),
  lanzado con `docker exec` desde la computadora o directo si ya se corre dentro del contenedor.
  Sin contenedor se salta limpio.
- `test_..._ventanas_ruidosas`: la misma regla con ventanas sintéticas con ruido de GPS y errores
  del clasificador; no necesita SUMO.

Correr: `pytest -m e2e` desde la carpeta que contiene `traci/`, `backend/` y `comun/`.
"""

from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import pytest

from traci.estados import MaquinaSesion

pytestmark = pytest.mark.e2e

AQUI = Path(__file__).resolve()
CODIGO = AQUI.parents[3]
CONTENEDOR = "van3twin"
RETARDO_MAX_S = 30.0
EN_CONTENEDOR = Path("/home/vanet/results").is_dir() and bool(os.environ.get("SUMO_HOME"))


def _ruta_en_contenedor(ruta: Path):
    raiz = next((p for p in AQUI.parents if (p / ".git").exists()), None)
    if raiz is None or raiz.parent.name != "results":
        return None
    return f"/home/vanet/results/{raiz.name}/" + ruta.resolve().relative_to(raiz).as_posix()


def _docker(*args, timeout=30):
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)


def _procesos_sumo():
    if EN_CONTENEDOR:
        r = subprocess.run(["bash", "-lc", "pgrep -x sumo; true"], capture_output=True, text=True)
    else:
        r = _docker("exec", CONTENEDOR, "bash", "-lc", "pgrep -x sumo; true")
    return set(r.stdout.split())


@pytest.fixture
def requiere_sumo():
    """Salta limpio sin SUMO; al terminar, no deben quedar procesos `sumo` nuevos."""
    if not EN_CONTENEDOR:
        if shutil.which("docker") is None:
            pytest.skip("sin SUMO: no hay `docker` (¿falta la integración WSL de Docker Desktop?)")
        if _ruta_en_contenedor(CODIGO) is None:
            pytest.skip("sin SUMO: el repo no está en van3twin-docker/results/e-sert")
        try:
            r = _docker("exec", CONTENEDOR, "which", "sumo", timeout=20)
        except (OSError, subprocess.TimeoutExpired) as err:
            pytest.skip(f"sin SUMO: docker no responde ({err})")
        if r.returncode != 0:
            pytest.skip(f"sin SUMO: el contenedor {CONTENEDOR} no responde: {(r.stderr or r.stdout).strip()[:160]}")
    antes = _procesos_sumo()
    yield
    fin = time.monotonic() + 10
    while (quedan := _procesos_sumo() - antes) and time.monotonic() < fin:
        time.sleep(0.5)
    assert not quedan, f"quedaron procesos sumo: {sorted(quedan)}"


def test_diligencias_no_cierran_y_la_salida_cierra_rapido_con_sumo(requiere_sumo):
    rel = f"traci/salidas/e2e_cierre_{uuid.uuid4().hex[:8]}.json"
    cmd = ["python3", "-m", "traci.tests.e2e.escenario_cierre", "--salida", rel]
    if EN_CONTENEDOR:
        r = subprocess.run(cmd, cwd=CODIGO, capture_output=True, text=True, timeout=240)
    else:
        r = _docker("exec", "-w", _ruta_en_contenedor(CODIGO), CONTENEDOR, *cmd, timeout=240)
    salida = CODIGO / rel
    try:
        assert r.returncode == 0, (r.stdout + r.stderr)[-3000:]
        assert "Traceback" not in r.stderr, r.stderr[-3000:]
        datos = json.loads(salida.read_text(encoding="utf-8"))
    finally:
        salida.unlink(missing_ok=True)

    peatones = datos["peatones"]
    assert peatones["llegadas"] == 5 and peatones["vueltas"] == 5, peatones
    assert peatones["casos"] == {"diligencia": 5}, peatones
    cierres = datos["cierres"]
    assert len(cierres) == 5 and datos["abiertas_al_final"] == 0, datos
    # Diligencias: ninguna sesión se cerró mientras el auto seguía estacionado.
    falsas = [c["veh"] for c in cierres if c["falsa"]]
    assert not falsas, (f"falsas liberaciones: {len(falsas)}/{len(cierres)} cierres con el auto estacionado "
                        f"({falsas}); clasificador {datos['sesiones_maquina'].get('ventanas_por_fuente')}")
    # Salida: cada auto que dejó el parkingArea se cerró por detección en menos de 30 s.
    for c in cierres:
        assert c["motivo"] == "deteccion", c
        assert c["t_salida_real"] is not None and c["retardo_cierre_s"] is not None, c
        assert 0 <= c["retardo_cierre_s"] < RETARDO_MAX_S, c
    assert datos["parados_al_final"] == []


# --------------------------------------------------------------------------- sin SUMO


def _diligencia(rng: random.Random, sigma_m: float = 6.0, p_error: float = 0.1):
    """Ventanas (modo, distancia) de alguien que se aleja a pie, hace diligencias y vuelve."""
    ida = [5 * i for i in range(1, 25)] + [120 + rng.uniform(-20, 20) for _ in range(60)]
    vuelta = [120 - 5 * i for i in range(1, 24)] + [3, 2, 2]
    for d in ida + vuelta:
        modo = "a_pie" if d > 3 else "quieto"
        if rng.random() < p_error:  # el clasificador se equivoca a veces (bus, trote)
            modo = rng.choice(["vehiculo", "quieto"])
        yield modo, max(0.0, d + rng.gauss(0, sigma_m))


@pytest.mark.parametrize("semilla", range(20))
def test_diligencias_y_salida_con_ventanas_ruidosas(semilla):
    rng = random.Random(semilla)
    m = MaquinaSesion(f"sim_e2e{semilla}")
    t = 0.0
    for modo, d in _diligencia(rng):
        t += 5
        tr = m.actualizar(modo, d, t)
        assert all(x.hacia != "CERRADA" for x in tr), f"cierre falso en t={t}: {tr}"
    assert m.estado in ("REGRESANDO", "ESTACIONADO"), m.estado
    # Arranca: a 8 m/s, ventanas de 5 s.
    salida = t
    for i in range(1, 7):
        t += 5
        if any(x.hacia == "CERRADA" for x in m.actualizar("vehiculo", 8 * 5 * i + rng.gauss(0, 6), t)):
            break
    assert m.estado == "CERRADA"
    assert t - salida < RETARDO_MAX_S, t - salida
