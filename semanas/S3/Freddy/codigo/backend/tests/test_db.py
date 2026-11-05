"""Base de datos: carga de puestos.csv (formato de Tyrone), mock y horas UTC."""

from datetime import datetime

import pytest

from backend.nucleo.db import BaseDatos, Usuario, leer_puestos_csv, puestos_iniciales, ruta_puestos_proyecto

CSV = (
    "puesto_id,edge,lane,calle,capacidad,lat,lon,x,y\n"
    "pa_-106945247#0_0,-106945247#0,-106945247#0_1,Del Chorro,17,-2.8898155,-78.9956309,2617.66,1898.72\n"
    "pa_-118367899_0,-118367899,-118367899_1,Del Chorro,7,-2.8900644,-78.9980747,2345.85,1871.67\n"
)


def test_leer_puestos_csv(tmp_path):
    ruta = tmp_path / "puestos.csv"
    ruta.write_text(CSV, encoding="utf-8")
    puestos = leer_puestos_csv(ruta)
    assert [(p.id, p.capacidad) for p in puestos] == [("pa_-106945247#0_0", 17), ("pa_-118367899_0", 7)]
    assert puestos_iniciales(ruta)[0].calle == "Del Chorro"
    bd = BaseDatos()
    assert bd.cargar_puestos(puestos) == 2


def test_mock_si_no_hay_csv(tmp_path):
    puestos = puestos_iniciales(tmp_path / "no_existe.csv")
    assert len(puestos) == 20 and all(p.id.startswith("pa_mock") for p in puestos)
    assert ruta_puestos_proyecto().name == "puestos.csv"


def test_base_en_archivo(tmp_path):
    bd = BaseDatos(f"sqlite:///{tmp_path / 'esert.db'}")
    bd.cargar_puestos(puestos_iniciales(tmp_path / "x.csv"))
    assert (tmp_path / "esert.db").exists()


def test_hora_sin_zona_falla():
    bd = BaseDatos()
    with pytest.raises(Exception):
        with bd.transaccion() as s:
            s.add(Usuario(id="sim_x", creado=datetime(2026, 10, 20, 14, 0)))
            s.flush()
