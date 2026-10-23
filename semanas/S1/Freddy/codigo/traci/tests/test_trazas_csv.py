"""Las trazas generadas cumplen el CSV del contrato (§8), validado con `comun/esquemas.py`."""

import csv
from collections import Counter
from pathlib import Path

import pytest

from comun.esquemas import COLUMNAS_TRAZA, FilaTraza

TRAZAS = Path(__file__).resolve().parents[1] / "trazas"
MUESTRA = TRAZAS / "sumo_semilla1_muestra.csv"
COMPLETAS = sorted(TRAZAS.glob("sumo_semilla[0-9].csv"))


def _validar(ruta: Path, maximo=None):
    with ruta.open(encoding="utf-8", newline="") as f:
        lector = csv.DictReader(f)
        assert lector.fieldnames[:7] == COLUMNAS_TRAZA  # las 7 del contrato, primero y en orden
        ultimo_t = {}
        clases, casos = Counter(), Counter()
        v_ped = {"normal": [], "peaton_rapido": []}
        for i, fila in enumerate(lector):
            if maximo and i >= maximo:
                break
            ft = FilaTraza.desde_csv(fila)
            assert ft.t > ultimo_t.get(ft.usuario_id, -1)  # t creciente por usuario
            ultimo_t[ft.usuario_id] = ft.t
            assert ft.usuario_id.startswith(("sim_", "ped_"))
            clases[ft.modo_real.value] += 1
            casos[fila["caso"]] += 1
            if ft.usuario_id.startswith("ped_") and ft.modo_real.value == "a_pie":
                v_ped[fila["caso"]].append(float(fila["velocidad_real_mps"]))
    # Los peatones rápidos de verdad caminan más rápido (no solo están etiquetados así).
    media = {k: sum(v) / len(v) for k, v in v_ped.items() if v}
    if len(media) == 2:
        assert media["peaton_rapido"] > 1.3 * media["normal"], media
    return clases, casos


def test_muestra_valida_y_completa():
    assert MUESTRA.exists(), "Genera la muestra: python3 -m traci.generar_trazas --semilla 1 --muestra 5000"
    clases, casos = _validar(MUESTRA)
    assert sum(clases.values()) == 5000
    assert set(clases) == {"a_pie", "quieto", "vehiculo"}
    assert casos["congestion"] > 0 and casos["peaton_rapido"] > 0
    with MUESTRA.open(encoding="utf-8") as f:
        agentes = {linea.split(",", 1)[0] for linea in f} - {"usuario_id"}
    assert len(agentes) >= 15  # variedad: muchos agentes, no unas pocas trazas largas


@pytest.mark.parametrize("ruta", COMPLETAS, ids=[p.name for p in COMPLETAS])
def test_trazas_completas(ruta):
    """Las 3 semillas (si están generadas): esquema válido, 3 clases y tráfico lento."""
    clases, casos = _validar(ruta, maximo=200_000)
    assert set(clases) == {"a_pie", "quieto", "vehiculo"}
    assert casos["congestion"] > 0 and casos["peaton_rapido"] > 0
