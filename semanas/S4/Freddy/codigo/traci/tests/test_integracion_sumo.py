"""Integración con SUMO: solo corre dentro del contenedor van3twin (con SUMO_HOME)."""

import os
from pathlib import Path

import pytest

# El proyecto usa el SUMO 1.12 del contenedor (CLAUDE.md), no uno instalado en la computadora.
EN_CONTENEDOR = Path("/home/vanet/results").is_dir() and bool(os.environ.get("SUMO_HOME"))
pytestmark = pytest.mark.skipif(not EN_CONTENEDOR, reason="requiere el contenedor van3twin")

CFG = Path(__file__).resolve().parents[1] / "escenario" / "tyrone" / "sumo" / "centro_red.sumocfg"


def test_carga_traci_de_sumo_sin_tapar_este_paquete():
    import sys

    import traci as este_paquete
    from traci.sumo import cargar_traci

    sumo_traci = cargar_traci()
    assert hasattr(sumo_traci, "simulationStep") and not hasattr(este_paquete, "simulationStep")
    assert sys.modules["traci"] is este_paquete


@pytest.mark.skipif(not CFG.exists(), reason="falta la copia del escenario (traci/obtener_escenario.py)")
def test_controlador_hooks_y_proyeccion():
    from traci.controlador import ConfigControlador, Controlador
    from traci.generar_trazas import conversor_red

    pasos = []
    with Controlador(ConfigControlador(cfg=CFG)) as ctrl:
        ctrl.agregar_hook(lambda c, t: pasos.append(t))
        assert ctrl.correr(5) == 0.0  # red sin demanda: correr() se detiene si no hay agentes
        for _ in range(5):
            ctrl.paso()
        rapido = conversor_red(CFG.parent / "red" / "centro.net.xml")
        lat, lon = ctrl.a_geo(1500.0, 1200.0)
        assert rapido(1500.0, 1200.0) == pytest.approx((lat, lon), abs=1e-9)
    assert pasos == [1.0, 2.0, 3.0, 4.0, 5.0]
