"""Configuración de las pruebas de S2 (peatones y sesiones): marcador `sumo` y escenario mínimo."""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ESCENARIO = Path(__file__).resolve().parents[1] / "escenario" / "tyrone" / "sumo"
DURACIONES_CORTAS_S = (240, 300, 360, 420, 480)  # estadías de la prueba (la demanda trae 10-120 min)


def pytest_configure(config):
    config.addinivalue_line("markers", "sumo: requiere SUMO (contenedor van3twin)")


@pytest.fixture
def escenario_mini(tmp_path):
    """Cinco autos de búsqueda de la demanda base, con estadías cortas, en una carpeta temporal.

    Devuelve la ruta del `.sumocfg`. La red y los parkingAreas son los de Tyrone (`proyecto/sumo`).
    """
    raiz = ET.parse(ESCENARIO / "demanda" / "demanda.rou.xml").getroot()
    busca = [v for v in raiz.findall("trip") if _clase(v) == "busca"][:5]
    rutas = ET.Element("routes")
    rutas.append(raiz.find("vType"))
    for trip, duracion in zip(busca, DURACIONES_CORTAS_S):
        trip.find("stop").set("duration", str(duracion))
        rutas.append(trip)
    (tmp_path / "demanda").mkdir()
    ET.ElementTree(rutas).write(tmp_path / "demanda" / "mini.rou.xml")

    cfg = tmp_path / "mini.sumocfg"
    cfg.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <input>
        <net-file value="{ESCENARIO / 'red' / 'centro.net.xml'}"/>
        <route-files value="{tmp_path / 'demanda' / 'mini.rou.xml'}"/>
        <additional-files value="{ESCENARIO / 'red' / 'centro.poly.xml'},{ESCENARIO / 'parqueos' / 'parqueos.add.xml'}"/>
    </input>
    <time><begin value="0"/><end value="16000"/></time>
    <processing><time-to-teleport value="300"/><ignore-route-errors value="true"/></processing>
    <report><no-step-log value="true"/></report>
</configuration>
""",
        encoding="utf-8",
    )
    return cfg


def _clase(trip):
    for p in trip.findall("param"):
        if p.get("key") == "clase":
            return p.get("value")
    return None
