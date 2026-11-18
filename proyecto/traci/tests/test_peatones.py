"""Peatones de diligencia con SUMO: cinco autos de búsqueda en el escenario mínimo.

Solo corren dentro del contenedor van3twin (con SUMO_HOME): `pytest traci/tests -m sumo`.
"""

import os
from pathlib import Path

import pytest

EN_CONTENEDOR = Path("/home/vanet/results").is_dir() and bool(os.environ.get("SUMO_HOME"))
pytestmark = [
    pytest.mark.sumo,
    pytest.mark.skipif(not EN_CONTENEDOR, reason="requiere el contenedor van3twin"),
]

ESCENARIO = Path(__file__).resolve().parents[1] / "escenario" / "tyrone" / "sumo"


@pytest.mark.parametrize(
    "p_regreso_corto, p_espera_en_auto, caso_esperado",
    [
        (0.0, 0.0, "diligencia"),
        (1.0, 0.0, "regreso_corto"),
        (0.0, 1.0, "en_auto"),
    ],
)
def test_todos_los_peatones_vuelven_y_ningun_auto_queda_parado(
    escenario_mini, tmp_path, p_regreso_corto, p_espera_en_auto, caso_esperado
):
    from traci.controlador import ConfigControlador, Controlador
    from traci.estados import ControlSesiones
    from traci.gps import EmuladorGPS
    from traci.peatones import GestorPeatones

    gestor = GestorPeatones(ESCENARIO / "demanda" / "destinos.csv", semilla=1,
                            p_regreso_corto=p_regreso_corto, p_espera_en_auto=p_espera_en_auto,
                            solo_web=False)  # se prueba el modo con todos los peatones (resultados)
    sesiones = ControlSesiones(EmuladorGPS(semilla=1), tmp_path, "mini")
    try:
        with Controlador(ConfigControlador(cfg=escenario_mini, etiqueta="s2_mini")) as ctrl:
            ctrl.agregar_hook(gestor.on_paso)
            ctrl.agregar_hook(sesiones.on_paso)
            ctrl.correr(16000)
            paradas = [v for v in ctrl.traci.vehicle.getIDList()
                       if ctrl.traci.vehicle.isStoppedParking(v)]
    finally:
        sesiones.cerrar()

    r = gestor.resumen()
    assert r["llegadas"] == 5
    assert r["vueltas"] == 5, r
    assert r["pendientes"] == 0 and r["liberados_sin_aparecer"] == 0, r
    assert r["casos"] == {caso_esperado: 5}
    assert paradas == []
    assert sesiones.llegadas == 5



def test_por_defecto_solo_bajan_los_conductores_web():
    """Desde el 2026-11-18: sin `solo_web=False`, los conductores simulados no se bajan."""
    from traci.peatones import GestorPeatones

    assert GestorPeatones(ESCENARIO / "demanda" / "destinos.csv", semilla=1).solo_web is True
