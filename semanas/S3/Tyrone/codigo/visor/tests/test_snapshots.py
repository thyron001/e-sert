"""Test 1: cada línea de los archivos de snapshots cumple `MensajeSnapshot` del contrato."""
import pytest

from comun.esquemas import MensajeSnapshot

from conftest import MUESTRA, SNAPSHOTS


@pytest.mark.parametrize("ruta", [SNAPSHOTS, MUESTRA], ids=["snapshots", "muestra"])
def test_lineas_validan_contra_contrato(ruta):
    if not ruta.exists():
        pytest.skip(f"no existe {ruta.name} (está en .gitignore; se genera con grabar_snapshots.py)")
    n = 0
    t_anterior = -1.0
    # Se recorre línea a línea para no cargar el archivo grande entero en memoria.
    with open(ruta, encoding="utf-8") as f:
        for num, linea in enumerate(f, start=1):
            if not linea.strip():
                continue
            msj = MensajeSnapshot.model_validate_json(linea)
            assert msj.tipo == "snapshot"
            # Los espejos deben ser vehículos presentes en el mismo snapshot.
            ids = {v.id for v in msj.vehiculos}
            faltan = [e for e in msj.espejos if e not in ids]
            assert not faltan, f"línea {num}: espejos sin vehículo {faltan}"
            # Cada puesto respeta su capacidad.
            for p in msj.puestos:
                assert p.ocupados <= p.capacidad, f"línea {num}: {p.puesto_id} sobreocupado"
            # El tiempo simulado avanza.
            assert msj.t_sim > t_anterior, f"línea {num}: t_sim no crece"
            t_anterior = msj.t_sim
            n += 1
    assert n > 0, f"{ruta.name} está vacío"
